from typing import Any, List
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.rag_schema import AIEventRequest

from app.api import deps
from app.services.audit_service import get_audit_logs
from app.models.user import User
from app.models.audit_log import AuditLog as AuditLogModel

from app.schemas.audit_log_schema import AuditLog

router = APIRouter()


async def _fetch_audit_logs(
    db: AsyncSession,
    skip: int,
    limit: int,
    action_contains: str | None,
    query_text: str | None,
    timestamp_from: datetime | None,
    timestamp_to: datetime | None,
) -> list[AuditLog]:
    return await get_audit_logs(
        db,
        skip=skip,
        limit=limit,
        action_contains=action_contains,
        query_text=query_text,
        timestamp_from=timestamp_from,
        timestamp_to=timestamp_to,
    )


@router.get("/", response_model=List[AuditLog])
async def read_audit_logs_root(
    skip: int = 0,
    limit: int = 50,
    action_contains: str | None = Query(None, description="Action filter"),
    query_text: str | None = Query(None, description="Search text in details"),
    timestamp_from: datetime | None = Query(None, description="Start timestamp"),
    timestamp_to: datetime | None = Query(None, description="End timestamp"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_privileged_user),
) -> Any:
    """
    Retrieve audit logs from root path for backward compatibility.
    """
    return await _fetch_audit_logs(
        db=db,
        skip=skip,
        limit=limit,
        action_contains=action_contains,
        query_text=query_text,
        timestamp_from=timestamp_from,
        timestamp_to=timestamp_to,
    )

@router.get("/history", response_model=List[AuditLog])
async def read_audit_logs(
    skip: int = 0,
    limit: int = 50,
    action_contains: str | None = Query(None, description="Action filter"),
    query_text: str | None = Query(None, description="Search text in details"),
    timestamp_from: datetime | None = Query(None, description="Start timestamp"),
    timestamp_to: datetime | None = Query(None, description="End timestamp"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_privileged_user),
) -> Any:
    """
    Retrieve audit logs.
    Only Admins and Auditors can access this endpoint.
    """
    logs = await _fetch_audit_logs(
        db=db,
        skip=skip,
        limit=limit,
        action_contains=action_contains,
        query_text=query_text,
        timestamp_from=timestamp_from,
        timestamp_to=timestamp_to,
    )
    return logs


@router.post("/ai-events", response_model=AuditLog, status_code=201)
async def create_ai_event(
    payload: AIEventRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    event = AuditLogModel(
        user_id=current_user.id,
        action=f"AI_{payload.event_type.upper()}",
        details={"session_id": payload.session_id, **payload.metadata},
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event
