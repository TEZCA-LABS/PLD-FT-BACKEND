from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.services.search_service import search_sanctions
from app.models.sanction import Sanction

router = APIRouter()

@router.get("/sanctions", response_model=List[dict])
async def search_sanctions_endpoint(
    q: str = Query(..., min_length=2, description="Search query (name, reference, etc.)"),
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(deps.get_db),
    # current_user = Depends(deps.get_current_active_user) # Uncomment to protect
) -> Any:
    """
    Search for sanctioned entities using hybrid search (Exact, Fuzzy, Vector).
    """
    results = await search_sanctions(db=db, query=q, limit=limit)
    
    # Simple serialization
    serialized = []
    for s in results:
        serialized.append({
            "id": s.id,
            "entity_name": s.entity_name,
            "reference_number": s.reference_number,
            "program": s.program,
            "source": s.source,
            "score": "N/A" # TODO: Return match score
        })
        
    return serialized
