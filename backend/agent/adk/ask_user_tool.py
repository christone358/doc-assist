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

        # 发送问题到 WebSocket
        await ctx.ws_sender({"type": "question", "content": question})

        # 标记正在等待用户输入
        ctx.waiting_for_user = True

        try:
            # 等待用户回复（超时 10 分钟）
            response = await asyncio.wait_for(
                ctx.user_input_queue.get(),
                timeout=600.0,
            )
            logger.info(f"ask_user: 收到回复 [{str(response)[:50]}...]")
            return response
        except asyncio.TimeoutError:
            logger.warning("ask_user: 等待用户回复超时")
            return "（用户未在限定时间内回复，跳过此问题）"
        finally:
            ctx.waiting_for_user = False

    return ask_user
