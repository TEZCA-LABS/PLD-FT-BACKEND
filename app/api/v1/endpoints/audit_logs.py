from typing import Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.services.audit_service import get_audit_logs
from app.models.user import User

from app.schemas.audit_log_schema import AuditLog

router = APIRouter()

@router.get("/history", response_model=List[AuditLog])
async def read_audit_logs(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_privileged_user),
) -> Any:
    """
    Retrieve audit logs.
    Only Admins and Auditors can access this endpoint.
    """
    logs = await get_audit_logs(db, skip=skip, limit=limit)
    return logs
