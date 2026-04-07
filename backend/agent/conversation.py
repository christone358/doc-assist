"""
Conversation Manager - Manages multi-round conversation state and persistence.
"""

import json
import uuid
import logging
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

from agent.models import (
    ConversationInfo,
    ConversationCreate,
    ConversationRound,
    ConversationStatus,
    DocumentOutputInfo,
    DocumentType,
    ExecutionEvent,
    ExecutionObjectNode,
    SkillExecutionResult,
)

from datetime import datetime, timezone

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONVERSATIONS_DIR = PROJECT_ROOT / "backend" / "docs" / "conversations"

def _now() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class ConversationManager:
    """Manages conversation lifecycle, history, and persistence."""

    _instance: Optional["ConversationManager"] = None

    def __init__(self):
        self._conversations: Dict[str, ConversationInfo] = {}
        CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_instance(cls) -> "ConversationManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def create_conversation(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        document_type: Optional[DocumentType] = None,
    ) -> ConversationInfo:
        """Create a new conversation."""
        conv_id = str(uuid.uuid4())
        now = _now()

        conversation = ConversationInfo(
            id=conv_id,
            name=name or f"对话 {now.strftime('%Y-%m-%d %H:%M')}",
            description=description,
            status=ConversationStatus.ACTIVE,
            document_type=document_type,
            created_at=now,
            updated_at=now,
            rounds=[],
            documents=[],
        )

        self._conversations[conv_id] = conversation
        await self._save(conversation)
        logger.info(f"Created conversation: {conv_id}")
        return conversation

    async def get_conversation(self, conversation_id: str) -> Optional[ConversationInfo]:
        """Get a conversation by ID."""
        if conversation_id in self._conversations:
            return self._conversations[conversation_id]

        # Try loading from disk
        loaded = await self._load(conversation_id)
        if loaded:
            self._conversations[conversation_id] = loaded
        return loaded

    async def list_conversations(self) -> List[dict]:
        """List all conversations (summary only)."""
        conversations = []

        # Load from disk if not already in memory
        for conv_file in CONVERSATIONS_DIR.glob("*/conversation_log.json"):
            conv_id = conv_file.parent.name
            if conv_id not in self._conversations:
                loaded = await self._load(conv_id)
                if loaded:
                    self._conversations[conv_id] = loaded

        for conv in self._conversations.values():
            conversations.append({
                "id": conv.id,
                "name": conv.name,
                "status": conv.status,
                "document_type": conv.document_type,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat(),
                "round_count": len(conv.rounds),
                "document_count": len(conv.documents),
            })

        # Sort by updated_at descending
        conversations.sort(key=lambda x: x["updated_at"], reverse=True)
        return conversations

    async def add_round(
        self,
        conversation_id: str,
        user_input: str,
        agent_response: str,
        skill_invoked: Optional[str] = None,
        documents_generated: Optional[List[DocumentOutputInfo]] = None,
        llm_info: Optional[dict] = None,
        skill_execution: Optional[SkillExecutionResult] = None,
        execution_events: Optional[List[ExecutionEvent]] = None,
        execution_nodes: Optional[List[ExecutionObjectNode]] = None,
        state_snapshot: Optional[dict] = None,
    ) -> bool:
        """Add a new round to the conversation."""
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            logger.error(f"Conversation not found: {conversation_id}")
            return False

        round_id = len(conversation.rounds) + 1
        new_round = ConversationRound(
            round_id=round_id,
            timestamp=_now(),
            user_input=user_input,
            agent_response=agent_response,
            skill_invoked=skill_invoked,
            documents_generated=documents_generated or [],
            llm_info=llm_info,
            skill_execution=skill_execution,
            execution_events=execution_events or [],
            execution_nodes=execution_nodes or [],
            state_snapshot=state_snapshot,
        )

        conversation.rounds.append(new_round)
        conversation.updated_at = _now()

        if documents_generated:
            conversation.documents.extend(documents_generated)

        await self._save(conversation)
        return True

    async def update_status(
        self,
        conversation_id: str,
        status: ConversationStatus,
    ) -> bool:
        """Update conversation status."""
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            return False
        conversation.status = status
        conversation.updated_at = _now()
        await self._save(conversation)
        return True

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation."""
        conv_dir = CONVERSATIONS_DIR / conversation_id
        if conv_dir.exists():
            import shutil
            shutil.rmtree(conv_dir)

        self._conversations.pop(conversation_id, None)
        return True

    async def _save(self, conversation: ConversationInfo) -> None:
        """Persist conversation to disk."""
        conv_dir = CONVERSATIONS_DIR / conversation.id
        conv_dir.mkdir(parents=True, exist_ok=True)

        log_file = conv_dir / "conversation_log.json"
        data = conversation.model_dump(mode="json")

        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    async def _load(self, conversation_id: str) -> Optional[ConversationInfo]:
        """Load a conversation from disk."""
        log_file = CONVERSATIONS_DIR / conversation_id / "conversation_log.json"
        if not log_file.exists():
            return None

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ConversationInfo(**data)
        except Exception as e:
            logger.error(f"Failed to load conversation {conversation_id}: {e}")
            return None
