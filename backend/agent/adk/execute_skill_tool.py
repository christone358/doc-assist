"""
execute_skill Tool - 触发 Skill Sub-agent 执行完整写作流程。

主 Agent 通过此工具将写作执行委托给 Skill Sub-agent。
Sub-agent 以 skill.md 正文为 instruction，通过 ReAct 循环自主完成
事实加载、草稿来源决策和写作，不依赖主 Agent 参与这些步骤。

Sub-agent 使用独立 InMemorySessionService，ReAct 历史不写入主 Agent session。
执行完成后，execute_skill 将写作产物从 Sub-agent session 转移到主 Agent session.state，
并将执行摘要写入 ctx.last_skill_execution_summary 供后续轮次参考。
"""

import logging
import json
import re
import uuid
from typing import TYPE_CHECKING, List

try:
    from google.adk.agents import LlmAgent
    from google.adk.agents.run_config import RunConfig, StreamingMode
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

_HALLUCINATED_TOOL_NAMES = {"thought", "thinking", "reflection"}
_HALLUCINATED_TOOL_PREFIX_RE = re.compile(
    r'^\s*\{\s*"name"\s*:\s*"(thought|thinking|reflection)"',
    re.IGNORECASE,
)


def _extract_text_from_event(event) -> str:
    if not event.content:
        return ""
    parts = []
    for part in event.content.parts or []:
        text = getattr(part, "text", None)
        if text:
            parts.append(text)
    return _strip_leading_hallucinated_tool_calls("".join(parts))


def _strip_leading_hallucinated_tool_calls(text: str) -> str:
    if not text:
        return ""

    stripped = text.lstrip()
    if not stripped.startswith("{"):
        return text

    decoder = json.JSONDecoder()
    idx = 0
    consumed_any = False

    while idx < len(stripped):
        while idx < len(stripped) and stripped[idx].isspace():
            idx += 1
        if idx >= len(stripped):
            break
        if stripped[idx] != "{":
            break

        try:
            obj, end = decoder.raw_decode(stripped, idx)
        except json.JSONDecodeError:
            if consumed_any or _HALLUCINATED_TOOL_PREFIX_RE.match(stripped):
                return ""
            return text

        if not isinstance(obj, dict):
            break

        tool_name = str(obj.get("name") or "").strip().lower()
        arguments = obj.get("arguments")
        if tool_name not in _HALLUCINATED_TOOL_NAMES:
            break
        if arguments is not None and not isinstance(arguments, dict):
            break

        consumed_any = True
        idx = end

    if not consumed_any:
        return text

    return stripped[idx:].lstrip()


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


def _merge_subagent_state_into_parent(
    parent_ctx: "ConversationContext",
    tool_state: dict,
    subagent_state: dict,
    fallback_skill_id: str,
) -> bool:
    """Promote sub-agent writing state into the parent orchestrator context."""
    draft_content = subagent_state.get("draft_content")
    if not draft_content:
        return False

    tool_state["draft_content"] = draft_content
    tool_state["selected_skill_id"] = subagent_state.get(
        "selected_skill_id", fallback_skill_id
    )

    if subagent_state.get("doc_type"):
        tool_state["doc_type"] = subagent_state["doc_type"]
    if subagent_state.get("module_name"):
        tool_state["module_name"] = subagent_state["module_name"]
        parent_ctx.current_module_name = subagent_state["module_name"]
    if subagent_state.get("module_id"):
        tool_state["module_id"] = subagent_state["module_id"]
        parent_ctx.current_module_id = subagent_state["module_id"]

    parent_ctx.draft_updated = True
    return True


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
        **llm_config.request_kwargs,
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


def _build_skill_subagent(
    skill: "SkillInfo",
    ctx: "ConversationContext",
    llm_config,
) -> LlmAgent:
    """创建 Skill Sub-agent（LlmAgent）。

    instruction = skill.md 正文 + 固定执行规范
    工具列表 = 通用工具集 + 当前 Skill 绑定的内部 `skill.*` 工具

    Args:
        skill: SkillInfo 实例。
        ctx: 当前对话上下文（与主 Agent 共享）。
        llm_config: LiteLLM 模型配置。
    Returns:
        LlmAgent 实例。
    """
    from agent.adk.prompt_loader import load_prompt_template
    from agent.adk.llm_adapter import build_adk_litellm_model
    from agent.adk.thought_tool import create_thought_tool, should_enable_thought_tool
    from agent.adk.tool_catalog import (
        build_skill_subagent_tool_view,
        render_tool_section,
    )

    skill_body = _read_skill_body(skill)
    skills_map = {skill.id: skill}
    tool_view = build_skill_subagent_tool_view(ctx, skill, skills_map)
    tool_section = render_tool_section(tool_view, "### 可用通用工具")
    instruction = skill_body + "\n\n" + load_prompt_template(
        "subagent_execution.md",
        slots={
            "tool_section": tool_section,
        },
    )
    tools: List = list(tool_view.tools)
    if should_enable_thought_tool(llm_config):
        tools.append(create_thought_tool())

    agent = LlmAgent(
        name=f"doc_worker_{skill.id.replace('-', '_')}",
        model=build_adk_litellm_model(llm_config),
        instruction=instruction,
        tools=tools,
    )

    logger.info(
        f"_build_skill_subagent: 创建 Sub-agent skill_id={skill.id}, "
        f"工具数={len(tools)}, tool_ids={list(tool_view.tool_ids)}"
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
    if ctx.clarification_context:
        context_hints.append(
            "已有澄清结论：\n" + "\n".join(ctx.clarification_context[-3:])
        )

    if context_hints:
        parts.append("【上下文信息】\n" + "\n".join(context_hints))

    parts.append(f"【写作任务】\n{user_intent}")

    return "\n\n".join(parts)


def _build_subagent_context(parent_ctx: "ConversationContext") -> "ConversationContext":
    """Create an isolated sub-agent context from the parent's minimal handoff.

    The sub-agent keeps its own working context for MCP-loaded facts / docs /
    skill resources. Only stable handoff signals are copied from the parent.
    """
    from agent.adk.runner_adapter import ConversationContext

    return ConversationContext(
        conversation_id=parent_ctx.conversation_id,
        ws_sender=parent_ctx.ws_sender,
        conversation_manager=parent_ctx.conversation_manager,
        orchestrator_execution_id=parent_ctx.orchestrator_execution_id,
        conversation_has_draft=parent_ctx.conversation_has_draft,
        last_skill_execution_summary=parent_ctx.last_skill_execution_summary,
        loaded_base_doc_name=parent_ctx.loaded_base_doc_name,
        loaded_base_module_id=parent_ctx.loaded_base_module_id,
        current_module_id=parent_ctx.current_module_id,
        current_module_name=parent_ctx.current_module_name,
        current_system_name=parent_ctx.current_system_name,
        current_subsystem_name=parent_ctx.current_subsystem_name,
        user_input_queue=parent_ctx.user_input_queue,
        execution_events=parent_ctx.execution_events,
        execution_nodes=parent_ctx.execution_nodes,
        execution_node_index=parent_ctx.execution_node_index,
        execution_node_order=parent_ctx.execution_node_order,
        open_tool_nodes=parent_ctx.open_tool_nodes,
        current_skill_node_id=parent_ctx.current_skill_node_id,
        current_question_node_id=parent_ctx.current_question_node_id,
        clarification_context=parent_ctx.clarification_context,
    )


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
        from agent.adk.runner_adapter import (
            append_thought,
            close_active_thought,
            create_execution_node,
            create_system_state_node,
            start_tool_node,
            update_execution_node,
            emit_execution_event,
        )
        from agent.models import (
            ExecutionActor,
            ExecutionEventStatus,
            ExecutionNodeType,
            ExecutionPhase,
            ExecutionNodeStatus,
            SkillExecutionFailure,
            SkillExecutionResult,
            SkillExecutionStatus,
        )

        if skill_id not in skills_map:
            return f"错误：未找到 Skill '{skill_id}'，请检查 skill_id 是否正确。"

        skill = skills_map[skill_id]
        llm_config = get_litellm_model_config()
        if llm_config is None:
            return "错误：未配置 LLM 模型，无法执行 Skill。"

        # 创建 Sub-agent，并为其分配独立 working context。
        # 主 Agent 只传递最小 handoff 信息，不直接共享完整资源上下文。
        execution_id = f"skill-{uuid.uuid4().hex}"
        sub_ctx = _build_subagent_context(ctx)
        sub_ctx.current_execution_id = execution_id
        subagent = _build_skill_subagent(skill, sub_ctx, llm_config)
        if ctx.current_skill_node_id:
            await update_execution_node(
                ctx,
                ctx.current_skill_node_id,
                status=ExecutionNodeStatus.RUNNING,
                title=skill.name,
                detail_text=f"Skill：{skill.name}",
                metadata_updates={"execution_id": execution_id},
            )
        await emit_execution_event(
            ctx,
            execution_id=execution_id,
            parent_execution_id=ctx.orchestrator_execution_id,
            actor=ExecutionActor.ORCHESTRATOR,
            phase=ExecutionPhase.DELEGATE,
            name="skill_dispatch",
            status=ExecutionEventStatus.STARTED,
            display_text=f"已委派给子 Agent：{skill.name}",
            data={
                "skill_id": skill_id,
                "node_id": ctx.current_skill_node_id,
                "parent_node_id": None,
            },
        )

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
        initial_input = _build_subagent_input(user_intent, sub_ctx)
        start_message = types.Content(
            role="user",
            parts=[types.Part(text=initial_input)],
        )

        # Sub-agent 工具调用的前端显示文本
        _SUBAGENT_TOOL_DISPLAY = {
            "facts_list_modules":   "加载模块清单",
            "facts_get_module":     "加载模块事实主档",
            "prototypes_list_pages": "加载原型页面清单",
            "prototypes_get_page":   "加载原型页面详情",
            "get_current_draft":    "加载已有草稿",
            "docs_list_saved":      "查询历史文档",
            "docs_load_saved":      "加载历史版本",
            "skill_list_resources": "列出 Skill 资源",
            "skill_read_resource":  "读取 Skill 资源",
            "skill_run_script":     "执行 Skill 脚本",
            "write_document":       "生成文档内容",
            "ask_user":             "向用户确认",
            "thought":              "兼容本地模型误调用",
        }

        # 通知前端 Sub-agent 开始执行（显示在可观测面板）
        await ctx.ws_sender({
            "type": "subagent_start",
            "skill_id": skill_id,
            "skill_name": skill.name,
        })
        await emit_execution_event(
            ctx,
            execution_id=execution_id,
            parent_execution_id=ctx.orchestrator_execution_id,
            actor=ExecutionActor.SUBAGENT,
            phase=ExecutionPhase.DELEGATE,
            name="skill_started",
            status=ExecutionEventStatus.STARTED,
            display_text=f"子 Agent 开始执行：{skill.name}",
            data={"skill_id": skill_id, "skill_name": skill.name},
        )

        # 运行 Sub-agent，将执行步骤实时转发给前端（可观测面板）
        reflection_buffer = ""
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
                    await close_active_thought(sub_ctx, status=ExecutionNodeStatus.COMPLETED)
                    for fc in func_calls:
                        tool_name = fc.name
                        label = _SUBAGENT_TOOL_DISPLAY.get(tool_name, f"调用：{tool_name}")
                        logger.info(f"subagent tool_call: {tool_name}")
                        phase = ExecutionPhase.RESOURCE
                        if tool_name == "write_document":
                            phase = ExecutionPhase.WRITE
                        elif tool_name == "ask_user":
                            phase = ExecutionPhase.CLARIFICATION
                        tool_node = await start_tool_node(
                            sub_ctx,
                            execution_id=execution_id,
                            actor=ExecutionActor.SUBAGENT,
                            tool_name=tool_name,
                            title=label,
                            params=fc.args or {},
                            parent_node_id=sub_ctx.current_skill_node_id,
                            skill_id=skill_id,
                        )
                        await emit_execution_event(
                            ctx,
                            execution_id=execution_id,
                            parent_execution_id=ctx.orchestrator_execution_id,
                            actor=ExecutionActor.SUBAGENT,
                            phase=phase,
                            name=tool_name,
                            status=ExecutionEventStatus.STARTED,
                            display_text=label,
                            data={
                                "tool": tool_name,
                                "node_id": tool_node.node_id,
                                "parent_node_id": sub_ctx.current_skill_node_id,
                            },
                        )
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
                    if sub_ctx.draft_updated:
                        _delta, reflection_buffer = _compute_stream_delta(
                            reflection_buffer,
                            event_text,
                        )
                    else:
                        await append_thought(
                            sub_ctx,
                            content=event_text,
                            actor=ExecutionActor.SUBAGENT,
                            parent_node_id=sub_ctx.current_skill_node_id,
                        )
                        await ctx.ws_sender({"type": "thinking", "content": event_text})

                # 捕获 Sub-agent 最终响应文本（写作完成总结）
                if event.is_final_response() and event.content:
                    final_text = _extract_text_from_event(event)
                    if sub_ctx.draft_updated and final_text.strip():
                        _delta, reflection_buffer = _compute_stream_delta(
                            reflection_buffer,
                            final_text,
                        )
                    else:
                        reflection_buffer = final_text

        except Exception as e:
            logger.error(
                f"execute_skill: Sub-agent 运行出错 skill_id={skill_id}: {e}",
                exc_info=True,
            )
            failure = SkillExecutionFailure(
                type="subagent_runtime_error",
                message=str(e),
                stage="subagent_run",
            )
            ctx.latest_skill_execution_result = SkillExecutionResult(
                execution_id=execution_id,
                skill_id=skill_id,
                status=SkillExecutionStatus.FAILED,
                summary=f"Skill 执行出错：{str(e)}",
                failure=failure,
                retryable=True,
            )
            tool_context.state["latest_skill_execution_result"] = (
                ctx.latest_skill_execution_result.model_dump(mode="json")
            )
            await emit_execution_event(
                ctx,
                execution_id=execution_id,
                parent_execution_id=ctx.orchestrator_execution_id,
                actor=ExecutionActor.SUBAGENT,
                phase=ExecutionPhase.COMPLETE,
                name="skill_failed",
                status=ExecutionEventStatus.FAILED,
                display_text=f"子 Agent 执行失败：{str(e)}",
                data={
                    "skill_id": skill_id,
                    "error": str(e),
                    "node_id": ctx.current_skill_node_id,
                    "parent_node_id": None,
                },
            )
            if ctx.current_skill_node_id:
                await update_execution_node(
                    ctx,
                    ctx.current_skill_node_id,
                    status=ExecutionNodeStatus.FAILED,
                    output_preview=f"Skill 执行失败：{str(e)}",
                    output_detail=str(e),
                )
            await create_system_state_node(
                ctx,
                title=f"Skill 执行失败：{skill.name}",
                status=ExecutionNodeStatus.FAILED,
                actor=ExecutionActor.SUBAGENT,
                parent_node_id=ctx.current_skill_node_id,
                metadata={"skill_id": skill_id},
            )
            ctx.current_skill_node_id = None
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
            if subagent_session and _merge_subagent_state_into_parent(
                ctx,
                tool_context.state,
                subagent_session.state,
                skill_id,
            ):
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
                    await create_execution_node(
                        ctx,
                        node_type=ExecutionNodeType.SYSTEM_STATE,
                        title="写作摘要",
                        status=ExecutionNodeStatus.COMPLETED,
                        actor=ExecutionActor.SUBAGENT,
                        parent_node_id=ctx.current_skill_node_id,
                        output_preview="写作摘要已生成",
                        output_detail=compact_summary,
                        detail_text=compact_summary,
                        metadata={"skill_id": skill_id, "kind": "summary"},
                    )
                else:
                    await create_execution_node(
                        ctx,
                        node_type=ExecutionNodeType.SYSTEM_STATE,
                        title="写作摘要",
                        status=ExecutionNodeStatus.COMPLETED,
                        actor=ExecutionActor.SUBAGENT,
                        parent_node_id=ctx.current_skill_node_id,
                        output_preview="未生成额外写作摘要",
                        output_detail="",
                        detail_text="",
                        metadata={"skill_id": skill_id, "kind": "summary"},
                    )
        except Exception as e:
            logger.warning(f"execute_skill: 生成压缩摘要失败 skill_id={skill_id}: {e}")
            await create_execution_node(
                ctx,
                node_type=ExecutionNodeType.SYSTEM_STATE,
                title="写作摘要",
                status=ExecutionNodeStatus.FAILED,
                actor=ExecutionActor.SUBAGENT,
                parent_node_id=ctx.current_skill_node_id,
                output_preview="写作摘要生成失败",
                output_detail=str(e),
                detail_text=str(e),
                metadata={"skill_id": skill_id, "kind": "summary"},
            )

        # 将压缩摘要写入 ctx，供后续轮次的 Sub-agent / 主 Agent 参考
        summary = compact_summary.strip() or reflection_text or f"Skill {skill_id} 执行完成"
        ctx.last_skill_execution_summary = summary
        ctx.latest_skill_execution_result = SkillExecutionResult(
            execution_id=execution_id,
            skill_id=skill_id,
            status=SkillExecutionStatus.COMPLETED,
            summary=summary,
            retryable=False,
        )
        tool_context.state["latest_skill_execution_result"] = (
            ctx.latest_skill_execution_result.model_dump(mode="json")
        )
        await emit_execution_event(
            ctx,
            execution_id=execution_id,
            parent_execution_id=ctx.orchestrator_execution_id,
            actor=ExecutionActor.SUBAGENT,
            phase=ExecutionPhase.COMPLETE,
            name="skill_completed",
            status=ExecutionEventStatus.COMPLETED,
            display_text=f"子 Agent 执行完成：{skill.name}",
            data={
                "skill_id": skill_id,
                "draft_updated": sub_ctx.draft_updated,
                "node_id": ctx.current_skill_node_id,
                "parent_node_id": None,
            },
        )
        if ctx.current_skill_node_id:
            await update_execution_node(
                ctx,
                ctx.current_skill_node_id,
                status=ExecutionNodeStatus.COMPLETED,
                output_preview=f"Skill 执行完成：{skill.name}",
                output_detail=summary,
                metadata_updates={"draft_updated": sub_ctx.draft_updated},
            )
        sub_ctx.execution_node_order = max(sub_ctx.execution_node_order, ctx.execution_node_order)
        ctx.execution_node_order = sub_ctx.execution_node_order
        ctx.current_skill_node_id = None

        logger.info(
            f"execute_skill: 完成 skill_id={skill_id}, 摘要长度={len(summary)}"
        )
        return summary

    return execute_skill
