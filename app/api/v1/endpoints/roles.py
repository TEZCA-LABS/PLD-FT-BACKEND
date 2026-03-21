from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.user import User
from app.schemas.role_schema import RolePermissionsResponse, RolePermissionsUpdateRequest
from app.services.role_permissions_service import get_role_permissions, update_role_permissions

router = APIRouter()


@router.get("/permissions", response_model=RolePermissionsResponse)
async def read_role_permissions(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_privileged_user),
) -> Any:
    # db is injected for consistency with endpoint dependencies and auth policy.
    _ = db
    _ = current_user
    return get_role_permissions()


@router.put("/permissions", response_model=RolePermissionsResponse)
async def put_role_permissions(
    payload: RolePermissionsUpdateRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    _ = db
    _ = current_user
    updates = [{"id": item.id, "allowed_roles": item.allowed_roles} for item in payload.permissions]
    return update_role_permissions(updates)
