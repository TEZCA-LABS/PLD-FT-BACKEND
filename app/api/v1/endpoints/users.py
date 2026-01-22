
from typing import Any, List
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.user_schema import User, UserCreate, UserUpdate
from app.services.user_service import create_user, get_user_by_email

from app.api import deps
from app.core.config import settings

router = APIRouter()

@router.post("/", response_model=User)
async def create_user_endpoint(
    *,
    db: AsyncSession = Depends(get_db),
    user_in: UserCreate,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Create new user.
    Only superusers can create new users.
    To create a superuser, the 'master_password' must be provided and correct.
    """
    # Check Master Password if creating a superuser
    if user_in.is_superuser:
        if not user_in.master_password:
             raise HTTPException(
                status_code=400,
                detail="Master password is required to create a superuser.",
            )
        if user_in.master_password != settings.MASTER_PASSWORD:
             raise HTTPException(
                status_code=400,
                detail="Invalid master password.",
            )

    user = await get_user_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )
    user = await create_user(db, user=user_in, created_by_id=current_user.id)
    return user

@router.put("/{user_id}", response_model=User)
async def update_user_endpoint(
    *,
    db: AsyncSession = Depends(get_db),
    user_id: int,
    user_in: UserUpdate,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Update a user.
    Only superusers can update users.
    """
    from app.services.user_service import get_user, update_user
    
    user = await get_user(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    user = await update_user(db, db_user=user, user_in=user_in)
    return user
