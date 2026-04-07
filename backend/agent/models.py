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


class SkillExecutionStatus(str, Enum):
    COMPLETED = "completed"
    NEEDS_CLARIFICATION = "needs_clarification"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionEventStatus(str, Enum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


class ExecutionActor(str, Enum):
    ORCHESTRATOR = "orchestrator"
    SUBAGENT = "subagent"
    RUNTIME = "runtime"
    USER = "user"


class ExecutionPhase(str, Enum):
    PLAN = "plan"
    DELEGATE = "delegate"
    RESOURCE = "resource"
    CLARIFICATION = "clarification"
    WRITE = "write"
    COMPLETE = "complete"


class ExecutionNodeType(str, Enum):
    LLM_THOUGHT = "llm_thought"
    TOOL_CALL = "tool_call"
    SKILL_CALL = "skill_call"
    USER_QUESTION = "user_question"
    SYSTEM_STATE = "system_state"


class ExecutionNodeStatus(str, Enum):
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


class ToolSourceType(str, Enum):
    MCP = "mcp"
    BUILTIN = "builtin"
    INTERNAL = "internal"


class ExecutionObjectNode(BaseModel):
    """Structured execution object node for the right-side observability panel."""

    node_id: str
    node_type: ExecutionNodeType
    title: str
    status: ExecutionNodeStatus
    actor: ExecutionActor
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_order: int = 0
    parent_node_id: Optional[str] = None
    execution_id: Optional[str] = None
    tool_name: Optional[str] = None
    tool_source: Optional[ToolSourceType] = None
    skill_id: Optional[str] = None
    skill_name: Optional[str] = None
    reason: Optional[str] = None
    display_input: str = ""
    output_preview: str = ""
    output_detail: str = ""
    detail_text: str = ""
    is_truncated: bool = False
    truncated_fields: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


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


class SkillResourceInfo(BaseModel):
    """A visible resource inside a skill directory."""
    category: str
    path: str
    name: str


class SkillSummary(BaseModel):
    """Public summary information for a single skill."""
    id: str
    name: str
    description: str
    type: str
    version: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)


class SkillDetail(SkillSummary):
    """Public detail information for a single skill."""
    resources: List[SkillResourceInfo] = Field(default_factory=list)


class SkillInfo(SkillDetail):
    """Internal skill model used by agent runtime."""
    skill_md_path: Optional[str] = Field(default=None, exclude=True)

    def to_summary(self) -> SkillSummary:
        return SkillSummary(
            id=self.id,
            name=self.name,
            description=self.description,
            type=self.type,
            version=self.version,
            capabilities=list(self.capabilities),
        )

    def to_detail(self) -> SkillDetail:
        return SkillDetail(
            id=self.id,
            name=self.name,
            description=self.description,
            type=self.type,
            version=self.version,
            capabilities=list(self.capabilities),
            resources=list(self.resources),
        )


class SkillListResponse(BaseModel):
    """Response for skill listing."""
    skills: List[SkillSummary]
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


class SkillExecutionFailure(BaseModel):
    """Structured failure signal returned from a sub-agent execution."""
    type: str
    message: str
    stage: str
    details: Optional[Dict[str, Any]] = None


class SkillExecutionResult(BaseModel):
    """Minimal structured execution result returned to the orchestrator."""
    execution_id: str
    skill_id: str
    status: SkillExecutionStatus
    summary: str
    failure: Optional[SkillExecutionFailure] = None
    retryable: bool = False


class ExecutionEvent(BaseModel):
    """Structured execution-chain event for UI/logging."""
    execution_id: str
    actor: ExecutionActor
    phase: ExecutionPhase
    name: str
    status: ExecutionEventStatus
    display_text: str
    parent_execution_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatResponse(BaseModel):
    """Response to a chat message."""
    conversation_id: str
    message: str                              # Agent response text
    role: MessageRole = MessageRole.ASSISTANT
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    documents_generated: List[DocumentOutputInfo] = Field(default_factory=list)
    skill_invoked: Optional[str] = None
    requires_clarification: bool = False
    clarification_options: List[str] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


class ConversationRound(BaseModel):
    """A single round in the conversation."""
    round_id: int
    timestamp: datetime
    user_input: str
    agent_response: str
    skill_invoked: Optional[str] = None
    documents_generated: List[DocumentOutputInfo] = Field(default_factory=list)
    llm_info: Optional[Dict[str, Any]] = None
    skill_execution: Optional[SkillExecutionResult] = None
    execution_events: List[ExecutionEvent] = Field(default_factory=list)
    execution_nodes: List[ExecutionObjectNode] = Field(default_factory=list)
    state_snapshot: Optional[Dict[str, Any]] = None


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
    rounds: List[ConversationRound] = Field(default_factory=list)
    documents: List[DocumentOutputInfo] = Field(default_factory=list)
    writing_state: Optional[WritingState] = None


class StreamChunk(BaseModel):
    """A chunk of streamed response."""
    type: str           # "text", "skill_start", "skill_end", "document", "error", "done"
    content: Optional[str] = None
    skill_id: Optional[str] = None
    document: Optional[DocumentOutputInfo] = None
    error: Optional[str] = None
    conversation_id: Optional[str] = None
