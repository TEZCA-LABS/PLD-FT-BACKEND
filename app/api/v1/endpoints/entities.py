
from typing import Any, List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api import deps
from app.db.session import get_db
from app.models.entity import EntityDocument
from app.models.user import User
from app.schemas.entity_schema import Entity, EntityCreate
from app.services.etl.tasks import process_entity_data

router = APIRouter()

@router.get("/", response_model=List[Entity])
async def read_entities(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve entities.
    """
    result = await db.execute(select(EntityDocument).offset(skip).limit(limit))
    return result.scalars().all()

@router.post("/", status_code=status.HTTP_202_ACCEPTED)
async def create_entity(
    *,
    db: AsyncSession = Depends(get_db),
    entity_in: EntityCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create new entity (Triggering ETL/Vectorization in background).
    """
    # Trigger Celery task for processing (or call directly if we want sync response)
    # For this endpoint, we might want to just save it directly or trigger the task.
    # Let's trigger the task to simulate the "Heavy ETL" requirement, 
    # but for immediate feedback we might want to return what we accepted.
    
    # In a real scenario, this might be an endpoint to manually add an entity
    # which then gets vectorized.
    
    task = process_entity_data.delay(entity_in.name, entity_in.source, entity_in.content)
    
    # Return async task metadata; persistence is handled by worker.
    return {
        "task_id": task.id,
        "status": "accepted",
        "message": "Entity ingestion queued",
        "name": entity_in.name,
        "source": entity_in.source,
        "content": entity_in.content,
    }
