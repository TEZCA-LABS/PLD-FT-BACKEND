from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, cast, String

from app.models.audit_log import AuditLog

async def log_search(
    db: AsyncSession, 
    user_id: int, 
    query: str, 
    ip_address: str, 
    details: Dict[str, Any] = None
) -> AuditLog:
    """
    Logs a search action.
    """
    if details is None:
        details = {}
        
    details["query"] = query
    details["ip_address"] = ip_address
    
    log_entry = AuditLog(
        user_id=user_id,
        action="SEARCH_SANCTIONS",
        details=details
    )
    db.add(log_entry)
    await db.commit()
    await db.refresh(log_entry)
    return log_entry

async def get_audit_logs(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 50,
    user_id: Optional[int] = None,
    action_contains: Optional[str] = None,
    query_text: Optional[str] = None,
    timestamp_from: Optional[datetime] = None,
    timestamp_to: Optional[datetime] = None,
) -> List[AuditLog]:
    """
    Retrieves audit logs. 
    If user_id is provided, filters by that user (for user's own history, if we wanted to allow that).
    """
    query = select(AuditLog)
    
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)

    if action_contains:
        query = query.filter(AuditLog.action.ilike(f"%{action_contains}%"))

    if query_text:
        query = query.filter(cast(AuditLog.details, String).ilike(f"%{query_text}%"))

    if timestamp_from:
        query = query.filter(AuditLog.timestamp >= timestamp_from)

    if timestamp_to:
        query = query.filter(AuditLog.timestamp <= timestamp_to)

    query = query.order_by(desc(AuditLog.timestamp)).offset(skip).limit(limit)
        
    result = await db.execute(query)
    return result.scalars().all()
