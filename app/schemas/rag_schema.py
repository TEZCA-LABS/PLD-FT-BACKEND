
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

class AnalysisRequest(BaseModel):
    query: str


class MessageSource(BaseModel):
    name: Optional[str] = None
    organization: Optional[str] = None
    date: Optional[str] = None
    snippet: Optional[str] = None
    url: Optional[str] = None


class RelatedEntity(BaseModel):
    name: str
    relationship: Optional[str] = None
    type: Optional[str] = None


class AnalysisContext(BaseModel):
    source: Optional[MessageSource] = None
    related_entities: List[RelatedEntity] = Field(default_factory=list)


class UsageMetrics(BaseModel):
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    latency_ms: Optional[int] = None


class AnalysisOptions(BaseModel):
    model: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    redact_pii: Optional[bool] = False

class AnalysisResponse(BaseModel):
    analysis: str
    context: Optional[AnalysisContext] = None
    usage: Optional[UsageMetrics] = None
    model_version: Optional[str] = None


class SessionStatus(str, Enum):
    open = "open"
    closed = "closed"
    archived = "archived"


class ChatSessionCreate(BaseModel):
    title: str
    initial_context: Optional[Dict[str, Any]] = None


class ChatSessionUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[SessionStatus] = None


class ChatSessionItem(BaseModel):
    id: int
    title: str
    status: str
    last_message_preview: Optional[str] = None
    updated_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionCreateResponse(BaseModel):
    id: int
    title: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionListResponse(BaseModel):
    items: List[ChatSessionItem]
    total: int
    skip: int
    limit: int


class ChatMessageItem(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    context: Optional[AnalysisContext] = None

    class Config:
        from_attributes = True


class ChatMessageListResponse(BaseModel):
    items: List[ChatMessageItem]
    total: int
    skip: int
    limit: int


class ChatMessageCreateRequest(BaseModel):
    query: str
    options: Optional[AnalysisOptions] = None


class ConfidenceLevel(str, Enum):
    """Confidence level of RAG response based on match quality and query specificity."""
    high = "high"
    medium = "medium"
    low = "low"


class MatchTierType(str, Enum):
    """Classification of match tiers based on relevance scoring."""
    exact = "exact"
    strong = "strong"
    weak = "weak"
    semantic = "semantic"


class MatchResult(BaseModel):
    """Individual match result with confidence score and tier classification."""
    name: str
    source: str
    evidence_id: Optional[str] = None
    score: float = Field(ge=0.0, le=1.0)
    match_type: str = Field(default="unknown")
    details: Optional[str] = None


class MatchTierResults(BaseModel):
    """Organized results by confidence tier."""
    exact: List[MatchResult] = Field(default_factory=list)
    strong: List[MatchResult] = Field(default_factory=list)
    weak: List[MatchResult] = Field(default_factory=list)
    semantic: List[MatchResult] = Field(default_factory=list)


class ChatMessageCreateResponse(BaseModel):
    message_id: int
    analysis: str
    context: Optional[AnalysisContext] = None
    usage: Optional[UsageMetrics] = None
    model_version: Optional[str] = None
    created_at: datetime
    confidence: Optional[ConfidenceLevel] = None
    ambiguity_detected: Optional[bool] = None
    suggested_refinements: Optional[List[str]] = None
    match_tiers: Optional[MatchTierResults] = None


class AttachmentResponse(BaseModel):
    id: int
    file_name: str
    mime_type: str
    size: int
    status: str
    file_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AttachmentListResponse(BaseModel):
    items: List[AttachmentResponse]
    total: int
    skip: int
    limit: int


class ExportRequest(BaseModel):
    format: str = Field(default="json")
    include: List[str] = Field(default_factory=lambda: ["messages", "sources", "entities", "metadata"])


class AIEventRequest(BaseModel):
    session_id: int
    event_type: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
