from typing import Any, Dict, Optional
from datetime import datetime
from pydantic import BaseModel

class AuditLogBase(BaseModel):
    action: str
    details: Optional[Dict[str, Any]] = None

class AuditLogCreate(AuditLogBase):
    user_id: int

class AuditLog(AuditLogBase):
    id: int
    user_id: int
    user_email: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True
