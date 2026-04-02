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
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

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

    # ask_user 机制：工具 await 此队列，WebSocket handler 将用户回复 put 进来
    user_input_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    waiting_for_user: bool = False

    # 本轮运行中积累的元数据
    selected_skill_id: Optional[str] = None
    selected_skill_name: Optional[str] = None
    skill_reason: Optional[str] = None
    draft_updated: bool = False
    llm_usage: Optional[dict] = None

    # 事实收集累积（per-round）：get_fact_overview / get_fact_detail 的结果按顺序追加
    # write_document 会自动将这些内容注入到写作上下文中。
    # 不跨轮累积——每轮 stream_message 创建新实例时自动清零。
    collected_facts_parts: List[str] = field(default_factory=list)

    # 历史已保存文档正文（per-round）：load_saved_document / get_current_draft 写入，write_document 按需读取。
    # context 参数优先；context 为空时使用此字段作为草稿基础。
    # 不跨轮持久化——每轮创建新实例时自动清零。
    loaded_base_draft: Optional[str] = None

    # 历史文档来源标识（per-round）：load_saved_document 写入。
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
        saw_tool_activity = False
        prefer_thinking_stream = _looks_like_writing_request(message)

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
            "resolve_target_module": "定位目标模块",
            "load_module_fact_sheet": "加载模块事实主档",
            "get_fact_overview": "查询项目概览",
            "get_fact_detail":   "查询详细信息",
            "execute_skill":     "执行写作 Skill",
            "ask_user":          "向用户确认",
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
                for fc in func_calls:
                    tool_name = fc.name
                    if tool_name == "execute_skill":
                        skill_id = (fc.args or {}).get("skill_id", "")
                        if skill_id:
                            ctx.selected_skill_id = skill_id
                        yield {
                            "type": "skill_start",
                            "skill_id": skill_id,
                            "content": f"技能调用：{skill_id}" if skill_id else "执行写作",
                        }
                    else:
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
                    if prefer_thinking_stream:
                        delta, streamed_thinking_buffer = _compute_stream_delta(
                            streamed_thinking_buffer,
                            partial_text,
                        )
                        if delta.strip():
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
                yield {
                    "type": "error",
                    "content": event.error_message or f"错误码: {event.error_code}",
                }

            # --- 最终响应 → done ---
            if event.is_final_response():
                # 提取最终响应文本（纯对话回复场景，无 Skill 写作）
                if not ctx.draft_updated and event.content:
                    final_text = _extract_text_from_content(event.content)
                    if ctx.selected_skill_id or prefer_thinking_stream:
                        delta, streamed_thinking_buffer = _compute_stream_delta(
                            streamed_thinking_buffer,
                            final_text,
                        )
                        if delta.strip():
                            yield {"type": "thinking", "content": delta}
                    else:
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
                }

        # 更新轮次计数，并将本轮 Skill 执行摘要持久化到 entry 供下轮使用
        entry.round_count += 1
        entry.last_active_at = time.time()
        if ctx.last_skill_execution_summary:
            entry.last_skill_execution_summary = ctx.last_skill_execution_summary

    except Exception as e:
        logger.error(f"stream_message 运行出错: {e}", exc_info=True)
        yield {"type": "error", "content": _format_stream_error(e)}

    finally:
        _active_contexts.pop(conversation_id, None)
