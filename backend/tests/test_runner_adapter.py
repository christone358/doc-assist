import pytest

from agent.adk.execute_skill_tool import _merge_subagent_state_into_parent
from agent.adk.runner_adapter import (
    _compute_stream_delta,
    _extract_text_from_content,
    _final_response_channel,
    _format_stream_error,
    ConversationContext,
    emit_execution_event,
)
from agent.models import ExecutionActor, ExecutionEventStatus, ExecutionPhase


def test_format_stream_error_for_ollama_connectivity():
    err = Exception(
        "litellm.APIConnectionError: OllamaException - Cannot connect to host 192.168.5.162:11434 [No route to host]"
    )

    message = _format_stream_error(err)

    assert "无法连接到本地模型服务" in message
    assert "Ollama" in message


def test_format_stream_error_for_generic_connectivity():
    err = Exception("All connection attempts failed")

    message = _format_stream_error(err)

    assert message.startswith("模型服务连接失败：")


def test_compute_stream_delta_for_cumulative_stream():
    delta, buffer = _compute_stream_delta("", "你好")
    assert delta == "你好"
    assert buffer == "你好"

    delta, buffer = _compute_stream_delta(buffer, "你好，世界")
    assert delta == "，世界"
    assert buffer == "你好，世界"


def test_compute_stream_delta_for_incremental_stream():
    delta, buffer = _compute_stream_delta("", "你好")
    assert delta == "你好"
    assert buffer == "你好"

    delta, buffer = _compute_stream_delta(buffer, "，世界")
    assert delta == "，世界"
    assert buffer == "你好，世界"


def test_compute_stream_delta_ignores_repeated_suffix():
    delta, buffer = _compute_stream_delta("你好，世界", "世界")
    assert delta == ""
    assert buffer == "你好，世界"


def test_final_response_channel_keeps_non_draft_skill_answers_in_bubble():
    channel = _final_response_channel(
        draft_updated=False,
        selected_skill_id="user-manual-writter",
        prefer_thinking_stream=True,
    )

    assert channel == "text"


def test_final_response_channel_suppresses_final_text_when_draft_exists():
    channel = _final_response_channel(
        draft_updated=True,
        selected_skill_id="user-manual-writter",
        prefer_thinking_stream=True,
    )

    assert channel == "none"


def test_extract_text_from_content_joins_parts():
    class Part:
        def __init__(self, text):
            self.text = text

    class Content:
        def __init__(self, parts):
            self.parts = parts

    content = Content([Part("你好"), Part("，"), Part("世界")])

    assert _extract_text_from_content(content) == "你好，世界"


@pytest.mark.asyncio
async def test_emit_execution_event_records_context_and_forwards_payload():
    sent = []

    async def ws_sender(payload):
        sent.append(payload)

    ctx = ConversationContext(
        conversation_id="conv-1",
        ws_sender=ws_sender,
        conversation_manager=object(),
    )

    event = await emit_execution_event(
        ctx,
        execution_id="main-1",
        actor=ExecutionActor.ORCHESTRATOR,
        phase=ExecutionPhase.PLAN,
        name="orchestrator_run",
        status=ExecutionEventStatus.STARTED,
        display_text="开始规划本轮处理路径",
    )

    assert event.execution_id == "main-1"
    assert len(ctx.execution_events) == 1
    assert sent[-1]["type"] == "execution_event"
    assert sent[-1]["event"]["phase"] == "plan"


def test_merge_subagent_state_into_parent_promotes_draft_and_target_metadata():
    ctx = ConversationContext(
        conversation_id="conv-1",
        ws_sender=lambda payload: None,
        conversation_manager=object(),
    )
    tool_state = {}

    merged = _merge_subagent_state_into_parent(
        ctx,
        tool_state,
        {
            "draft_content": "# 文档标题\n\n正文",
            "selected_skill_id": "user-manual-writter",
            "doc_type": "general",
            "module_name": "资产管理",
            "module_id": "mod-asset",
        },
        "fallback-skill",
    )

    assert merged is True
    assert ctx.draft_updated is True
    assert ctx.current_module_name == "资产管理"
    assert ctx.current_module_id == "mod-asset"
    assert tool_state["draft_content"].startswith("# 文档标题")
    assert tool_state["selected_skill_id"] == "user-manual-writter"
    assert tool_state["doc_type"] == "general"
    assert tool_state["module_name"] == "资产管理"
    assert tool_state["module_id"] == "mod-asset"


def test_merge_subagent_state_into_parent_ignores_empty_draft():
    ctx = ConversationContext(
        conversation_id="conv-2",
        ws_sender=lambda payload: None,
        conversation_manager=object(),
    )
    tool_state = {}

    merged = _merge_subagent_state_into_parent(
        ctx,
        tool_state,
        {"module_name": "资产管理"},
        "fallback-skill",
    )

    assert merged is False
    assert ctx.draft_updated is False
    assert tool_state == {}
