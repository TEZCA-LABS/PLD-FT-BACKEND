from typing import Any, List, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.services.search_service import search_sanctions
from app.models.sanction import Sanction
from app.services.langchain_service import analyze_search_results

router = APIRouter()

@router.get("/sanctions", response_model=Dict[str, Any])
async def search_sanctions_endpoint(
    request: Request,
    q: str = Query(..., min_length=2, description="Search query (name, reference, etc.)"),
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_user)
) -> Any:
    """
    Search for sanctioned entities using hybrid search (Exact, Fuzzy, Vector).
    Returns a summary analysis and the list of results.
    """
    results = await search_sanctions(db=db, query=q, limit=limit)
    
    # Audit Logging
    try:
        from app.services.audit_service import log_search
        await log_search(
            db=db,
            user_id=current_user.id,
            query=q,
            ip_address=request.client.host if request.client else "unknown",
            details={"limit": limit, "results_count": len(results)}
        )
    except Exception as e:
        # Do not fail the search if logging fails, but log the error
        print(f"Failed to log search: {e}")
        pass
    
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

    # Analyze with LangChain
    summary = await analyze_search_results(query=q, results=serialized)
        
    return {
        "query": q,
        "summary": summary,
        "results": serialized
    }
