"""
execute_skill Tool - 触发 Skill Sub-agent 执行完整写作流程。

主 Agent 通过此工具将写作执行委托给 Skill Sub-agent。
Sub-agent 以 skill.md 正文为 instruction，通过 ReAct 循环自主完成
事实加载、草稿来源决策和写作，不依赖主 Agent 参与这些步骤。

Sub-agent 使用独立 InMemorySessionService，ReAct 历史不写入主 Agent session。
执行完成后，execute_skill 将写作产物从 Sub-agent session 转移到主 Agent session.state，
并将执行摘要写入 ctx.last_skill_execution_summary 供后续轮次参考。
"""

import importlib.util
import logging
import os
from typing import TYPE_CHECKING, List

from google.adk.agents import LlmAgent
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import ToolContext
from google.genai import types

if TYPE_CHECKING:
    from agent.adk.runner_adapter import ConversationContext
    from agent.models import SkillInfo

logger = logging.getLogger(__name__)


# ── 固定执行规范（注入到所有 Sub-agent instruction 末尾）───────────────────────

_SUBAGENT_EXECUTION_SPEC = """

## 执行规范

你是专注于文档编写的 AI 助手，使用 ReAct 推理模式执行写作任务。
请根据上方的写作规范完成任务，并遵守以下执行约束。

### 可用通用工具

- **get_fact_overview(category)**：加载项目概览清单，用于定位写作对象。
  category 可选：modules（模块清单）、usecases（用例清单）、classes（类包清单）、interfaces（接口清单）。

- **get_fact_detail(target_id, fact_type)**：加载某目标的详细事实信息。
  target_id 为目标标识符（如 mod-auth），fact_type 可选：usecases、classes、interfaces、prototypes。

- **get_current_draft()**：读取当前对话已有的文档草稿（修改场景必须先调用）。

- **list_saved_documents(doc_type?)**：列出历史已保存文档的元数据清单（不含正文）。

- **load_saved_document(doc_type, doc_name)**：加载历史保存文档的最新版本，注入写作上下文。

- **write_document(skill_id, module_name, context, user_intent)**：生成或修改文档正文，流式输出给用户。
  调用此工具完成写作；未调用此工具时不得声称"已完成"。

- **ask_user(question)**：向用户提问，用于执行层面的澄清（如写作对象有歧义、版本选择、细节超出事实库范围）。

### 写作约束

1. 所有文档内容必须基于项目事实，不得虚构。
2. 若无法从 user_intent 定位写作对象，调用 ask_user 澄清或终止写作。
3. 先用事实工具完成最小检索闭环，再决定是否 ask_user：
   - 先调用 get_fact_overview 定位目标模块、用例或对象标识；
   - 若概览里出现目标模块或相近名称，继续调用 get_fact_detail，或追加调用其他概览工具补足事实；
   - 只有在完成上述检索后，仍然无法确定写作对象，或用户明确要求的关键信息完全不存在时，才调用 ask_user。
4. 若事实不足以支撑完整写作，优先基于已有事实继续生成，并把缺口写成“待确认”或“待补充”；
   不要因为缺少原型、截图、页面文案就立刻 ask_user。
5. 草稿来源决策——结合当前保存状态和用户意图判断：
   - **有正式保存版本**（调用 list_saved_documents 能查到对应类型的文档）：
     修改意图默认以最新保存版本为基础，调用 load_saved_document 加载后再修改；
   - **只有未保存草稿**（list_saved_documents 无结果，但 get_current_draft 有内容）：
     修改意图以上一轮对话草稿为基础，调用 get_current_draft 加载后再修改；
   - **用户明确指定来源**（如"基于上次保存的 v1"、"用刚才写的草稿"）：按用户指定处理；
   - **均无草稿**：新建场景，无需询问。
6. 对于模块型写作任务，如果从 get_fact_overview("modules") 已能定位出目标模块（例如返回了 `模块名(mod-xxx)`），不得重复调用同一个概览工具两次以上；应继续加载相关事实或直接写作。
7. 写作完成后，最终响应须包含执行摘要：加载了哪些事实类型、基于哪个草稿版本（或新建）、生成文档字数。

所有输出使用中文。
"""


# ── 辅助函数 ──────────────────────────────────────────────────────────────────

def _read_skill_body(skill: "SkillInfo") -> str:
    """读取 skill.md 正文（去除 YAML frontmatter）。"""
    if not skill.skill_md_path:
        return f"# {skill.name}\n\n{skill.description}"

    try:
        with open(skill.skill_md_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        logger.warning(f"_read_skill_body: 读取 skill.md 失败 {skill.skill_md_path}: {e}")
        return f"# {skill.name}\n\n{skill.description}"

    # 去除 YAML frontmatter（--- ... \n--- 块）
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            return content[end + 4:].strip()

    return content.strip()


async def _extract_and_load_skill_tools(skill_body: str, skill_dir: str) -> list:
    """从 skill.md 正文中通过 LLM 提取专属工具文件路径，加载并返回工具函数列表。

    Args:
        skill_body: skill.md 的正文内容（不含 frontmatter）。
        skill_dir: skill 目录的绝对路径。

    Returns:
        工具函数列表。若 skill.md 中未声明工具，返回空列表。
    """
    import litellm
    from agent.adk.llm_adapter import get_litellm_model_config

    llm_config = get_litellm_model_config()
    if llm_config is None:
        logger.warning("_extract_and_load_skill_tools: 无 LLM 配置，跳过工具提取")
        return []

    prompt = (
        "从以下 skill.md 正文中提取所有专属工具文件的相对路径（相对于 skill 目录）。\n"
        "只返回路径列表，每行一个路径，不包含任何说明文字。\n"
        "如果没有声明任何工具文件，返回空字符串。\n\n"
        f"skill.md 正文：\n{skill_body}\n\n"
        "工具文件路径列表（每行一个，例如：tools/my_tool.py）："
    )

    try:
        response = await litellm.acompletion(
            model=llm_config.model,
            api_key=llm_config.api_key,
            api_base=llm_config.api_base,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=200,
        )
        raw = response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"_extract_and_load_skill_tools: LLM 提取失败: {e}")
        return []

    if not raw:
        return []

    paths = [
        line.strip()
        for line in raw.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    tool_functions = []
    for rel_path in paths:
        abs_path = os.path.join(skill_dir, rel_path)
        if not os.path.isfile(abs_path):
            logger.warning(f"_extract_and_load_skill_tools: 工具文件不存在: {abs_path}")
            continue

        try:
            module_name = os.path.splitext(os.path.basename(abs_path))[0]
            spec = importlib.util.spec_from_file_location(
                f"skill_tool_{module_name}", abs_path
            )
            if spec is None or spec.loader is None:
                logger.warning(f"_extract_and_load_skill_tools: 无法加载模块: {abs_path}")
                continue

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            tool_fn = getattr(module, module_name, None)
            if callable(tool_fn):
                tool_functions.append(tool_fn)
                logger.info(
                    f"_extract_and_load_skill_tools: 加载工具 {module_name} from {abs_path}"
                )
            else:
                logger.warning(
                    f"_extract_and_load_skill_tools: 模块 {module_name} 未暴露同名可调用函数"
                )
        except Exception as e:
            logger.warning(
                f"_extract_and_load_skill_tools: 加载工具模块失败 {abs_path}: {e}"
            )

    return tool_functions


def _build_skill_subagent(
    skill: "SkillInfo",
    ctx: "ConversationContext",
    llm_config,
    skill_specific_tools: list,
) -> LlmAgent:
    """创建 Skill Sub-agent（LlmAgent）。

    instruction = skill.md 正文 + 固定执行规范
    工具列表 = 通用工具集 + Skill 专属工具

    Args:
        skill: SkillInfo 实例。
        ctx: 当前对话上下文（与主 Agent 共享）。
        llm_config: LiteLLM 模型配置。
        skill_specific_tools: 已加载的 Skill 专属工具函数列表。

    Returns:
        LlmAgent 实例。
    """
    from agent.adk.fact_tools import create_fact_tools
    from agent.adk.write_document_tool import create_write_document_tool
    from agent.adk.draft_tool import create_get_current_draft_tool
    from agent.adk.ask_user_tool import create_ask_user_tool
    from agent.adk.saved_doc_tools import create_saved_doc_tools

    skill_body = _read_skill_body(skill)
    instruction = skill_body + _SUBAGENT_EXECUTION_SPEC

    # 通用工具集（与主 Agent 共享同一 ctx）
    get_fact_overview_fn, get_fact_detail_fn = create_fact_tools(ctx)
    list_saved_documents_fn, load_saved_document_fn = create_saved_doc_tools(ctx)
    skills_map = {skill.id: skill}

    tools: List = [
        create_get_current_draft_tool(ctx),
        list_saved_documents_fn,
        load_saved_document_fn,
        get_fact_overview_fn,
        get_fact_detail_fn,
        create_write_document_tool(ctx, skills_map),
        create_ask_user_tool(ctx),
    ] + skill_specific_tools

    agent = LlmAgent(
        name=f"doc_worker_{skill.id.replace('-', '_')}",
        model=LiteLlm(
            model=llm_config.model,
            api_key=llm_config.api_key,
            api_base=llm_config.api_base,
        ),
        instruction=instruction,
        tools=tools,
    )

    logger.info(
        f"_build_skill_subagent: 创建 Sub-agent skill_id={skill.id}, 工具数={len(tools)}"
    )
    return agent


def _build_subagent_input(user_intent: str, ctx: "ConversationContext") -> str:
    """构造 Sub-agent 的初始输入消息，注入 ctx 状态摘要。

    Args:
        user_intent: 主 Agent 提炼的结构化写作意图。
        ctx: 当前对话上下文。

    Returns:
        Sub-agent 初始输入字符串。
    """
    parts = []

    context_hints = []
    if ctx.loaded_base_draft:
        char_count = len(ctx.loaded_base_draft)
        context_hints.append(
            f"当前已有草稿（约 {char_count} 字），可调用 get_current_draft 获取全文。"
        )
    if ctx.last_skill_execution_summary:
        context_hints.append(
            f"上次写作执行摘要：{ctx.last_skill_execution_summary}"
        )

    if context_hints:
        parts.append("【上下文信息】\n" + "\n".join(context_hints))

    parts.append(f"【写作任务】\n{user_intent}")

    return "\n\n".join(parts)


# ── 工厂函数（注册到主 Agent）─────────────────────────────────────────────────

def create_execute_skill_tool(ctx: "ConversationContext", skills_map: dict):
    """创建 execute_skill 工具函数，注册到主 Agent。

    Args:
        ctx: 当前对话上下文。
        skills_map: skill_id → SkillInfo 查找表。

    Returns:
        execute_skill 工具函数。
    """

    async def execute_skill(
        skill_id: str,
        user_intent: str,
        tool_context: ToolContext,
    ) -> str:
        """执行指定 Skill，创建 Skill Sub-agent 完成文档写作全流程。

        主 Agent 在确定写作意图和目标 Skill 后调用此工具。
        Sub-agent 将自主完成事实加载、草稿来源决策和文档写作，
        主 Agent 不参与这些执行步骤。

        Args:
            skill_id: 要执行的 Skill 的 id（如 "write-requirements"）。
            user_intent: 结构化的写作意图描述，须包含写作对象名称、文档类型、写作重点等信息。
                例如："为用户认证模块编写需求规格说明书，重点覆盖登录和权限验证两个用例"

        Returns:
            执行摘要，描述本次写作完成情况（加载了哪些事实、生成了多少字等）。
        """
        from agent.adk.llm_adapter import get_litellm_model_config

        if skill_id not in skills_map:
            return f"错误：未找到 Skill '{skill_id}'，请检查 skill_id 是否正确。"

        skill = skills_map[skill_id]
        llm_config = get_litellm_model_config()
        if llm_config is None:
            return "错误：未配置 LLM 模型，无法执行 Skill。"

        # 加载 Skill 专属工具
        skill_dir = (
            os.path.dirname(skill.skill_md_path) if skill.skill_md_path else ""
        )
        skill_body = _read_skill_body(skill)
        skill_specific_tools = []
        if skill_dir:
            skill_specific_tools = await _extract_and_load_skill_tools(
                skill_body, skill_dir
            )

        # 创建 Sub-agent
        subagent = _build_skill_subagent(skill, ctx, llm_config, skill_specific_tools)

        # Sub-agent 使用独立 session（与主 Agent 隔离）
        subagent_session_service = InMemorySessionService()
        subagent_session_id = f"subagent_{ctx.conversation_id}_{skill_id}"
        subagent_user_id = f"subuser_{ctx.conversation_id}"

        await subagent_session_service.create_session(
            app_name="doc_assist_subagent",
            user_id=subagent_user_id,
            session_id=subagent_session_id,
        )

        subagent_runner = Runner(
            agent=subagent,
            session_service=subagent_session_service,
            app_name="doc_assist_subagent",
        )

        # 构造 Sub-agent 初始输入（注入 ctx 状态摘要）
        initial_input = _build_subagent_input(user_intent, ctx)
        start_message = types.Content(
            role="user",
            parts=[types.Part(text=initial_input)],
        )

        # Sub-agent 工具调用的前端显示文本
        _SUBAGENT_TOOL_DISPLAY = {
            "get_fact_overview":    "加载项目概览",
            "get_fact_detail":      "加载事实详情",
            "get_current_draft":    "加载已有草稿",
            "list_saved_documents": "查询历史文档",
            "load_saved_document":  "加载历史版本",
            "write_document":       "生成文档内容",
            "ask_user":             "向用户确认",
        }

        # 通知前端 Sub-agent 开始执行（显示在可观测面板）
        await ctx.ws_sender({
            "type": "subagent_start",
            "skill_id": skill_id,
            "skill_name": skill.name,
        })

        # 运行 Sub-agent，将执行步骤实时转发给前端（可观测面板）
        final_text = ""
        try:
            async for event in subagent_runner.run_async(
                user_id=subagent_user_id,
                session_id=subagent_session_id,
                new_message=start_message,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            ):
                # 诊断日志：记录所有事件类型，排查 get_function_calls 是否有效
                func_calls = event.get_function_calls()
                logger.debug(
                    f"subagent event: author={getattr(event, 'author', None)}, "
                    f"partial={getattr(event, 'partial', None)}, "
                    f"is_final={event.is_final_response()}, "
                    f"func_calls={[fc.name for fc in func_calls] if func_calls else []}, "
                    f"has_content={bool(event.content)}"
                )

                # Sub-agent 工具调用 → 转发为 status 事件（显示在可观测面板）
                if func_calls:
                    for fc in func_calls:
                        tool_name = fc.name
                        label = _SUBAGENT_TOOL_DISPLAY.get(tool_name, f"调用：{tool_name}")
                        logger.info(f"subagent tool_call: {tool_name}")
                        await ctx.ws_sender({
                            "type": "status",
                            "sub": "tool_call",
                            "tool": tool_name,
                            "content": label,
                        })

                # Sub-agent 推理文字 → 转发为 thinking 事件
                # 捕获每个 ReAct 步骤中 LLM 在决定调用工具之前生成的推理内容
                # 注意：不捕获最终响应（摘要），只捕获中间推理过程
                if event.content and not event.is_final_response():
                    for part in event.content.parts or []:
                        if getattr(part, 'text', None) and part.text.strip():
                            await ctx.ws_sender({"type": "thinking", "content": part.text})

                # 捕获 Sub-agent 最终响应文本（执行摘要）
                if event.is_final_response() and event.content:
                    for part in event.content.parts or []:
                        if part.text:
                            final_text += part.text

        except Exception as e:
            logger.error(
                f"execute_skill: Sub-agent 运行出错 skill_id={skill_id}: {e}",
                exc_info=True,
            )
            return f"Skill 执行出错：{str(e)}"

        # 将 Sub-agent 写入的写作产物转移到主 Agent session.state
        # Sub-agent 的 write_document 工具写入了子 session.state，
        # 此处将其转移到主 Agent tool_context.state，供 runner_adapter 读取持久化
        try:
            subagent_session = await subagent_session_service.get_session(
                app_name="doc_assist_subagent",
                user_id=subagent_user_id,
                session_id=subagent_session_id,
            )
            if subagent_session and subagent_session.state.get("draft_content"):
                tool_context.state["draft_content"] = subagent_session.state[
                    "draft_content"
                ]
                tool_context.state["selected_skill_id"] = subagent_session.state.get(
                    "selected_skill_id", skill_id
                )
                if subagent_session.state.get("doc_type"):
                    tool_context.state["doc_type"] = subagent_session.state["doc_type"]
                if subagent_session.state.get("module_name"):
                    tool_context.state["module_name"] = subagent_session.state[
                        "module_name"
                    ]
                logger.info(
                    f"execute_skill: 已将写作产物从 Sub-agent 转移到主 Agent session.state"
                    f" (skill_id={skill_id}, "
                    f"chars={len(subagent_session.state['draft_content'])})"
                )
        except Exception as e:
            logger.warning(f"execute_skill: 转移 session.state 失败: {e}")

        # 将执行摘要写入 ctx，供后续轮次的 Sub-agent 参考
        summary = final_text.strip() or f"Skill {skill_id} 执行完成"
        ctx.last_skill_execution_summary = summary

        logger.info(
            f"execute_skill: 完成 skill_id={skill_id}, 摘要长度={len(summary)}"
        )
        return summary

    return execute_skill
