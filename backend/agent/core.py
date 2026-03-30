"""
Agent Core - 主 Agent 类，接口层保持不变，内部替换为 ADK ReAct 实现。
"""

import logging
from typing import Optional, List, AsyncIterator

from agent.models import (
    ChatResponse,
    SkillInfo,
)

logger = logging.getLogger(__name__)


class AgentCore:
    """Core Agent - 接口层保持与旧版兼容，内部通过 ADK runner_adapter 实现。"""

    _instance: Optional["AgentCore"] = None

    def __init__(self):
        self._initialized = False
        self._skill_manager = None
        self._conversation_manager = None

    @classmethod
    def get_instance(cls) -> "AgentCore":
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self):
        """初始化 Agent：加载 Skills，初始化 ConversationManager。"""
        if self._initialized:
            return

        logger.info("Initializing Agent Core (ADK mode)...")

        from pathlib import Path
        from skill.manager import SkillManager
        from agent.conversation import ConversationManager

        # 加载 Skills
        skills_dir = str(Path(__file__).parent.parent.parent / "skills")
        self._skill_manager = SkillManager(skills_dir=skills_dir)
        await self._skill_manager.discover_and_load()

        # 初始化对话管理器
        self._conversation_manager = ConversationManager.get_instance()

        self._initialized = True
        loaded = len(await self.get_available_skills())
        logger.info(f"Agent Core (ADK) initialized. Loaded {loaded} skills.")

    async def stream_message(
        self,
        conversation_id: str,
        message: str,
    ) -> AsyncIterator[dict]:
        """流式处理用户消息，委托给 ADK runner_adapter。

        Yields:
            dict: WebSocket 消息，type 为 text / status / done / error。
        """
        if not self._initialized:
            await self.initialize()

        from agent.adk.runner_adapter import stream_message as adk_stream

        # ws_sender 在此上下文中不可用（由 main.py WebSocket handler 提供），
        # 使用 no-op sender；实际 ws_sender 由 main.py 直接调用 adk_stream 传入。
        async def _noop_sender(msg: dict):
            pass

        async for event in adk_stream(
            conversation_id=conversation_id,
            message=message,
            ws_sender=_noop_sender,
            conversation_manager=self._conversation_manager,
            skill_manager=self._skill_manager,
        ):
            yield event

    async def process_message(
        self,
        conversation_id: str,
        message: str,
    ) -> ChatResponse:
        """非流式处理（收集 stream_message 的完整输出）。"""
        if not self._initialized:
            await self.initialize()

        full_text = ""
        skill_id = None

        async for event in self.stream_message(conversation_id, message):
            if event.get("type") == "text":
                full_text += event.get("content", "")
            elif event.get("type") == "done":
                skill_id = event.get("skill_id")

        return ChatResponse(
            conversation_id=conversation_id,
            message=full_text,
            skill_invoked=skill_id,
        )

    async def get_available_skills(self) -> List[SkillInfo]:
        """返回所有已加载的 Skill。"""
        if not self._skill_manager:
            return []
        return await self._skill_manager.get_all_skills()

    async def get_skill(self, skill_id: str) -> Optional[SkillInfo]:
        """按 ID 获取单个 Skill。"""
        if not self._skill_manager:
            return None
        return await self._skill_manager.get_skill(skill_id)
