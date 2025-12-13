
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.entity import EntityDocument
from app.schemas.entity_schema import Entity, EntityCreate
from app.services.etl.tasks import process_entity_data

router = APIRouter()

@router.get("/", response_model=List[Entity])
async def read_entities(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve entities.
    """
    result = await db.execute(select(EntityDocument).offset(skip).limit(limit))
    return result.scalars().all()

@router.post("/", response_model=Entity)
async def create_entity(
    *,
    db: AsyncSession = Depends(get_db),
    entity_in: EntityCreate,
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
    
    # We return a dummy response since the actual creation happens in the worker
    # Or we could create the DB record here and let the worker handle the embedding.
    # For simplicity, let's just return what was sent, assuming success.
    return {
        "id": 0, # ID will be generated
        "name": entity_in.name,
        "source": entity_in.source,
        "content": entity_in.content
    }
