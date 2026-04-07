"""
ask_user Tool - 向用户提问并等待回复。

设计：ConversationContext 持有 asyncio.Queue，工具发送问题后挂起等待，
WebSocket handler 将用户回复放入队列，工具恢复并返回答案。
"""

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.adk.runner_adapter import ConversationContext

logger = logging.getLogger(__name__)


def create_ask_user_tool(ctx: "ConversationContext"):
    """创建 ask_user 工具函数，捕获对话上下文。"""

    async def ask_user(question: str) -> str:
        """向用户提问，等待用户回复后返回答案。

        当系统无法从已有事实中确定信息时调用此工具。
        系统将向用户展示问题，并在收到回复后继续执行。

        Args:
            question: 向用户提出的问题，应明确说明需要哪类信息。

        Returns:
            用户的回复内容。
        """
        logger.info(f"ask_user: 发送问题 [{question[:50]}...]")
        from agent.adk.runner_adapter import (
            complete_tool_node,
            create_question_node,
            update_execution_node,
            emit_execution_event,
            get_active_context,
        )
        from agent.models import (
            ExecutionActor,
            ExecutionEventStatus,
            ExecutionNodeStatus,
            ExecutionPhase,
        )

        active_ctx = get_active_context(ctx.conversation_id)
        execution_id = ctx.current_execution_id or ctx.orchestrator_execution_id

        # 发送问题到 WebSocket
        await ctx.ws_sender({"type": "question", "content": question})
        question_node = await create_question_node(
            ctx,
            question=question,
            actor=ExecutionActor.SUBAGENT if ctx.current_execution_id else ExecutionActor.ORCHESTRATOR,
            parent_node_id=ctx.current_skill_node_id if ctx.current_execution_id else None,
        )
        ctx.current_question_node_id = question_node.node_id
        await emit_execution_event(
            ctx,
            execution_id=execution_id,
            actor=ExecutionActor.SUBAGENT if ctx.current_execution_id else ExecutionActor.ORCHESTRATOR,
            phase=ExecutionPhase.CLARIFICATION,
            name="ask_user",
            status=ExecutionEventStatus.STARTED,
            display_text=question,
            data={
                "node_id": question_node.node_id,
                "parent_node_id": question_node.parent_node_id,
            },
        )

        # 标记正在等待用户输入
        ctx.waiting_for_user = True
        if active_ctx and active_ctx is not ctx:
            active_ctx.waiting_for_user = True

        try:
            # 等待用户回复（超时 10 分钟）
            response = await asyncio.wait_for(
                ctx.user_input_queue.get(),
                timeout=600.0,
            )
            logger.info(f"ask_user: 收到回复 [{str(response)[:50]}...]")
            ctx.clarification_context.append(f"Q: {question}\nA: {response}")
            await emit_execution_event(
                ctx,
                execution_id=execution_id,
                actor=ExecutionActor.USER,
                phase=ExecutionPhase.CLARIFICATION,
                name="clarification_answered",
                status=ExecutionEventStatus.COMPLETED,
                display_text=f"用户已回复：{str(response)[:80]}",
                data={"question": question, "answer": response},
            )
            if ctx.current_question_node_id:
                await update_execution_node(
                    ctx,
                    ctx.current_question_node_id,
                    status=ExecutionNodeStatus.COMPLETED,
                    output_preview=f"用户已回复：{str(response)[:80]}",
                    output_detail=f"Q: {question}\n\nA: {response}",
                )
                ctx.current_question_node_id = None
            await complete_tool_node(
                ctx,
                execution_id=execution_id,
                tool_name="ask_user",
                parent_node_id=ctx.current_skill_node_id if ctx.current_execution_id else None,
                status=ExecutionNodeStatus.COMPLETED,
                output_preview=f"用户已回复：{str(response)[:80]}",
                output_detail=f"Q: {question}\n\nA: {response}",
            )
            return response
        except asyncio.TimeoutError:
            logger.warning("ask_user: 等待用户回复超时")
            await emit_execution_event(
                ctx,
                execution_id=execution_id,
                actor=ExecutionActor.RUNTIME,
                phase=ExecutionPhase.CLARIFICATION,
                name="clarification_timeout",
                status=ExecutionEventStatus.FAILED,
                display_text="等待用户回复超时",
                data={"question": question},
            )
            if ctx.current_question_node_id:
                await update_execution_node(
                    ctx,
                    ctx.current_question_node_id,
                    status=ExecutionNodeStatus.FAILED,
                    output_preview="等待用户回复超时",
                    output_detail=question,
                )
                ctx.current_question_node_id = None
            await complete_tool_node(
                ctx,
                execution_id=execution_id,
                tool_name="ask_user",
                parent_node_id=ctx.current_skill_node_id if ctx.current_execution_id else None,
                status=ExecutionNodeStatus.FAILED,
                output_preview="等待用户回复超时",
                output_detail=question,
            )
            return "（用户未在限定时间内回复，跳过此问题）"
        finally:
            ctx.waiting_for_user = False
            if active_ctx and active_ctx is not ctx:
                active_ctx.waiting_for_user = False

    return ask_user
