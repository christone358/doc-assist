"""
get_current_draft Tool - 按需加载当前对话的已有草稿。

优先从 ADK session.state["draft_content"] 读取（跨轮持久化草稿），
回退到 ConversationManager 中的 writing_state.draft_content（数据库持久化草稿）。
"""

import logging
from typing import TYPE_CHECKING

try:
    from google.adk.tools import ToolContext
except ModuleNotFoundError:  # pragma: no cover - fallback for unit tests
    class ToolContext:  # type: ignore[override]
        pass

if TYPE_CHECKING:
    from agent.adk.runner_adapter import ConversationContext

logger = logging.getLogger(__name__)


def create_get_current_draft_tool(ctx: "ConversationContext"):
    """创建 get_current_draft 工具函数，捕获对话上下文。"""

    async def get_current_draft(tool_context: ToolContext) -> str:
        """读取当前对话的已有草稿全文。

        当用户发出修改类指令时调用，获取上一轮生成的文档作为修改基础。
        草稿正文存入内部上下文（供 write_document 自动衔接），
        ADK session 历史只记录摘要，避免历史膨胀。

        若当前对话尚无草稿，返回空字符串。

        Returns:
            草稿摘要字符串（如"已加载草稿，共 N 字，可直接调用 write_document(context='') 修改"）；
            草稿正文通过内部上下文传递，不写入此返回值。
        """
        draft = None

        # 优先从 session.state 读取（上一轮 write_document 写入，跨轮即时可见）
        state_draft = tool_context.state.get("draft_content")
        if state_draft:
            draft = state_draft
            logger.info(
                f"get_current_draft: 从 session.state 读取草稿 "
                f"conversation={ctx.conversation_id}, chars={len(draft)}"
            )
        else:
            # 回退：从 ConversationManager 读取（数据库持久化草稿）
            try:
                conv = await ctx.conversation_manager.get_conversation(ctx.conversation_id)
                if conv and conv.writing_state and conv.writing_state.draft_content:
                    draft = conv.writing_state.draft_content
                    logger.info(
                        f"get_current_draft: 从 ConversationManager 读取草稿 "
                        f"conversation={ctx.conversation_id}, chars={len(draft)}"
                    )
            except Exception as e:
                logger.error(f"get_current_draft: 读取草稿失败: {e}")

        if not draft:
            logger.info(f"get_current_draft: 当前对话无草稿 conversation={ctx.conversation_id}")
            return "当前对话尚无草稿。"

        # 双路输出：正文存入 loaded_base_draft 供 write_document 自动衔接，不进 ADK 历史
        ctx.loaded_base_draft = draft

        # 同步恢复 doc_name / module_id，确保后续 write_document 继续写入同一文档目录，
        # 并在修改场景下沿用同一模块身份，避免重新触发模块消歧。
        if not ctx.loaded_base_doc_name:
            # 优先从 session.state 读取（上一轮 write_document 保存的 module_name）
            state_doc_name = tool_context.state.get("module_name")
            if state_doc_name:
                ctx.loaded_base_doc_name = state_doc_name
                ctx.current_module_name = state_doc_name
                logger.info(f"get_current_draft: 恢复 doc_name={state_doc_name} 来自 session.state")
            else:
                # 回退：从 ConversationManager 的 writing_state 读取
                try:
                    conv = await ctx.conversation_manager.get_conversation(ctx.conversation_id)
                    if conv and conv.writing_state and conv.writing_state.module_name:
                        ctx.loaded_base_doc_name = conv.writing_state.module_name
                        ctx.current_module_name = conv.writing_state.module_name
                        logger.info(
                            f"get_current_draft: 恢复 doc_name={ctx.loaded_base_doc_name} 来自 writing_state"
                        )
                except Exception as e:
                    logger.warning(f"get_current_draft: 恢复 doc_name 失败: {e}")

        if not ctx.loaded_base_module_id:
            state_module_id = tool_context.state.get("module_id")
            if state_module_id:
                ctx.loaded_base_module_id = state_module_id
                ctx.current_module_id = state_module_id
                logger.info(f"get_current_draft: 恢复 module_id={state_module_id} 来自 session.state")
            else:
                try:
                    conv = await ctx.conversation_manager.get_conversation(ctx.conversation_id)
                    if conv and conv.writing_state and conv.writing_state.module_id:
                        ctx.loaded_base_module_id = conv.writing_state.module_id
                        ctx.current_module_id = conv.writing_state.module_id
                        logger.info(
                            f"get_current_draft: 恢复 module_id={ctx.loaded_base_module_id} 来自 writing_state"
                        )
                except Exception as e:
                    logger.warning(f"get_current_draft: 恢复 module_id 失败: {e}")

        summary = f"已加载草稿，共 {len(draft)} 字，可直接调用 write_document(context=\"\") 修改。"
        return summary

    return get_current_draft
