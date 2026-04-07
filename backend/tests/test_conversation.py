"""
单元测试 - 对话管理
"""
from unittest.mock import patch

import pytest


@pytest.fixture
def conv_dir(tmp_path):
    return tmp_path / "conversations"


@pytest.fixture
def manager(conv_dir):
    from agent.conversation import ConversationManager
    ConversationManager._instance = None  # Reset singleton
    with patch("agent.conversation.CONVERSATIONS_DIR", conv_dir):
        mgr = ConversationManager()
        conv_dir.mkdir(parents=True, exist_ok=True)
        return mgr


@pytest.mark.asyncio
async def test_create_conversation(manager):
    """测试创建对话"""
    conv = await manager.create_conversation(name="测试对话")
    assert conv.id is not None
    assert conv.name == "测试对话"
    assert conv.rounds == []


@pytest.mark.asyncio
async def test_add_round(manager):
    """测试添加对话轮次"""
    conv = await manager.create_conversation()
    success = await manager.add_round(
        conv.id,
        user_input="用户输入",
        agent_response="Agent响应",
    )
    assert success is True

    loaded = await manager.get_conversation(conv.id)
    assert len(loaded.rounds) == 1
    assert loaded.rounds[0].user_input == "用户输入"


@pytest.mark.asyncio
async def test_multi_round_conversation(manager):
    """测试多轮对话"""
    conv = await manager.create_conversation()
    for i in range(3):
        await manager.add_round(conv.id, f"用户输入{i}", f"响应{i}")

    loaded = await manager.get_conversation(conv.id)
    assert len(loaded.rounds) == 3


@pytest.mark.asyncio
async def test_conversation_persistence(manager, conv_dir):
    """测试对话持久化"""
    conv = await manager.create_conversation(name="持久化测试")
    await manager.add_round(conv.id, "输入", "响应")

    # 清除内存缓存，模拟重启
    manager._conversations.clear()

    loaded = await manager.get_conversation(conv.id)
    assert loaded is not None
    assert loaded.name == "持久化测试"
    assert len(loaded.rounds) == 1


@pytest.mark.asyncio
async def test_list_conversations(manager):
    """测试列出对话"""
    await manager.create_conversation(name="对话A")
    await manager.create_conversation(name="对话B")

    convs = await manager.list_conversations()
    assert len(convs) >= 2


@pytest.mark.asyncio
async def test_delete_conversation(manager):
    """测试删除对话"""
    conv = await manager.create_conversation()
    result = await manager.delete_conversation(conv.id)
    assert result is True

    loaded = await manager.get_conversation(conv.id)
    assert loaded is None


@pytest.mark.asyncio
async def test_add_round_to_nonexistent_conversation(manager):
    """测试向不存在的对话添加轮次"""
    result = await manager.add_round(
        "nonexistent-id", "输入", "响应"
    )
    assert result is False


@pytest.mark.asyncio
async def test_add_round_persists_structured_execution_payload(manager):
    from agent.models import ExecutionActor, ExecutionEventStatus, ExecutionPhase

    conv = await manager.create_conversation()
    success = await manager.add_round(
        conv.id,
        user_input="编写资产管理用户手册",
        agent_response="# 资产管理用户手册",
        skill_invoked="write-user-manual",
        skill_execution={
            "execution_id": "skill-1",
            "skill_id": "write-user-manual",
            "status": "completed",
            "summary": "已完成用户手册初稿",
            "retryable": False,
        },
        execution_events=[
            {
                "execution_id": "main-1",
                "actor": "orchestrator",
                "phase": "plan",
                "name": "orchestrator_run",
                "status": "started",
                "display_text": "开始规划本轮处理路径",
            }
        ],
        state_snapshot={"writing_state": {"module_name": "资产管理", "has_draft": True}},
    )

    assert success is True
    loaded = await manager.get_conversation(conv.id)
    round_data = loaded.rounds[0]
    assert round_data.skill_execution is not None
    assert round_data.skill_execution.skill_id == "write-user-manual"
    assert round_data.execution_events[0].phase == ExecutionPhase.PLAN
    assert round_data.execution_events[0].actor == ExecutionActor.ORCHESTRATOR
    assert round_data.execution_events[0].status == ExecutionEventStatus.STARTED
    assert round_data.state_snapshot["writing_state"]["has_draft"] is True
