"""
Pydantic domain models, enums, validators, and serialization schemas for Graph-Based AI Agent Memory.
"""

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


# --- Enums ---

class MemoryType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    OBSERVATION = "observation"
    FINDING = "finding"
    FEEDBACK = "feedback"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    STALE = "stale"
    DISPUTED = "disputed"
    SUPERSEDED = "superseded"
    UNVERIFIED = "unverified"
    ARCHIVED = "archived"


class SourceType(str, Enum):
    FILE = "file"
    SESSION = "session"
    TEST_RUN = "test_run"
    GIT_COMMIT = "git_commit"
    MANUAL = "manual"
    AGENT = "agent"


class AuthorType(str, Enum):
    AGENT = "agent"
    DEVELOPER = "developer"


class DecisionStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


class EntityType(str, Enum):
    FILE = "file"
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    SERVICE = "service"
    API_ENDPOINT = "api_endpoint"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    CHECKPOINTED = "checkpointed"
    CLOSED = "closed"


class EvidenceType(str, Enum):
    TEST_RESULT = "test_result"
    BENCHMARK = "benchmark"
    FILE_DIFF = "file_diff"
    LOG_OUTPUT = "log_output"
    DOC_REFERENCE = "doc_reference"


class FeedbackRating(str, Enum):
    USEFUL = "useful"
    STALE = "stale"
    INCORRECT = "incorrect"
    DISPUTED = "disputed"


# --- Secret Detection Utility ---

SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),
    re.compile(r"ghp_[a-zA-Z0-9]{20,}", re.IGNORECASE),
    re.compile(r"xox[baprs]-[0-9a-zA-Z]{10,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE),
    re.compile(r"(?:api[_-]?key|secret|password|bearer)\s*[:=]\s*['\"][a-zA-Z0-9_\-\.]{8,}['\"]", re.IGNORECASE),
]


def check_for_secrets(text: str) -> None:
    """Raises ValueError if potentially sensitive credentials or raw secrets are detected."""
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise ValueError(
                "Security rejection: Input contains potential raw secret, API key, or credential pattern."
            )


def current_iso_timestamp() -> str:
    """Returns the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


# --- Node Domain Models ---

class WorkspaceModel(BaseModel):
    id: str = Field(..., description="Unique workspace identifier")
    name: str = Field(default="", description="Human-readable workspace name")
    description: Optional[str] = Field(None, description="Workspace description")
    created_at: str = Field(default_factory=current_iso_timestamp)


class DeveloperModel(BaseModel):
    id: str = Field(..., description="Developer username or ID")
    name: str = Field(..., description="Developer full name")
    email: Optional[str] = Field(None, description="Developer email")


class AgentModel(BaseModel):
    id: str = Field(..., description="Agent identifier")
    model: str = Field("unknown", description="Foundation model name")
    role: str = Field("assistant", description="Configured agent persona or role")


class SessionModel(BaseModel):
    id: str = Field(..., description="Unique session ID")
    workspace_id: str = Field(..., description="Owning workspace ID")
    agent_id: str = Field(..., description="Agent performing the session")
    status: SessionStatus = Field(default=SessionStatus.ACTIVE)
    started_at: str = Field(default_factory=current_iso_timestamp)
    ended_at: Optional[str] = None
    last_checkpoint_at: Optional[str] = None
    summary: Optional[str] = None
    changed_files: List[str] = Field(default_factory=list)
    verified_findings: List[str] = Field(default_factory=list)
    test_outcomes: Optional[str] = None
    blockers: Optional[str] = None
    next_steps: Optional[str] = None
    version: int = Field(default=1, ge=1, description="Optimistic concurrency version counter")


class ConversationMessageModel(BaseModel):
    id: str = Field(..., description="Unique, idempotent conversation message ID")
    workspace_id: str = Field(..., description="Owning workspace ID")
    session_id: str = Field(..., description="Session that owns this message")
    role: Literal["user", "assistant", "tool", "system"]
    content: str = Field(..., min_length=1)
    created_at: str = Field(default_factory=current_iso_timestamp)

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, value: str) -> str:
        check_for_secrets(value)
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Conversation message content must not be empty")
        return cleaned


class EvidenceModel(BaseModel):
    id: str = Field(..., description="Unique evidence ID")
    workspace_id: str = Field(..., description="Owning workspace ID")
    evidence_type: EvidenceType = Field(default=EvidenceType.TEST_RESULT)
    content: str = Field(..., min_length=1, description="Verifiable evidence content")
    source_uri: str = Field("unknown", description="Source file, test name, or log URI")
    verified: bool = Field(default=True, description="Whether this evidence was verified")
    created_at: str = Field(default_factory=current_iso_timestamp)

    @field_validator("content")
    @classmethod
    def sanitize_evidence(cls, v: str) -> str:
        check_for_secrets(v)
        return v.strip()


class MemoryModel(BaseModel):
    id: str = Field(..., description="Unique memory ID")
    workspace_id: str = Field(..., description="Owning workspace ID")
    content: str = Field(..., min_length=1, description="Memory text or claim")
    memory_type: MemoryType = Field(default=MemoryType.FINDING)
    status: MemoryStatus = Field(default=MemoryStatus.ACTIVE)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_type: SourceType = Field(default=SourceType.AGENT)
    source_ref: str = Field("unknown", description="Source file path, session, or git hash")
    author_id: str = Field("system", description="Agent or Developer ID who authored this")
    author_type: AuthorType = Field(default=AuthorType.AGENT)
    session_id: Optional[str] = Field(None, description="Originating session ID")
    version: int = Field(default=1, ge=1, description="Optimistic concurrency version counter")
    superseded_by: Optional[str] = Field(None, description="ID of superseding memory if obsolete")
    valid_until: Optional[str] = Field(None, description="Optional ISO timestamp expiration")
    created_at: str = Field(default_factory=current_iso_timestamp)
    updated_at: str = Field(default_factory=current_iso_timestamp)
    content_hash: Optional[str] = Field(None, description="Normalized SHA-256 content hash")

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        check_for_secrets(v)
        return v.strip()


class DecisionModel(BaseModel):
    id: str = Field(..., description="Unique decision ID")
    workspace_id: str = Field(..., description="Owning workspace ID")
    title: str = Field(..., min_length=1, description="Short title of decision")
    rationale: str = Field(..., min_length=1, description="Why this decision was made")
    alternatives_considered: List[str] = Field(default_factory=list, description="Rejected alternatives")
    status: DecisionStatus = Field(default=DecisionStatus.ACCEPTED)
    author_id: str = Field("system", description="Authoring agent or developer ID")
    author_type: AuthorType = Field(default=AuthorType.AGENT)
    session_id: Optional[str] = Field(None, description="Originating session ID")
    version: int = Field(default=1, ge=1, description="Optimistic concurrency version counter")
    created_at: str = Field(default_factory=current_iso_timestamp)
    updated_at: str = Field(default_factory=current_iso_timestamp)

    @field_validator("title", "rationale")
    @classmethod
    def sanitize_fields(cls, v: str) -> str:
        check_for_secrets(v)
        return v.strip()


class EntityModel(BaseModel):
    id: str = Field(..., description="Entity identifier, e.g. entity:src/file.py")
    workspace_id: str = Field(..., description="Owning workspace ID")
    name: str = Field(..., description="Entity name")
    entity_type: EntityType = Field(default=EntityType.FILE)
    path: Optional[str] = Field(None, description="Relative file path")
    properties: Dict[str, Any] = Field(default_factory=dict)


class TaskModel(BaseModel):
    id: str = Field(..., description="Task identifier")
    workspace_id: str = Field(..., description="Owning workspace ID")
    title: str = Field(..., description="Task title / objective")
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    created_at: str = Field(default_factory=current_iso_timestamp)
    updated_at: str = Field(default_factory=current_iso_timestamp)


# --- MCP Tool Input / Output Models ---

class MemorySaveInput(BaseModel):
    workspace_id: Optional[str] = None
    content: str = Field(..., min_length=1, description="The memory content or finding to persist")
    memory_type: MemoryType = Field(default=MemoryType.FINDING)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_type: SourceType = Field(default=SourceType.AGENT)
    source_ref: str = Field("unknown", description="Source file, test name, or commit reference")
    entity_ids: Optional[List[str]] = Field(default=None, description="Optional entity IDs to link with RELATES_TO")
    evidence_content: Optional[str] = Field(default=None, description="Optional verifiable evidence text")
    session_id: Optional[str] = None
    author_id: Optional[str] = None
    author_type: AuthorType = Field(default=AuthorType.AGENT)


class MemoryUpdateInput(BaseModel):
    memory_id: str = Field(..., description="The ID of the memory to update")
    workspace_id: Optional[str] = None
    expected_version: int = Field(..., ge=1, description="Expected current version for optimistic concurrency check")
    new_content: Optional[str] = Field(None, min_length=1, description="Updated memory content")
    new_status: Optional[MemoryStatus] = None
    new_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    superseded_by: Optional[str] = None


class DecisionRecordInput(BaseModel):
    workspace_id: Optional[str] = None
    title: str = Field(..., min_length=1, description="Decision title")
    rationale: str = Field(..., min_length=1, description="Why this decision was chosen")
    alternatives_considered: Optional[List[str]] = Field(default_factory=list, description="Evaluated alternatives")
    evidence_content: Optional[str] = Field(None, description="Supporting evidence or test result")
    evidence_source: Optional[str] = Field("session", description="Source reference for evidence")
    session_id: Optional[str] = None
    author_id: Optional[str] = None
    author_type: AuthorType = Field(default=AuthorType.AGENT)
    status: DecisionStatus = Field(default=DecisionStatus.ACCEPTED)


class MemorySearchInput(BaseModel):
    workspace_id: Optional[str] = None
    query: Optional[str] = Field(None, description="Search keywords or task query")
    entity_id: Optional[str] = Field(None, description="Optional entity filter")
    memory_type: Optional[MemoryType] = None
    status: Optional[MemoryStatus] = Field(default=MemoryStatus.ACTIVE)
    limit: int = Field(default=10, ge=1, le=50)


class MemoryTraverseInput(BaseModel):
    workspace_id: Optional[str] = None
    start_node_id: str = Field(..., description="Memory, Entity, or Decision ID to begin traversal from")
    max_depth: int = Field(default=2, ge=1, le=4, description="Maximum traversal depth (hops)")
    relationship_types: Optional[List[str]] = Field(
        default=None,
        description="Filter relationship types, e.g. ['RELATES_TO', 'SUPPORTED_BY', 'DECIDED', 'SUPERSEDES']"
    )
    limit: int = Field(default=20, ge=1, le=50)


class SessionStartInput(BaseModel):
    workspace_id: Optional[str] = None
    agent_id: str = Field(..., description="Unique agent identifier")
    session_id: Optional[str] = Field(None, description="Optional custom session ID; generated if omitted")


class SessionCheckpointInput(BaseModel):
    session_id: str = Field(..., description="Active session ID")
    workspace_id: Optional[str] = None
    task_progress: str = Field(..., description="Progress summary or current task status")
    changed_files: Optional[List[str]] = Field(default_factory=list)
    verified_findings: Optional[List[str]] = Field(default_factory=list)
    test_outcomes: Optional[str] = None
    blockers: Optional[str] = None
    next_steps: Optional[str] = None

    @field_validator("task_progress", "test_outcomes", "blockers", "next_steps")
    @classmethod
    def sanitize_checkpoint_text(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            check_for_secrets(value)
        return value.strip() if value is not None else None

    @field_validator("changed_files", "verified_findings")
    @classmethod
    def sanitize_checkpoint_items(cls, values: Optional[List[str]]) -> Optional[List[str]]:
        if values is not None:
            for value in values:
                check_for_secrets(value)
        return [value.strip() for value in values] if values is not None else None


class SessionEndInput(BaseModel):
    session_id: str = Field(..., description="Active session ID to close")
    workspace_id: Optional[str] = None
    summary: str = Field(..., min_length=1, description="Final accomplishments summary")

    @field_validator("summary")
    @classmethod
    def sanitize_summary(cls, value: str) -> str:
        check_for_secrets(value)
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Session summary must not be empty")
        return cleaned


class MemoryFeedbackInput(BaseModel):
    memory_id: str = Field(..., description="Target memory ID")
    workspace_id: Optional[str] = None
    rating: FeedbackRating = Field(..., description="useful, stale, incorrect, or disputed")
    notes: Optional[str] = None


# --- Context Packet Result ---

class ContextPacket(BaseModel):
    workspace_id: str
    query: Optional[str] = None
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    decisions: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    connected_entities: List[Dict[str, Any]] = Field(default_factory=list)
    failed_approaches: List[Dict[str, Any]] = Field(default_factory=list)
    conflicts_and_stale: List[Dict[str, Any]] = Field(default_factory=list)
    suggested_next_steps: List[str] = Field(default_factory=list)
    total_items: int = 0
