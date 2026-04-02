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
import re
from typing import TYPE_CHECKING, List

try:
    from google.adk.agents import LlmAgent
    from google.adk.agents.run_config import RunConfig, StreamingMode
    from google.adk.models.lite_llm import LiteLlm
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.adk.tools import ToolContext
    from google.genai import types
except ModuleNotFoundError:  # pragma: no cover - fallback for unit tests
    class LlmAgent:  # type: ignore[override]
        pass

    class RunConfig:  # type: ignore[override]
        def __init__(self, *args, **kwargs):
            pass

    class StreamingMode:  # type: ignore[override]
        SSE = "SSE"

    class LiteLlm:  # type: ignore[override]
        def __init__(self, *args, **kwargs):
            pass

    class Runner:  # type: ignore[override]
        def __init__(self, *args, **kwargs):
            pass

    class InMemorySessionService:  # type: ignore[override]
        async def create_session(self, *args, **kwargs):
            return None

    class ToolContext:  # type: ignore[override]
        pass

    class _TypesFallback:  # pragma: no cover - simple namespace for tests
        class Content:
            def __init__(self, role=None, parts=None):
                self.role = role
                self.parts = parts or []

        class Part:
            def __init__(self, text=None):
                self.text = text

    types = _TypesFallback()

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

- **resolve_target_module(target_ref)**：定位目标模块。
  对于模块级写作任务，优先先调用它确认“写的是哪个模块”。
  返回可能是：唯一模块、多个候选模块（歧义）或未找到。

- **load_module_fact_sheet(target_ref)**：按模块聚合根加载模块事实主档。
  在目标模块唯一明确后，优先调用它获取模块事实主文档正文，作为写作主上下文。
  当前项目的模块事实主档已经覆盖模块级写作所需的描述、用例、功能点、API、页面、依赖等章节；拿到主档正文后，应直接基于该正文推理和写作。

- **get_fact_overview(category)**：加载项目概览清单，用于定位写作对象。
  category 可选：systems、subsystems、modules、usecases、function_points、apis、classes、prototypes。
  兼容别名：interfaces。

- **get_fact_detail(target_id, fact_type)**：加载某目标的详细事实信息。
  对于模块型事实，target_id 可传稳定模块 ID，也可直接传模块名/别名，工具会自动解析；若同名模块有多个，工具会返回歧义提示。
  fact_type 可选：
  module、description、usecases、function_points、apis、classes、prototypes、dependencies、remarks。
  兼容别名：interfaces。

- **get_current_draft()**：读取当前对话已有的文档草稿（修改场景必须先调用）。

- **list_saved_documents(doc_type?)**：列出历史已保存文档的元数据清单（不含正文）。

- **load_saved_document(doc_type, doc_name)**：加载历史保存文档的最新版本，注入写作上下文。

- **write_document(skill_id, module_name, context, user_intent)**：生成或修改文档正文，流式输出给用户。
  调用此工具完成写作；未调用此工具时不得声称"已完成"。

- **ask_user(question)**：向用户提问，用于执行层面的澄清（如写作对象有歧义、版本选择、细节超出事实库范围）。

### 写作约束

1. 所有文档内容必须基于项目事实，不得虚构。
2. 若【上下文信息】或 `get_current_draft()` 已明确给出“当前文档目标”，且用户没有明确要求切换到别的模块/文档，则默认本轮是在继续修改该文档，不要把它当成新的模块定位任务。
3. 先用事实工具完成最小检索闭环，再决定是否 ask_user：
   - 若当前对话已有草稿且本轮是修改请求，应先调用 `get_current_draft()` 加载草稿，并沿用该草稿对应的模块/文档目标；
   - 只有在没有可沿用的当前文档目标、且本轮确实是新的模块级写作任务时，才调用 `resolve_target_module` 定位目标模块；
   - 若返回唯一模块，优先调用 `load_module_fact_sheet` 加载模块事实主档；
   - 若返回多个候选模块或未找到，不要继续猜测，不要先加载某个候选模块详情，应立即调用 `ask_user` 请用户明确目标模块；
   - 只有当用户要求列清单、看范围或目标对象本身不是模块时，才优先调用 `get_fact_overview`；
   - 当前阶段不要再为同一模块重复调用 `get_fact_detail(description/usecases/function_points/apis/prototypes/dependencies/remarks)`；模块事实主档已是模块级完整事实正文；
   - 仅当未来存在主档未覆盖的资源型事实入口，或用户明确要求额外专项资源时，才按需调用 `get_fact_detail`；
   - 只有在完成上述检索后，仍然无法确定写作对象，或用户明确要求的关键信息完全不存在时，才调用 ask_user。
4. 若事实不足以支撑完整写作，优先基于已有事实继续生成，并把缺口写成“待确认”或“待补充”；
   不要因为缺少原型、截图、页面文案就立刻 ask_user。
5. 草稿来源决策——结合当前保存状态和用户意图判断：
   - **有正式保存版本**（调用 list_saved_documents 能查到对应类型的文档）：
     修改意图默认以最新保存版本为基础，调用 load_saved_document 加载后再修改；
   - **只有未保存草稿**（list_saved_documents 无结果，但 get_current_draft 有内容）：
     修改意图以上一轮对话草稿为基础，调用 get_current_draft 加载后再修改，并把该草稿的模块/文档目标视为本轮唯一写作对象；
   - **用户明确指定来源**（如"基于上次保存的 v1"、"用刚才写的草稿"）：按用户指定处理；
   - **均无草稿**：新建场景，无需询问。
6. 写作完成后，最终响应只输出“本轮写作完成总结”，不得再次输出或改写文档正文。
   最终响应建议包含：
   - 事实来源说明
   - 质量检查结论
   - 建议（如有）
   最终响应应简洁，聚焦执行过程与结果质量，不要重复正文内容。
7. 若需要向用户补充确认信息，必须调用 ask_user(question)。
   禁止在推理文本、过程说明、最终响应或正文中直接输出“请问…”、“为了准确编写…”、“我需要了解…”等提问内容。
   所有面向用户的澄清问题都必须通过 ask_user 发出。

所有输出使用中文。
"""


def _extract_text_from_event(event) -> str:
    if not event.content:
        return ""
    parts = []
    for part in event.content.parts or []:
        text = getattr(part, "text", None)
        if text:
            parts.append(text)
    return "".join(parts)


def _compute_stream_delta(previous_text: str, incoming_text: str) -> tuple[str, str]:
    if not incoming_text:
        return "", previous_text
    if incoming_text.startswith(previous_text):
        return incoming_text[len(previous_text):], incoming_text
    if previous_text.endswith(incoming_text):
        return "", previous_text
    return incoming_text, previous_text + incoming_text


def _normalize_reflection_text(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^\s*(?:#+\s*)?(?:执行摘要|完成总结)\s*\n+", "", cleaned)
    return cleaned.strip()


async def _generate_context_summary(
    llm_config,
    user_intent: str,
    draft_content: str,
    reflection_text: str,
) -> str:
    import litellm

    prompt = (
        "请根据以下文档写作结果，生成一段供上层 Agent 维持上下文的压缩摘要。\n"
        "要求：\n"
        "1. 使用中文；\n"
        "2. 控制在 120-220 字；\n"
        "3. 只保留后续继续修改文档最关键的信息：文档对象、类型、主要覆盖范围、明显待确认项；\n"
        "4. 不要写客套话，不要重复过程细节，不要输出 Markdown 标题。\n\n"
        f"用户任务：{user_intent}\n\n"
        f"文档正文前 4000 字：\n{draft_content[:4000]}\n\n"
        f"写作完成总结：\n{reflection_text[:2000]}"
    )

    response = await litellm.acompletion(
        model=llm_config.model,
        api_key=llm_config.api_key,
        api_base=llm_config.api_base,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=220,
    )
    return (response.choices[0].message.content or "").strip()


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
    resolve_target_module_fn, load_module_fact_sheet_fn, get_fact_overview_fn, get_fact_detail_fn = create_fact_tools(ctx)
    list_saved_documents_fn, load_saved_document_fn = create_saved_doc_tools(ctx)
    skills_map = {skill.id: skill}

    tools: List = [
        create_get_current_draft_tool(ctx),
        list_saved_documents_fn,
        load_saved_document_fn,
        resolve_target_module_fn,
        load_module_fact_sheet_fn,
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
    current_target_name = ctx.loaded_base_doc_name or ctx.current_module_name
    current_target_id = ctx.loaded_base_module_id or ctx.current_module_id
    current_target_scope = " / ".join(
        item for item in [ctx.current_system_name, ctx.current_subsystem_name] if item
    )

    if ctx.conversation_has_draft:
        context_hints.append(
            "当前对话已有延续中的文档草稿；若本轮是修改请求，请先调用 get_current_draft 获取全文。"
        )
    if current_target_name or current_target_id:
        target_label = current_target_name or "当前文档"
        if current_target_scope:
            target_label = f"{current_target_scope} / {target_label}"
        if current_target_id:
            target_label = f"{target_label} ({current_target_id})"
        context_hints.append(
            f"当前文档目标：{target_label}。若用户未明确要求切换对象，本轮继续修改时直接沿用该目标，不要重新做模块消歧。"
        )
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
            "resolve_target_module": "定位目标模块",
            "load_module_fact_sheet": "加载模块事实主档",
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
        reflection_buffer = ""
        reflection_started = False
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
                # write_document 完成前，这些内容代表普通 ReAct 推理。
                # write_document 完成后，模型继续生成的是“写作完成总结”，
                # 需要单独展示到右侧过程明细，而不是作为新的思考链。
                if event.content and not event.is_final_response():
                    event_text = _extract_text_from_event(event)
                    if not event_text.strip():
                        continue
                    if ctx.draft_updated:
                        delta, reflection_buffer = _compute_stream_delta(
                            reflection_buffer,
                            event_text,
                        )
                        if delta.strip():
                            if not reflection_started:
                                reflection_started = True
                                await ctx.ws_sender({
                                    "type": "status",
                                    "sub": "tool_call",
                                    "tool": "write_reflection",
                                    "content": "写作完成总结",
                                })
                            await ctx.ws_sender({
                                "type": "reflection",
                                "content": delta,
                            })
                    else:
                        await ctx.ws_sender({"type": "thinking", "content": event_text})

                # 捕获 Sub-agent 最终响应文本（写作完成总结）
                if event.is_final_response() and event.content:
                    final_text = _extract_text_from_event(event)
                    if ctx.draft_updated and final_text.strip():
                        delta, reflection_buffer = _compute_stream_delta(
                            reflection_buffer,
                            final_text,
                        )
                        if delta.strip():
                            if not reflection_started:
                                reflection_started = True
                                await ctx.ws_sender({
                                    "type": "status",
                                    "sub": "tool_call",
                                    "tool": "write_reflection",
                                    "content": "写作完成总结",
                                })
                            await ctx.ws_sender({
                                "type": "reflection",
                                "content": delta,
                            })
                    else:
                        reflection_buffer = final_text

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

        reflection_text = _normalize_reflection_text(reflection_buffer)
        if not reflection_text:
            reflection_text = f"已完成 {skill.name} 写作。"

        # 生成供主 Agent 续写时使用的压缩摘要，并在右侧过程明细中单独标识。
        compact_summary = ""
        try:
            if llm_config is not None:
                await ctx.ws_sender({
                    "type": "status",
                    "sub": "tool_call",
                    "tool": "write_context_summary",
                    "content": "写作摘要生成",
                })
                draft_content = tool_context.state.get("draft_content", "")
                compact_summary = await _generate_context_summary(
                    llm_config=llm_config,
                    user_intent=user_intent,
                    draft_content=draft_content,
                    reflection_text=reflection_text,
                )
                if compact_summary:
                    await ctx.ws_sender({
                        "type": "summary",
                        "content": compact_summary,
                    })
        except Exception as e:
            logger.warning(f"execute_skill: 生成压缩摘要失败 skill_id={skill_id}: {e}")

        # 将压缩摘要写入 ctx，供后续轮次的 Sub-agent / 主 Agent 参考
        summary = compact_summary.strip() or reflection_text or f"Skill {skill_id} 执行完成"
        ctx.last_skill_execution_summary = summary

        logger.info(
            f"execute_skill: 完成 skill_id={skill_id}, 摘要长度={len(summary)}"
        )
        return summary

    return execute_skill
