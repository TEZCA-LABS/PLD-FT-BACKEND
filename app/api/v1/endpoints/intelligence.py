
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.user import User
from app.schemas.rag_schema import (
    AnalysisRequest,
    AnalysisResponse,
    AttachmentListResponse,
    AttachmentResponse,
    ChatMessageCreateRequest,
    ChatMessageCreateResponse,
    ChatMessageListResponse,
    ChatSessionCreate,
    ChatSessionCreateResponse,
    ChatSessionListResponse,
    ChatSessionUpdate,
    ExportRequest,
)
from app.services.audit_service import log_search
from app.services.intelligence_service import (
    _ensure_session_access,
    build_export_payload,
    build_json_bytes,
    build_pdf_from_payload,
    create_attachment,
    create_message_and_analysis,
    create_session,
    delete_session,
    get_session_or_404,
    list_attachments,
    list_messages,
    list_sessions,
    update_session,
)
from app.services.rag.chains import get_rag_chain, is_ambiguous_query, retrieve_context

router = APIRouter()


@router.post("/analyze-entity", response_model=AnalysisResponse)
async def analyze_entity(
    request: AnalysisRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Endpoint for natural language queries about sanction lists.
    Backward-compatible wrapper that now also returns context.
    """
    context = await retrieve_context(request.query)
    chain = get_rag_chain()
    response = await chain.ainvoke({"context": context, "question": request.query})

    if is_ambiguous_query(request.query, context):
        response = (
            f"{response}\n\n"
            "Sugerencia para mejorar la búsqueda: incluye un identificador único. "
            "Ejemplo: 'Juan Carlos Araiza Arambula RFC AAAJ830204PA9 en SAT 69-B' "
            "o 'Juan Perez fuente MEX_SANCIONADOS referencia EXP-12345'."
        )

    try:
        await log_search(
            db=db,
            user_id=current_user.id,
            query=request.query,
            ip_address="ai-intelligence",
            details={"event": "ANALYZE_ENTITY"},
        )
    except Exception:
        pass

    from app.services.intelligence_service import _build_context_payload

    return {
        "analysis": response,
        "context": _build_context_payload(context),
        "usage": {"prompt_tokens": None, "completion_tokens": None, "latency_ms": None},
        "model_version": "gpt-4-turbo",
    }


@router.get("/sessions", response_model=ChatSessionListResponse)
async def get_chat_sessions(
    skip: int = 0,
    limit: int = Query(20, le=100),
    status: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    items, total = await list_sessions(
        db=db,
        current_user=current_user,
        skip=skip,
        limit=limit,
        status=status,
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.post("/sessions", response_model=ChatSessionCreateResponse, status_code=201)
async def create_chat_session(
    payload: ChatSessionCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    session_obj = await create_session(
        db=db,
        current_user=current_user,
        title=payload.title,
        initial_context=payload.initial_context,
    )
    return session_obj


@router.patch("/sessions/{session_id}", response_model=ChatSessionCreateResponse)
async def patch_chat_session(
    session_id: int,
    payload: ChatSessionUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    session_obj = await get_session_or_404(db, session_id)
    _ensure_session_access(session_obj, current_user)
    updated = await update_session(db, session_obj, title=payload.title, status=payload.status)
    return updated


@router.delete("/sessions/{session_id}", status_code=204)
async def remove_chat_session(
    session_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Response:
    session_obj = await get_session_or_404(db, session_id)
    _ensure_session_access(session_obj, current_user)
    await delete_session(db, session_obj)
    return Response(status_code=204)


@router.get("/sessions/{session_id}/messages", response_model=ChatMessageListResponse)
async def get_chat_messages(
    session_id: int,
    skip: int = 0,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    session_obj = await get_session_or_404(db, session_id)
    _ensure_session_access(session_obj, current_user)
    items, total = await list_messages(db, session_id=session_id, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageCreateResponse, status_code=201)
async def post_chat_message(
    session_id: int,
    payload: ChatMessageCreateRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    session_obj = await get_session_or_404(db, session_id)
    _ensure_session_access(session_obj, current_user)
    result = await create_message_and_analysis(
        db=db,
        session_obj=session_obj,
        query=payload.query,
        options=payload.options,
    )
    return result


@router.post("/sessions/{session_id}/attachments", response_model=AttachmentResponse, status_code=201)
async def upload_session_attachment(
    session_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    session_obj = await get_session_or_404(db, session_id)
    _ensure_session_access(session_obj, current_user)
    attachment = await create_attachment(db=db, session_id=session_id, upload=file)
    return attachment


@router.get("/sessions/{session_id}/attachments", response_model=AttachmentListResponse)
async def get_session_attachments(
    session_id: int,
    skip: int = 0,
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    session_obj = await get_session_or_404(db, session_id)
    _ensure_session_access(session_obj, current_user)
    items, total = await list_attachments(db=db, session_id=session_id, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.post("/sessions/{session_id}/export")
async def export_session_case(
    session_id: int,
    payload: ExportRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    session_obj = await get_session_or_404(db, session_id)
    _ensure_session_access(session_obj, current_user)

    export_payload = await build_export_payload(db=db, session_obj=session_obj, include=payload.include)
    output_format = payload.format.lower()

    if output_format == "pdf":
        pdf_bytes = build_pdf_from_payload(export_payload)
        headers = {"Content-Disposition": f'attachment; filename="case_{session_id}.pdf"'}
        return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf", headers=headers)

    json_bytes = build_json_bytes(export_payload)
    headers = {"Content-Disposition": f'attachment; filename="case_{session_id}.json"'}
    return StreamingResponse(iter([json_bytes]), media_type="application/json", headers=headers)
