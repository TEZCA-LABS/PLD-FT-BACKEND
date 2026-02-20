
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


class ChatMessageCreateResponse(BaseModel):
    message_id: int
    analysis: str
    context: Optional[AnalysisContext] = None
    usage: Optional[UsageMetrics] = None
    model_version: Optional[str] = None
    created_at: datetime


class AttachmentResponse(BaseModel):
    id: int
    file_name: str
    mime_type: str
    size: int
    status: str
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
