"""
Runner 适配层 - 将 ADK Runner 事件流转换为 WebSocket 消息格式。

管理 ConversationContext（持有 ws_sender、user_input_queue 等），
以及进程级 SessionEntry 注册表（跨轮复用 session），
实现 stream_message() 接口与现有 AgentCore 保持兼容。

研究结论（ADK 1.27.2）：
- 无原生 Events Compaction API；通过直接操作 session_service.sessions 内部 events 列表实现裁剪
- session.state 写入：工具函数声明 tool_context: ToolContext 参数，ADK 自动注入；
  写入 tool_context.state["key"] = value，读取调用 session_service.get_session() 后 session.state.get("key")
- 工具返回值可以是任意字符串，直接作为 FunctionResponse 写入 session 历史
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Tuple

from agent.models import (
    ExecutionActor,
    ExecutionEvent,
    ExecutionEventStatus,
    ExecutionNodeStatus,
    ExecutionNodeType,
    ExecutionObjectNode,
    ExecutionPhase,
    SkillExecutionResult,
    ToolSourceType,
)

try:
    from google.adk.agents.run_config import RunConfig, StreamingMode
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
except ModuleNotFoundError:  # pragma: no cover - fallback for unit tests
    class RunConfig:  # type: ignore[override]
        def __init__(self, *args, **kwargs):
            pass

    class StreamingMode:  # type: ignore[override]
        SSE = "SSE"

    class Runner:  # type: ignore[override]
        def __init__(self, *args, **kwargs):
            pass

    class InMemorySessionService:  # type: ignore[override]
        def __init__(self, *args, **kwargs):
            self.sessions = {}

        async def create_session(self, *args, **kwargs):
            return None

        async def get_session(self, *args, **kwargs):
            return None

    class _TypesFallback:  # pragma: no cover - simple namespace for tests
        class Content:
            def __init__(self, role=None, parts=None):
                self.role = role
                self.parts = parts or []

        class Part:
            def __init__(self, text=None):
                self.text = text

    types = _TypesFallback()

logger = logging.getLogger(__name__)

# ── 压缩策略常量 ─────────────────────────────────────────────────────────────
SESSION_TTL_SECONDS = 4 * 3600          # session 最长闲置时间（4 小时）
COMPRESSION_ROUND_THRESHOLD = 6         # 第二层：超过此轮次触发早期事件裁剪
FORCE_PRUNE_THRESHOLD = 15              # 第三层：超过此轮次强制保留最近 N 轮
FORCE_PRUNE_KEEP_ROUNDS = 8             # 第三层：强制裁剪后保留的轮数

DISPLAY_INPUT_BUDGET = 500
OUTPUT_PREVIEW_BUDGET = 800
OUTPUT_DETAIL_BUDGET = 2400
THOUGHT_DETAIL_BUDGET = 3200

# ── 全局活跃上下文表：conversation_id → ConversationContext ─────────────────
# 用于 ask_user 场景下：用户回复直接投入等待中的队列
_active_contexts: Dict[str, "ConversationContext"] = {}


# ── Session 注册表 ───────────────────────────────────────────────────────────

@dataclass
class SessionEntry:
    """进程级 session 注册表条目，跨轮持久持有 ADK session 基础设施。

    注意：agent 和 runner 每轮重建（因为工具闭包捕获 per-round ConversationContext），
    session_service 跨轮共享（持有 events 和 state 历史）。
    """
    session_service: InMemorySessionService
    session_id: str
    user_id: str
    last_active_at: float = field(default_factory=time.time)
    round_count: int = 0
    last_skill_execution_summary: Optional[str] = None
    clarification_context: List[str] = field(default_factory=list)


# conversation_id → SessionEntry
_session_registry: Dict[str, SessionEntry] = {}


def _format_stream_error(error: Exception) -> str:
    """Convert raw provider errors into user-facing messages."""
    raw = str(error).strip() or error.__class__.__name__
    lowered = raw.lower()

    if "ollama" in lowered and ("cannot connect" in lowered or "no route to host" in lowered):
        return (
            "无法连接到本地模型服务。请检查 Ollama 服务是否已启动、"
            "IP/端口是否正确，以及当前机器能否访问该地址。"
        )

    if "all connection attempts failed" in lowered or "cannot connect" in lowered:
        return f"模型服务连接失败：{raw}"

    return f"处理出错：{raw}"


def _extract_text_from_content(content: Any) -> str:
    """Flatten ADK content parts into plain text."""
    if not content:
        return ""
    chunks: List[str] = []
    for part in content.parts or []:
        text = getattr(part, "text", None)
        if text:
            chunks.append(text)
    return "".join(chunks)


def _compute_stream_delta(previous_text: str, incoming_text: str) -> tuple[str, str]:
    """Normalize streaming payloads that may be cumulative or delta-based.

    Some providers stream "full text so far", while others stream only the latest
    delta. This helper returns the newly appended delta and the updated buffer.
    """
    if not incoming_text:
        return "", previous_text

    if incoming_text.startswith(previous_text):
        return incoming_text[len(previous_text):], incoming_text

    if previous_text.endswith(incoming_text):
        return "", previous_text

    return incoming_text, previous_text + incoming_text


def _final_response_channel(
    *,
    draft_updated: bool,
    selected_skill_id: Optional[str],
    prefer_thinking_stream: bool,
) -> str:
    """Choose where the final user-visible answer should be rendered.

    Even if the main agent called a Skill or the request looked like a writing
    task, a round that did not produce/update a draft should still surface its
    final answer in the left chat bubble instead of the thinking panel.
    """
    if draft_updated:
        return "none"
    return "text"


def _looks_like_writing_request(message: str) -> bool:
    """Best-effort heuristic for requests that should delegate to writing flow.

    In writing scenarios, the main agent often emits planning prose before it
    actually calls ``execute_skill``. That prose belongs to the thinking panel,
    not the formal document/output bubble.
    """
    text = (message or "").strip().lower()
    if not text:
        return False

    writing_keywords = (
        "写", "编写", "撰写", "修订", "修改", "润色",
        "文档", "手册", "说明书", "操作指南", "用户指南",
        "需求", "设计", "方案", "接口文档", "技术文档",
        "manual", "document", "doc",
    )
    return any(keyword in text for keyword in writing_keywords)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _with_truncation_suffix(text: str) -> str:
    return text.rstrip() + "\n\n[内容已截断]"


def _normalize_display_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except TypeError:
        return str(value)


def _budget_text(value: Any, *, limit: int) -> Tuple[str, bool]:
    text = _normalize_display_text(value)
    if not text:
        return "", False
    if len(text) <= limit:
        return text, False
    return _with_truncation_suffix(text[:limit].rstrip()), True


def _tool_source(tool_name: str) -> ToolSourceType:
    if tool_name.startswith("skill_") or tool_name.startswith("skill."):
        return ToolSourceType.INTERNAL
    if "." in tool_name:
        return ToolSourceType.MCP
    return ToolSourceType.BUILTIN


def _map_event_status(status: ExecutionEventStatus) -> ExecutionNodeStatus:
    if status == ExecutionEventStatus.COMPLETED:
        return ExecutionNodeStatus.COMPLETED
    if status == ExecutionEventStatus.FAILED:
        return ExecutionNodeStatus.FAILED
    return ExecutionNodeStatus.RUNNING


def _make_node_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _prune_session_events(entry: SessionEntry, keep_rounds: int) -> None:
    """裁剪 session events，只保留最近 keep_rounds 个用户轮次的事件。"""
    sessions_store = entry.session_service.sessions.get("doc_assist", {})
    session_obj = sessions_store.get(entry.user_id, {}).get(entry.session_id)
    if not session_obj or not session_obj.events:
        return

    # 找到所有用户消息事件的下标（每个用户轮次的起点）
    user_turn_indices = [
        i for i, e in enumerate(session_obj.events)
        if getattr(e, "author", None) == "user"
    ]

    if len(user_turn_indices) <= keep_rounds:
        return  # 轮次不足，无需裁剪

    # 从倒数第 keep_rounds 个用户轮次起点开始保留
    cutoff_index = user_turn_indices[-keep_rounds]
    logger.info(
        f"_prune_session_events: 裁剪 session {entry.session_id}，"
        f"保留最近 {keep_rounds} 轮（从事件 {cutoff_index} 开始），"
        f"共 {len(session_obj.events)} → {len(session_obj.events) - cutoff_index} 个事件"
    )
    session_obj.events = session_obj.events[cutoff_index:]


def cleanup_expired_sessions() -> None:
    """清理所有 TTL 过期的 session entry（懒清理，在每次 get_or_create_session 时调用）。"""
    now = time.time()
    expired = [
        cid for cid, entry in _session_registry.items()
        if now - entry.last_active_at > SESSION_TTL_SECONDS
    ]
    for cid in expired:
        del _session_registry[cid]
        logger.info(f"cleanup_expired_sessions: 清理过期 session，conversation_id={cid}")


async def get_or_create_session(
    conversation_id: str,
    force_rebuild: bool = False,
) -> SessionEntry:
    """获取或创建 conversation 对应的 SessionEntry。

    Args:
        conversation_id: 对话 ID。
        force_rebuild: 为 True 时强制销毁旧 entry 并重建（用于 conversation 切换场景）。

    Returns:
        SessionEntry，包含 session_service、session_id、user_id 等。
    """
    cleanup_expired_sessions()

    if force_rebuild:
        _session_registry.pop(conversation_id, None)
        logger.info(f"get_or_create_session: force_rebuild，清除旧 entry conversation_id={conversation_id}")

    if conversation_id in _session_registry:
        entry = _session_registry[conversation_id]
        entry.last_active_at = time.time()
        return entry

    # 首次创建
    user_id = f"user_{conversation_id}"
    session_id = f"session_{conversation_id}"
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="doc_assist",
        user_id=user_id,
        session_id=session_id,
    )

    entry = SessionEntry(
        session_service=session_service,
        session_id=session_id,
        user_id=user_id,
    )
    _session_registry[conversation_id] = entry
    logger.info(f"get_or_create_session: 新建 session，conversation_id={conversation_id}, session_id={session_id}")
    return entry


def remove_session(conversation_id: str) -> None:
    """从注册表中移除 session entry（conversation 删除时调用）。"""
    if conversation_id in _session_registry:
        del _session_registry[conversation_id]
        logger.info(f"remove_session: 已移除 session，conversation_id={conversation_id}")


# ── ConversationContext（per-round）──────────────────────────────────────────

@dataclass
class ConversationContext:
    """单次 Agent 运行的对话上下文，被所有工具共享。每轮 stream_message 新建一个实例。"""

    conversation_id: str
    ws_sender: Callable  # async (dict) -> None
    conversation_manager: Any  # ConversationManager 实例
    orchestrator_execution_id: str = field(default_factory=lambda: f"main-{uuid.uuid4().hex}")
    current_execution_id: Optional[str] = None

    # ask_user 机制：工具 await 此队列，WebSocket handler 将用户回复 put 进来
    user_input_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    waiting_for_user: bool = False

    # 本轮运行中积累的元数据
    selected_skill_id: Optional[str] = None
    selected_skill_name: Optional[str] = None
    skill_reason: Optional[str] = None
    draft_updated: bool = False
    llm_usage: Optional[dict] = None
    latest_skill_execution_result: Optional[SkillExecutionResult] = None
    execution_events: List[ExecutionEvent] = field(default_factory=list)
    execution_nodes: List[ExecutionObjectNode] = field(default_factory=list)
    execution_node_index: Dict[str, ExecutionObjectNode] = field(default_factory=dict)
    execution_node_order: int = 0
    open_tool_nodes: Dict[str, List[str]] = field(default_factory=dict)
    active_thought_node_id: Optional[str] = None
    current_skill_node_id: Optional[str] = None
    current_question_node_id: Optional[str] = None
    clarification_context: List[str] = field(default_factory=list)

    # legacy facts 累积（per-round）：保留给旧工具路径的兼容回退。
    # 正常 MCP 模式下由 loaded_facts_parts / loaded_skill_resource_parts / loaded_docs_parts 承担写作上下文注入。
    # 不跨轮累积——每轮 stream_message 创建新实例时自动清零。
    collected_facts_parts: List[str] = field(default_factory=list)

    # MCP working context（per-round）：按来源分层记录显式读取的运行时资源。
    loaded_facts_parts: List[str] = field(default_factory=list)
    loaded_skill_resource_parts: List[str] = field(default_factory=list)
    loaded_docs_parts: List[str] = field(default_factory=list)

    # 历史已保存文档正文（per-round）：`docs.load_saved` / `get_current_draft` 写入，write_document 按需读取。
    # context 参数优先；context 为空时使用此字段作为草稿基础。
    # 不跨轮持久化——每轮创建新实例时自动清零。
    loaded_base_draft: Optional[str] = None

    # 历史文档来源标识（per-round）：`docs.load_saved` 写入。
    # write_document 保存时优先用此 doc_name，确保修改后继续追加版本而非创建新文档目录。
    loaded_base_doc_name: Optional[str] = None

    # 当前草稿对应的稳定模块标识（per-round）：从事实工具解析或 get_current_draft 恢复。
    # write_document 保存时会将其写回 session.state，供后续轮次继续沿用。
    loaded_base_module_id: Optional[str] = None

    # 当前对话已知的写作目标（per-round）：用于修改场景下跨轮延续上下文，
    # 避免用户仅说“删掉这一章”时再次触发模块消歧。
    current_module_id: Optional[str] = None
    current_module_name: Optional[str] = None
    current_system_name: Optional[str] = None
    current_subsystem_name: Optional[str] = None
    conversation_has_draft: bool = False

    # 上次 Skill 执行摘要（跨轮传递）：execute_skill 写入，供后续轮次 Sub-agent 注入上下文。
    # stream_message 在每轮创建新 ctx 后，从上一轮 ctx 拷贝此字段实现跨轮传递。
    last_skill_execution_summary: Optional[str] = None


def get_active_context(conversation_id: str) -> Optional[ConversationContext]:
    """获取指定对话的活跃上下文（供 WebSocket handler 投递用户回复）。"""
    return _active_contexts.get(conversation_id)


def _tool_stack_key(
    execution_id: Optional[str],
    tool_name: str,
    parent_node_id: Optional[str],
) -> str:
    canonical_name = str(tool_name or "").replace(".", "_")
    return "::".join([execution_id or "root", parent_node_id or "top", canonical_name])


async def _send_trace_node(ctx: ConversationContext, node: ExecutionObjectNode) -> None:
    await ctx.ws_sender(
        {
            "type": "trace_node",
            "node": node.model_dump(mode="json"),
        }
    )


def _next_created_order(ctx: ConversationContext) -> int:
    ctx.execution_node_order += 1
    return ctx.execution_node_order


async def create_execution_node(
    ctx: ConversationContext,
    *,
    node_type: ExecutionNodeType,
    title: str,
    status: ExecutionNodeStatus,
    actor: ExecutionActor,
    parent_node_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    tool_name: Optional[str] = None,
    tool_source: Optional[ToolSourceType] = None,
    skill_id: Optional[str] = None,
    skill_name: Optional[str] = None,
    reason: Optional[str] = None,
    display_input: str = "",
    output_preview: str = "",
    output_detail: str = "",
    detail_text: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    truncated_fields: Optional[List[str]] = None,
) -> ExecutionObjectNode:
    now = _now()
    node = ExecutionObjectNode(
        node_id=_make_node_id(node_type.value),
        node_type=node_type,
        title=title,
        status=status,
        actor=actor,
        parent_node_id=parent_node_id,
        execution_id=execution_id,
        tool_name=tool_name,
        tool_source=tool_source,
        skill_id=skill_id,
        skill_name=skill_name,
        reason=reason,
        display_input=display_input,
        output_preview=output_preview,
        output_detail=output_detail,
        detail_text=detail_text,
        metadata=metadata or {},
        created_at=now,
        updated_at=now,
        created_order=_next_created_order(ctx),
        truncated_fields=list(truncated_fields or []),
        is_truncated=bool(truncated_fields),
    )
    ctx.execution_nodes.append(node)
    ctx.execution_node_index[node.node_id] = node
    await _send_trace_node(ctx, node)
    return node


async def update_execution_node(
    ctx: ConversationContext,
    node_id: str,
    *,
    title: Optional[str] = None,
    status: Optional[ExecutionNodeStatus] = None,
    reason: Optional[str] = None,
    display_input: Optional[str] = None,
    output_preview: Optional[str] = None,
    output_detail: Optional[str] = None,
    detail_text: Optional[str] = None,
    metadata_updates: Optional[Dict[str, Any]] = None,
    append_detail_text: Optional[str] = None,
    append_output_detail: Optional[str] = None,
    truncated_fields: Optional[List[str]] = None,
) -> Optional[ExecutionObjectNode]:
    node = ctx.execution_node_index.get(node_id)
    if node is None:
        return None

    if title is not None:
        node.title = title
    if status is not None:
        node.status = status
    if reason is not None:
        node.reason = reason
    if display_input is not None:
        node.display_input = display_input
    if output_preview is not None:
        node.output_preview = output_preview
    if output_detail is not None:
        node.output_detail = output_detail
    if detail_text is not None:
        node.detail_text = detail_text
    if append_detail_text:
        node.detail_text = (node.detail_text or "") + append_detail_text
    if append_output_detail:
        node.output_detail = (node.output_detail or "") + append_output_detail
    if metadata_updates:
        node.metadata = {**node.metadata, **metadata_updates}
    if truncated_fields is not None:
        merged = sorted(set([*node.truncated_fields, *truncated_fields]))
        node.truncated_fields = merged
        node.is_truncated = bool(merged)
    node.updated_at = _now()
    await _send_trace_node(ctx, node)
    return node


def _tool_parent_node_id(ctx: ConversationContext) -> Optional[str]:
    return ctx.current_skill_node_id


async def start_tool_node(
    ctx: ConversationContext,
    *,
    execution_id: Optional[str],
    actor: ExecutionActor,
    tool_name: str,
    title: str,
    params: Optional[Dict[str, Any]] = None,
    parent_node_id: Optional[str] = None,
    skill_id: Optional[str] = None,
) -> ExecutionObjectNode:
    display_input, input_truncated = _budget_text(params or {}, limit=DISPLAY_INPUT_BUDGET)
    truncated_fields = ["display_input"] if input_truncated else []
    node = await create_execution_node(
        ctx,
        node_type=ExecutionNodeType.TOOL_CALL,
        title=title,
        status=ExecutionNodeStatus.RUNNING,
        actor=actor,
        parent_node_id=parent_node_id,
        execution_id=execution_id,
        tool_name=tool_name,
        tool_source=_tool_source(tool_name),
        skill_id=skill_id,
        display_input=display_input,
        output_preview="",
        output_detail="",
        metadata={"tool_name": tool_name},
        truncated_fields=truncated_fields,
    )
    stack_key = _tool_stack_key(execution_id, tool_name, parent_node_id)
    ctx.open_tool_nodes.setdefault(stack_key, []).append(node.node_id)
    return node


def _find_open_tool_node_id(
    ctx: ConversationContext,
    *,
    execution_id: Optional[str],
    tool_name: str,
    parent_node_id: Optional[str],
) -> Optional[str]:
    stack_key = _tool_stack_key(execution_id, tool_name, parent_node_id)
    stack = ctx.open_tool_nodes.get(stack_key) or []
    return stack[-1] if stack else None


async def complete_tool_node(
    ctx: ConversationContext,
    *,
    execution_id: Optional[str],
    tool_name: str,
    parent_node_id: Optional[str],
    status: ExecutionNodeStatus,
    output_preview: Any,
    output_detail: Any,
    metadata_updates: Optional[Dict[str, Any]] = None,
) -> Optional[ExecutionObjectNode]:
    node_id = _find_open_tool_node_id(
        ctx,
        execution_id=execution_id,
        tool_name=tool_name,
        parent_node_id=parent_node_id,
    )
    if not node_id:
        return None

    preview_text, preview_truncated = _budget_text(output_preview, limit=OUTPUT_PREVIEW_BUDGET)
    detail_text, detail_truncated = _budget_text(output_detail, limit=OUTPUT_DETAIL_BUDGET)
    truncated_fields = []
    if preview_truncated:
        truncated_fields.append("output_preview")
    if detail_truncated:
        truncated_fields.append("output_detail")
    node = await update_execution_node(
        ctx,
        node_id,
        status=status,
        output_preview=preview_text,
        output_detail=detail_text,
        metadata_updates=metadata_updates,
        truncated_fields=truncated_fields,
    )

    stack_key = _tool_stack_key(execution_id, tool_name, parent_node_id)
    stack = ctx.open_tool_nodes.get(stack_key) or []
    if stack and stack[-1] == node_id:
        stack.pop()
    return node


async def append_tool_detail(
    ctx: ConversationContext,
    *,
    execution_id: Optional[str],
    tool_name: str,
    parent_node_id: Optional[str],
    detail: Any,
) -> Optional[ExecutionObjectNode]:
    node_id = _find_open_tool_node_id(
        ctx,
        execution_id=execution_id,
        tool_name=tool_name,
        parent_node_id=parent_node_id,
    )
    if not node_id:
        return None

    node = ctx.execution_node_index.get(node_id)
    if node is None:
        return None
    merged_detail = "\n\n".join(part for part in [node.output_detail, _normalize_display_text(detail)] if part)
    budgeted_detail, detail_truncated = _budget_text(merged_detail, limit=OUTPUT_DETAIL_BUDGET)
    truncated_fields = ["output_detail"] if detail_truncated else []
    return await update_execution_node(
        ctx,
        node_id,
        output_detail=budgeted_detail,
        truncated_fields=truncated_fields,
    )


async def ensure_thought_node(
    ctx: ConversationContext,
    *,
    actor: ExecutionActor,
    parent_node_id: Optional[str],
) -> ExecutionObjectNode:
    if ctx.active_thought_node_id and ctx.active_thought_node_id in ctx.execution_node_index:
        node = ctx.execution_node_index[ctx.active_thought_node_id]
        if node.parent_node_id == parent_node_id and node.actor == actor:
            return node

    node = await create_execution_node(
        ctx,
        node_type=ExecutionNodeType.LLM_THOUGHT,
        title="LLM 思考",
        status=ExecutionNodeStatus.RUNNING,
        actor=actor,
        parent_node_id=parent_node_id,
        detail_text="",
        output_detail="",
    )
    ctx.active_thought_node_id = node.node_id
    return node


async def append_thought(
    ctx: ConversationContext,
    *,
    content: str,
    actor: ExecutionActor,
    parent_node_id: Optional[str],
) -> None:
    node = await ensure_thought_node(ctx, actor=actor, parent_node_id=parent_node_id)
    merged = (node.detail_text or "") + content
    budgeted, truncated = _budget_text(merged, limit=THOUGHT_DETAIL_BUDGET)
    await update_execution_node(
        ctx,
        node.node_id,
        detail_text=budgeted,
        output_detail=budgeted,
        truncated_fields=["detail_text", "output_detail"] if truncated else [],
    )


async def close_active_thought(ctx: ConversationContext, *, status: ExecutionNodeStatus) -> None:
    node_id = ctx.active_thought_node_id
    if not node_id:
        return
    await update_execution_node(ctx, node_id, status=status)
    ctx.active_thought_node_id = None


async def flush_buffered_thought(
    ctx: ConversationContext,
    *,
    content: str,
    actor: ExecutionActor,
    parent_node_id: Optional[str],
) -> None:
    if not (content or "").strip():
        return
    await append_thought(
        ctx,
        content=content,
        actor=actor,
        parent_node_id=parent_node_id,
    )
    await close_active_thought(ctx, status=ExecutionNodeStatus.COMPLETED)


async def create_system_state_node(
    ctx: ConversationContext,
    *,
    title: str,
    status: ExecutionNodeStatus,
    actor: ExecutionActor,
    parent_node_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> ExecutionObjectNode:
    return await create_execution_node(
        ctx,
        node_type=ExecutionNodeType.SYSTEM_STATE,
        title=title,
        status=status,
        actor=actor,
        parent_node_id=parent_node_id,
        detail_text=title,
        metadata=metadata,
    )


async def create_question_node(
    ctx: ConversationContext,
    *,
    question: str,
    actor: ExecutionActor,
    parent_node_id: Optional[str] = None,
) -> ExecutionObjectNode:
    return await create_execution_node(
        ctx,
        node_type=ExecutionNodeType.USER_QUESTION,
        title="等待用户澄清",
        status=ExecutionNodeStatus.WAITING,
        actor=actor,
        parent_node_id=parent_node_id,
        detail_text=question,
        output_detail=question,
    )


async def create_skill_node(
    ctx: ConversationContext,
    *,
    execution_id: str,
    actor: ExecutionActor,
    skill_id: str,
    skill_name: str,
    reason: str = "",
    parent_node_id: Optional[str] = None,
) -> ExecutionObjectNode:
    budgeted_reason, reason_truncated = _budget_text(reason, limit=DISPLAY_INPUT_BUDGET)
    node = await create_execution_node(
        ctx,
        node_type=ExecutionNodeType.SKILL_CALL,
        title=skill_name or skill_id or "Skill 调用",
        status=ExecutionNodeStatus.RUNNING,
        actor=actor,
        parent_node_id=parent_node_id,
        execution_id=execution_id,
        skill_id=skill_id,
        skill_name=skill_name,
        reason=budgeted_reason,
        display_input=budgeted_reason,
        metadata={"skill_id": skill_id, "skill_name": skill_name},
        truncated_fields=["display_input"] if reason_truncated else [],
    )
    return node


async def emit_execution_event(
    ctx: ConversationContext,
    *,
    execution_id: str,
    actor: ExecutionActor,
    phase: ExecutionPhase,
    name: str,
    status: ExecutionEventStatus,
    display_text: str,
    data: Optional[Dict[str, Any]] = None,
    parent_execution_id: Optional[str] = None,
) -> ExecutionEvent:
    """Record and forward a structured execution-chain event."""
    event = ExecutionEvent(
        execution_id=execution_id,
        actor=actor,
        phase=phase,
        name=name,
        status=status,
        display_text=display_text,
        parent_execution_id=parent_execution_id,
        data=data or {},
    )
    ctx.execution_events.append(event)

    event_data = data or {}
    tool_name = str(event_data.get("tool") or name or "")
    parent_node_id = event_data.get("parent_node_id")

    if tool_name and status in {ExecutionEventStatus.COMPLETED, ExecutionEventStatus.FAILED}:
        await complete_tool_node(
            ctx,
            execution_id=execution_id,
            tool_name=tool_name,
            parent_node_id=parent_node_id or _tool_parent_node_id(ctx),
            status=_map_event_status(status),
            output_preview=event_data.get("output_preview") or display_text,
            output_detail=event_data.get("output_detail") or event_data.get("detail") or display_text,
            metadata_updates=event_data,
        )

    await ctx.ws_sender(
        {
            "type": "execution_event",
            "event": event.model_dump(mode="json"),
        }
    )
    return event


# ── 主入口 ───────────────────────────────────────────────────────────────────

async def stream_message(
    conversation_id: str,
    message: str,
    ws_sender: Callable,
    conversation_manager: Any,
    skill_manager: Any,
    force_rebuild: bool = False,
) -> AsyncIterator[dict]:
    """运行 DocumentAgent 并将 ADK 事件流转换为 WebSocket 消息。

    接口签名与现有 AgentCore.stream_message() 保持兼容。

    Yields:
        dict: WebSocket 消息，type 为 text / status / done / error。
    """
    from agent.adk.document_agent import build_document_agent

    # 获取当前对话草稿状态（ConversationManager 中的持久化草稿）
    try:
        conv = await conversation_manager.get_conversation(conversation_id)
        has_draft = bool(
            conv and conv.writing_state and conv.writing_state.draft_content
        )
        # 是否已保存过正式版本（saved_version 非空表示用户点过"保存"）
        has_saved = bool(
            conv and conv.writing_state and getattr(conv.writing_state, "saved_version", None)
        )
    except Exception:
        has_draft = False
        has_saved = False
        conv = None

    # 获取所有可用 Skill
    skills = await skill_manager.get_all_skills()

    # 获取或创建 session entry（跨轮复用）
    entry = await get_or_create_session(conversation_id, force_rebuild=force_rebuild)

    # 若 session.state 中已有草稿（前几轮写作产生），也视为 has_draft=True
    if not has_draft:
        session = await entry.session_service.get_session(
            app_name="doc_assist", user_id=entry.user_id, session_id=entry.session_id
        )
        if session and session.state.get("draft_content"):
            has_draft = True

    # 若有现有草稿，提前发送状态事件
    if has_draft and conv and conv.writing_state:
        ws_state = conv.writing_state
        label = ws_state.module_name or ws_state.module_id or "文档"
        version_info = f"v{ws_state.saved_version}" if getattr(ws_state, "saved_version", None) else "草稿"
        yield {
            "type": "status",
            "content": f"已加载草稿：{label} {version_info}",
        }

    # 创建本轮的对话上下文（per-round，collected_facts_parts 从空列表开始）
    ctx = ConversationContext(
        conversation_id=conversation_id,
        ws_sender=ws_sender,
        conversation_manager=conversation_manager,
        conversation_has_draft=has_draft,
        last_skill_execution_summary=entry.last_skill_execution_summary,
        clarification_context=list(entry.clarification_context),
    )
    if conv and conv.writing_state:
        ctx.current_module_id = conv.writing_state.module_id or None
        ctx.current_module_name = conv.writing_state.module_name or None
    _active_contexts[conversation_id] = ctx

    try:
        # 本轮重建 agent 和 runner（工具闭包绑定当前 ctx）
        agent = build_document_agent(ctx, skills, has_draft, has_saved)
        runner = Runner(
            agent=agent,
            session_service=entry.session_service,
            app_name="doc_assist",
        )
        streamed_text_buffer = ""
        streamed_thinking_buffer = ""
        buffered_pre_skill_text = ""
        saw_tool_activity = False
        prefer_thinking_stream = _looks_like_writing_request(message)
        await emit_execution_event(
            ctx,
            execution_id=ctx.orchestrator_execution_id,
            actor=ExecutionActor.ORCHESTRATOR,
            phase=ExecutionPhase.PLAN,
            name="orchestrator_run",
            status=ExecutionEventStatus.STARTED,
            display_text="开始规划本轮处理路径",
            data={"message": message},
        )

        # ── 三层压缩策略（第二、三层）─────────────────────────────────────
        # 第二层：超过 COMPRESSION_ROUND_THRESHOLD 轮时裁剪早期事件
        if entry.round_count >= COMPRESSION_ROUND_THRESHOLD:
            keep = max(FORCE_PRUNE_KEEP_ROUNDS, COMPRESSION_ROUND_THRESHOLD)
            _prune_session_events(entry, keep_rounds=keep)

        # 第三层：超过 FORCE_PRUNE_THRESHOLD 轮时强制只保留最近 FORCE_PRUNE_KEEP_ROUNDS 轮
        if entry.round_count >= FORCE_PRUNE_THRESHOLD:
            _prune_session_events(entry, keep_rounds=FORCE_PRUNE_KEEP_ROUNDS)

        start_message = types.Content(
            role="user",
            parts=[types.Part(text=message)],
        )

        # 运行 Agent，映射事件到 WebSocket 消息
        _TOOL_DISPLAY = {
            "facts_list_modules": "查询模块清单",
            "facts_get_module": "加载模块事实主档",
            "prototypes_list_pages": "查询原型页面清单",
            "prototypes_get_page": "加载原型页面详情",
            "docs_list_saved": "查询历史文档",
            "docs_load_saved": "加载历史版本",
            "artifacts_read_file": "读取本地文件",
            "artifacts_write_file": "写入本地文件",
            "execute_skill":     "执行写作 Skill",
            "ask_user":          "向用户确认",
            "thought":           "兼容本地模型误调用",
        }

        async for event in runner.run_async(
            user_id=entry.user_id,
            session_id=entry.session_id,
            new_message=start_message,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        ):
            # --- 工具调用 → status (tool_call) ---
            func_calls = event.get_function_calls()
            if func_calls:
                saw_tool_activity = True
                if buffered_pre_skill_text.strip():
                    await flush_buffered_thought(
                        ctx,
                        content=buffered_pre_skill_text,
                        actor=ExecutionActor.ORCHESTRATOR,
                        parent_node_id=None,
                    )
                    yield {"type": "thinking", "content": buffered_pre_skill_text}
                    streamed_thinking_buffer = ""
                    buffered_pre_skill_text = ""
                await close_active_thought(ctx, status=ExecutionNodeStatus.COMPLETED)
                for fc in func_calls:
                    tool_name = fc.name
                    if tool_name == "execute_skill":
                        skill_id = (fc.args or {}).get("skill_id", "")
                        user_intent = (fc.args or {}).get("user_intent", "")
                        if skill_id:
                            ctx.selected_skill_id = skill_id
                        skill_node = await create_skill_node(
                            ctx,
                            execution_id="",
                            actor=ExecutionActor.ORCHESTRATOR,
                            skill_id=skill_id,
                            skill_name=skill_id or "未命名 Skill",
                            reason=user_intent,
                            parent_node_id=None,
                        )
                        ctx.current_skill_node_id = skill_node.node_id
                        await emit_execution_event(
                            ctx,
                            execution_id=ctx.orchestrator_execution_id,
                            actor=ExecutionActor.ORCHESTRATOR,
                            phase=ExecutionPhase.DELEGATE,
                            name="execute_skill",
                            status=ExecutionEventStatus.STARTED,
                            display_text=f"委派 Skill：{skill_id or '未命名 Skill'}",
                            data={
                                "tool": tool_name,
                                "skill_id": skill_id,
                                "node_id": skill_node.node_id,
                                "parent_node_id": None,
                            },
                        )
                        yield {
                            "type": "skill_start",
                            "skill_id": skill_id,
                            "content": f"技能调用：{skill_id}" if skill_id else "执行写作",
                        }
                    else:
                        tool_node = await start_tool_node(
                            ctx,
                            execution_id=ctx.current_execution_id or ctx.orchestrator_execution_id,
                            actor=ExecutionActor.SUBAGENT if ctx.current_execution_id else ExecutionActor.ORCHESTRATOR,
                            tool_name=tool_name,
                            title=_TOOL_DISPLAY.get(tool_name, f"调用：{tool_name}"),
                            params=fc.args or {},
                            parent_node_id=_tool_parent_node_id(ctx),
                            skill_id=ctx.selected_skill_id,
                        )
                        await emit_execution_event(
                            ctx,
                            execution_id=ctx.orchestrator_execution_id,
                            actor=ExecutionActor.ORCHESTRATOR,
                            phase=ExecutionPhase.RESOURCE,
                            name=tool_name,
                            status=ExecutionEventStatus.STARTED,
                            display_text=_TOOL_DISPLAY.get(tool_name, f"调用：{tool_name}"),
                            data={
                                "tool": tool_name,
                                "node_id": tool_node.node_id,
                                "parent_node_id": _tool_parent_node_id(ctx),
                            },
                        )
                        yield {
                            "type": "status",
                            "sub": "tool_call",
                            "tool": tool_name,
                            "content": _TOOL_DISPLAY.get(tool_name, f"调用：{tool_name}"),
                        }

            # --- 主 Agent 流式文本 → text ---
            # 仅在“普通对话/查询”场景下，将 partial 内容实时输出到左侧消息区。
            # 一旦本轮已经进入写作流程（ctx.draft_updated=True），
            # 后续主 Agent 的收尾总结/压缩摘要不应再混入正文气泡，
            # 因此这里直接忽略主 Agent 的 partial 文本。
            # 对于明确写作场景，主 Agent 的流式段落优先进入 thinking。
            # 普通查询即便用到了事实工具，最终回答仍应走左侧正式正文气泡，
            # 否则会把真正的查询结论错误地吞进思考面板。
            if event.partial and event.content:
                if not ctx.draft_updated:
                    partial_text = _extract_text_from_content(event.content)
                    if prefer_thinking_stream and not ctx.selected_skill_id:
                        _delta, buffered_pre_skill_text = _compute_stream_delta(
                            buffered_pre_skill_text,
                            partial_text,
                        )
                    elif prefer_thinking_stream:
                        delta, streamed_thinking_buffer = _compute_stream_delta(
                            streamed_thinking_buffer,
                            partial_text,
                        )
                        if delta.strip():
                            await append_thought(
                                ctx,
                                content=delta,
                                actor=ExecutionActor.ORCHESTRATOR,
                                parent_node_id=None,
                            )
                            yield {"type": "thinking", "content": delta}
                    else:
                        delta, streamed_text_buffer = _compute_stream_delta(
                            streamed_text_buffer,
                            partial_text,
                        )
                        if delta.strip():
                            yield {"type": "text", "content": delta}

            # --- 错误事件 → error ---
            if event.error_code or event.error_message:
                await create_system_state_node(
                    ctx,
                    title=event.error_message or f"错误码: {event.error_code}",
                    status=ExecutionNodeStatus.FAILED,
                    actor=ExecutionActor.RUNTIME,
                    parent_node_id=None,
                    metadata={"error_code": event.error_code},
                )
                yield {
                    "type": "error",
                    "content": event.error_message or f"错误码: {event.error_code}",
                }

            # --- 最终响应 → done ---
            if event.is_final_response():
                # 提取最终响应文本（纯对话回复场景，无 Skill 写作）
                if not ctx.draft_updated and event.content:
                    final_text = _extract_text_from_content(event.content)
                    final_channel = _final_response_channel(
                        draft_updated=ctx.draft_updated,
                        selected_skill_id=ctx.selected_skill_id,
                        prefer_thinking_stream=prefer_thinking_stream,
                    )
                    if final_channel == "thinking":
                        if buffered_pre_skill_text.strip():
                            await flush_buffered_thought(
                                ctx,
                                content=buffered_pre_skill_text,
                                actor=ExecutionActor.ORCHESTRATOR,
                                parent_node_id=None,
                            )
                            yield {"type": "thinking", "content": buffered_pre_skill_text}
                            streamed_thinking_buffer = ""
                            buffered_pre_skill_text = ""
                        delta, streamed_thinking_buffer = _compute_stream_delta(
                            streamed_thinking_buffer,
                            final_text,
                        )
                        if delta.strip():
                            await append_thought(
                                ctx,
                                content=delta,
                                actor=ExecutionActor.ORCHESTRATOR,
                                parent_node_id=None,
                            )
                            yield {"type": "thinking", "content": delta}
                    elif final_channel == "text":
                        if buffered_pre_skill_text.strip():
                            delta, streamed_text_buffer = _compute_stream_delta(
                                streamed_text_buffer,
                                buffered_pre_skill_text,
                            )
                            if delta.strip():
                                yield {"type": "text", "content": delta}
                            buffered_pre_skill_text = ""
                        delta, streamed_text_buffer = _compute_stream_delta(
                            streamed_text_buffer,
                            final_text,
                        )
                        if delta.strip():
                            yield {"type": "text", "content": delta}

                # 从 session.state 读取写作产物（由 write_document 工具写入）
                session = await entry.session_service.get_session(
                    app_name="doc_assist",
                    user_id=entry.user_id,
                    session_id=entry.session_id,
                )
                state_draft = session.state.get("draft_content") if session else None
                state_skill_id = session.state.get("selected_skill_id") if session else None
                state_module_id = session.state.get("module_id", "") if session else ""
                state_module_name = session.state.get("module_name", "") if session else ""
                state_doc_type = session.state.get("doc_type", "") if session else ""

                # 收集 ADK 级别的 token usage
                adk_usage = None
                if event.usage_metadata:
                    m = event.usage_metadata
                    adk_usage = {
                        "prompt_tokens": getattr(m, "prompt_token_count", 0) or 0,
                        "completion_tokens": getattr(m, "candidates_token_count", 0) or 0,
                        "total_tokens": getattr(m, "total_token_count", 0) or 0,
                    }

                final_usage = ctx.llm_usage or adk_usage
                final_skill_id = state_skill_id or ctx.selected_skill_id

                await close_active_thought(ctx, status=ExecutionNodeStatus.COMPLETED)
                await emit_execution_event(
                    ctx,
                    execution_id=ctx.orchestrator_execution_id,
                    actor=ExecutionActor.ORCHESTRATOR,
                    phase=ExecutionPhase.COMPLETE,
                    name="orchestrator_run",
                    status=ExecutionEventStatus.COMPLETED,
                    display_text="本轮处理完成",
                    data={"skill_id": final_skill_id, "has_draft": ctx.draft_updated},
                )
                await create_system_state_node(
                    ctx,
                    title="本轮处理完成",
                    status=ExecutionNodeStatus.COMPLETED,
                    actor=ExecutionActor.ORCHESTRATOR,
                    metadata={"skill_id": final_skill_id, "has_draft": ctx.draft_updated},
                )
                yield {
                    "type": "done",
                    "skill_id": final_skill_id,
                    "skill_name": ctx.selected_skill_name,
                    "skill_reason": ctx.skill_reason,
                    "usage": final_usage,
                    "has_draft": ctx.draft_updated,
                    "draft_content": state_draft,    # 从 session.state 读取，供 main.py 持久化
                    "writing_state_data": (
                        {
                            "module_id": state_module_id,
                            "module_name": state_module_name,
                            "skill_id": final_skill_id or "",
                            "doc_type": state_doc_type,
                        }
                        if ctx.draft_updated
                        else None
                    ),
                    "writing_state_update": (
                        "draft_only" if (ctx.draft_updated and has_draft) else None
                    ),
                    "skill_execution": (
                        ctx.latest_skill_execution_result.model_dump(mode="json")
                        if ctx.latest_skill_execution_result
                        else None
                    ),
                    "execution_events": [
                        event.model_dump(mode="json")
                        for event in ctx.execution_events
                    ],
                    "execution_nodes": [
                        node.model_dump(mode="json")
                        for node in ctx.execution_nodes
                    ],
                    "state_snapshot": (
                        {
                            "writing_state": {
                                "module_id": state_module_id,
                                "module_name": state_module_name,
                                "skill_id": final_skill_id or "",
                                "doc_type": state_doc_type,
                                "has_draft": bool(state_draft),
                            }
                        }
                        if ctx.draft_updated
                        else None
                    ),
                }

        # 更新轮次计数，并将本轮 Skill 执行摘要持久化到 entry 供下轮使用
        entry.round_count += 1
        entry.last_active_at = time.time()
        if ctx.last_skill_execution_summary:
            entry.last_skill_execution_summary = ctx.last_skill_execution_summary
        entry.clarification_context = list(ctx.clarification_context)

    except Exception as e:
        logger.error(f"stream_message 运行出错: {e}", exc_info=True)
        await close_active_thought(ctx, status=ExecutionNodeStatus.FAILED)
        await emit_execution_event(
            ctx,
            execution_id=ctx.orchestrator_execution_id,
            actor=ExecutionActor.ORCHESTRATOR,
            phase=ExecutionPhase.COMPLETE,
            name="orchestrator_run",
            status=ExecutionEventStatus.FAILED,
            display_text=_format_stream_error(e),
            data={"error": str(e)},
        )
        await create_system_state_node(
            ctx,
            title=_format_stream_error(e),
            status=ExecutionNodeStatus.FAILED,
            actor=ExecutionActor.ORCHESTRATOR,
            metadata={"error": str(e)},
        )
        yield {"type": "error", "content": _format_stream_error(e)}

    finally:
        _active_contexts.pop(conversation_id, None)
