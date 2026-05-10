
from typing import Any, Optional

import os

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, HTTPException
from fastapi.responses import FileResponse
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
    build_attachment_response,
    build_export_payload,
    build_json_bytes,
    build_pdf_from_payload,
    create_attachment,
    create_message_and_analysis,
    create_session,
    delete_session,
    get_attachment_or_404,
    get_session_or_404,
    list_attachments,
    list_messages,
    list_sessions,
    update_session,
)
from app.services.rag.chains import (
    build_match_correction,
    context_has_target_match,
    get_rag_chain,
    is_ambiguous_query,
    response_indicates_no_match,
    retrieve_context,
)

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
    context_text, context_metadata = await retrieve_context(request.query)
    needs_clarification = context_metadata.get("needs_clarification", False)
    
    chain = get_rag_chain()
    ambiguity_alert = ""
    if needs_clarification:
        match_tiers = context_metadata.get("match_tiers", {})
        clarification_suggestions = context_metadata.get("clarification_suggestions", [])
        ambiguity_alert = (
            "\n\nAMBIGUEDAD DETECTADA:\n"
            f"- Se encontraron {len(match_tiers.get('exact', []))} coincidencias exactas, "
            f"{len(match_tiers.get('strong', []))} fuertes, "
            f"{len(match_tiers.get('weak', []))} débiles\n"
            "- Se sugiere al usuario proporcionar: " + ", ".join(clarification_suggestions)
        )
    
    response = await chain.ainvoke({
        "context": context_text,
        "question": request.query,
        "ambiguity_alert": ambiguity_alert,
    })

    if response_indicates_no_match(response) and context_has_target_match(request.query, context_text):
        correction = build_match_correction(request.query, context_text)
        if correction:
            response = correction

    if needs_clarification:
        response = (
            f"{response}\n\n"
            "**Sugerencia para mejorar la búsqueda:** Incluye un identificador único. "
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
    return build_attachment_response(attachment)


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
    return {
        "items": [build_attachment_response(item) for item in items],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/sessions/{session_id}/attachments/{attachment_id}/download")
async def download_session_attachment(
    session_id: int,
    attachment_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    session_obj = await get_session_or_404(db, session_id)
    _ensure_session_access(session_obj, current_user)

    attachment = await get_attachment_or_404(
        db=db,
        session_id=session_id,
        attachment_id=attachment_id,
    )
    if not os.path.exists(attachment.storage_path):
        raise HTTPException(status_code=404, detail="Stored file not found")

    return FileResponse(
        path=attachment.storage_path,
        media_type=attachment.mime_type,
        filename=attachment.file_name,
    )


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
        return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)

    json_bytes = build_json_bytes(export_payload)
    headers = {"Content-Disposition": f'attachment; filename="case_{session_id}.json"'}
    return Response(content=json_bytes, media_type="application/json", headers=headers)
