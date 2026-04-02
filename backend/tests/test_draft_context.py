import asyncio
from types import SimpleNamespace

from agent.adk.draft_tool import create_get_current_draft_tool
from agent.adk.execute_skill_tool import _build_subagent_input


class _DummyConversationManager:
    async def get_conversation(self, conversation_id):
        return None


def test_get_current_draft_restores_module_identity_from_session_state():
    ctx = SimpleNamespace(
        conversation_id="conv-1",
        conversation_manager=_DummyConversationManager(),
        loaded_base_draft=None,
        loaded_base_doc_name=None,
        loaded_base_module_id=None,
        current_module_id=None,
        current_module_name=None,
    )
    tool = create_get_current_draft_tool(ctx)
    tool_context = SimpleNamespace(
        state={
            "draft_content": "# 脆弱性管理模块用户手册\n\n## 1. 概述",
            "module_name": "脆弱性管理",
            "module_id": "mod-ce9f97011132",
        }
    )

    summary = asyncio.run(tool(tool_context))

    assert "已加载草稿" in summary
    assert ctx.loaded_base_draft.startswith("# 脆弱性管理模块用户手册")
    assert ctx.loaded_base_doc_name == "脆弱性管理"
    assert ctx.loaded_base_module_id == "mod-ce9f97011132"
    assert ctx.current_module_name == "脆弱性管理"
    assert ctx.current_module_id == "mod-ce9f97011132"


def test_build_subagent_input_includes_current_draft_target_hint():
    ctx = SimpleNamespace(
        conversation_has_draft=True,
        loaded_base_doc_name=None,
        current_module_name="脆弱性管理",
        loaded_base_module_id=None,
        current_module_id="mod-ce9f97011132",
        current_system_name="业务保障管理系统",
        current_subsystem_name="资产脆弱性管理",
        loaded_base_draft=None,
        last_skill_execution_summary=None,
    )

    content = _build_subagent_input("删除风险提示章节和常见问题与处理章节", ctx)

    assert "先调用 get_current_draft" in content
    assert "业务保障管理系统 / 资产脆弱性管理 / 脆弱性管理 (mod-ce9f97011132)" in content
    assert "不要重新做模块消歧" in content
