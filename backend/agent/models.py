"""
Pydantic models for the Agent API request/response schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class DocumentType(str, Enum):
    REQUIREMENTS = "requirements"
    DESIGN = "design"
    API = "api"
    TEST = "test"
    USER_GUIDE = "user-guide"
    OTHER = "other"


class ConversationStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"


# =============================================================================
# Request Models
# =============================================================================

class ChatRequest(BaseModel):
    """Request model for sending a chat message."""
    conversation_id: str = Field(..., description="Conversation ID")
    message: str = Field(..., description="User message")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")


class ConversationCreate(BaseModel):
    """Request model for creating a new conversation."""
    name: Optional[str] = Field(None, description="Conversation name")
    description: Optional[str] = Field(None, description="Conversation description")
    document_type: Optional[DocumentType] = Field(None, description="Primary document type")


# =============================================================================
# Response Models
# =============================================================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    components: Dict[str, str]


class MessageInfo(BaseModel):
    """A single message in the conversation."""
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Optional[Dict[str, Any]] = None


class SkillInfo(BaseModel):
    """Information about a single skill."""
    id: str
    name: str
    description: str
    type: str
    version: Optional[str] = None
    tags: List[str] = []
    capabilities: List[str] = []
    skill_md_path: Optional[str] = None  # Absolute path to skill.md, for lazy content loading


class SkillListResponse(BaseModel):
    """Response for skill listing."""
    skills: List[SkillInfo]
    total: int = 0

    def __init__(self, **data):
        super().__init__(**data)
        self.total = len(self.skills)


class DocumentOutputInfo(BaseModel):
    """Information about a generated document."""
    doc_type: str
    doc_name: str
    file_path: str          # Relative path from docs/
    version: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    file_size_bytes: Optional[int] = None


class ChatResponse(BaseModel):
    """Response to a chat message."""
    conversation_id: str
    message: str                              # Agent response text
    role: MessageRole = MessageRole.ASSISTANT
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    documents_generated: List[DocumentOutputInfo] = []
    skill_invoked: Optional[str] = None
    requires_clarification: bool = False
    clarification_options: List[str] = []
    metadata: Optional[Dict[str, Any]] = None


class ConversationRound(BaseModel):
    """A single round in the conversation."""
    round_id: int
    timestamp: datetime
    user_input: str
    agent_response: str
    skill_invoked: Optional[str] = None
    documents_generated: List[DocumentOutputInfo] = []
    llm_info: Optional[Dict[str, Any]] = None


class WritingState(BaseModel):
    """Tracks the current document writing state within a conversation."""
    module_id: str
    module_name: str
    skill_id: str
    doc_type: str
    draft_content: str
    saved_version: Optional[str] = None
    saved_path: Optional[str] = None


class ConversationInfo(BaseModel):
    """Detailed information about a conversation."""
    id: str
    name: str
    description: Optional[str] = None
    status: ConversationStatus = ConversationStatus.ACTIVE
    document_type: Optional[DocumentType] = None
    created_at: datetime
    updated_at: datetime
    rounds: List[ConversationRound] = []
    documents: List[DocumentOutputInfo] = []
    writing_state: Optional[WritingState] = None


class StreamChunk(BaseModel):
    """A chunk of streamed response."""
    type: str           # "text", "skill_start", "skill_end", "document", "error", "done"
    content: Optional[str] = None
    skill_id: Optional[str] = None
    document: Optional[DocumentOutputInfo] = None
    error: Optional[str] = None
    conversation_id: Optional[str] = None
