
from typing import Any
from fastapi import APIRouter, Depends
from app.schemas.rag_schema import AnalysisRequest, AnalysisResponse
from app.services.rag.chains import get_rag_chain, retrieve_context

router = APIRouter()

@router.post("/analyze-entity", response_model=AnalysisResponse)
async def analyze_entity(request: AnalysisRequest) -> Any:
    """
    Endpoint for natural language queries about sanction lists.
    """
    # 1. Retrieve context
    context = await retrieve_context(request.query)
    
    # 2. Run chain
    chain = get_rag_chain()
    response = await chain.ainvoke({"context": context, "question": request.query})
    
    return {"analysis": response}
