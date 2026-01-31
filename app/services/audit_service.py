from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc

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
    user_id: Optional[int] = None
) -> List[AuditLog]:
    """
    Retrieves audit logs. 
    If user_id is provided, filters by that user (for user's own history, if we wanted to allow that).
    """
    query = select(AuditLog).order_by(desc(AuditLog.timestamp)).offset(skip).limit(limit)
    
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
        
    result = await db.execute(query)
    return result.scalars().all()
