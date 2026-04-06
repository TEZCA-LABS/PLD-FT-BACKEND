from typing import Any, Dict
from datetime import date
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
    source: str | None = Query(None, description="Filter by source"),
    program: str | None = Query(None, description="Filter by program"),
    listed_after: date | None = Query(None, description="Filter sanctions listed on or after this date"),
    listed_before: date | None = Query(None, description="Filter sanctions listed on or before this date"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_user)
) -> Any:
    """
    Search for sanctioned entities using hybrid search (Exact, Fuzzy, Vector).
    Returns a summary analysis and the list of results.
    """
    results = await search_sanctions(
        db=db,
        query=q,
        limit=limit,
        source=source,
        program=program,
        listed_after=listed_after,
        listed_before=listed_before,
    )

    # Simple serialization first (before optional side-effects like audit log)
    serialized = []
    match_breakdown = {
        "exact": 0,
        "fuzzy": 0,
        "vector": 0,
        "cluster": 0,
    }
    for item in results:
        s = item["sanction"]
        match_type = item.get("match_type") or "unknown"
        if match_type.startswith("cluster"):
            match_breakdown["cluster"] += 1
        elif match_type in match_breakdown:
            match_breakdown[match_type] += 1

        serialized.append({
            "id": s.id,
            "entity_name": s.entity_name,
            "reference_number": s.reference_number,
            "program": s.program,
            "source": s.source,
            "score": item.get("score"),
            "match_type": match_type,
        })
    
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
        await db.rollback()

    # Analyze with LangChain
    summary = await analyze_search_results(query=q, results=serialized)
        
    return {
        "query": q,
        "filters": {
            "source": source,
            "program": program,
            "listed_after": listed_after.isoformat() if listed_after else None,
            "listed_before": listed_before.isoformat() if listed_before else None,
        },
        "match_breakdown": match_breakdown,
        "summary": summary,
        "results": serialized
    }
