import json
import os
import re
import time
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, UploadFile
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_chat_attachment import AIChatAttachment
from app.models.ai_chat_message import AIChatMessage
from app.models.ai_chat_session import AIChatSession
from app.models.user import User
from app.schemas.rag_schema import AnalysisOptions
from app.services.rag.chains import get_rag_chain, is_ambiguous_query, retrieve_context


def _sanitize_text(text: str) -> str:
    return text.strip()


def _redact_pii(text: str) -> str:
    email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    phone_pattern = r"\b(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)\d{3,4}[\s-]?\d{3,4}\b"
    text = re.sub(email_pattern, "[REDACTED_EMAIL]", text)
    text = re.sub(phone_pattern, "[REDACTED_PHONE]", text)
    return text


def _build_context_payload(context_text: str) -> Dict[str, Any]:
    lines = [line.strip() for line in context_text.splitlines() if line.strip()]
    parsed_entries: List[Dict[str, Optional[str]]] = []
    current_entry: Dict[str, Optional[str]] = {
        "name": None,
        "source": None,
        "detail": None,
        "status": None,
        "risk": None,
        "evidence": None,
    }

    for line in lines:
        lowered = line.lower()
        if lowered.startswith("nombre:"):
            # New block starts when we already had a name collected.
            if current_entry.get("name"):
                parsed_entries.append(current_entry)
                current_entry = {
                    "name": None,
                    "source": None,
                    "detail": None,
                    "status": None,
                    "risk": None,
                    "evidence": None,
                }
            current_entry["name"] = line.split(":", 1)[1].strip()
        elif lowered.startswith("fuente:"):
            current_entry["source"] = line.split(":", 1)[1].strip()
        elif lowered.startswith("estado:"):
            current_entry["status"] = line.split(":", 1)[1].strip()
        elif lowered.startswith("riesgo:"):
            current_entry["risk"] = line.split(":", 1)[1].strip()
        elif lowered.startswith("evidencia:"):
            current_entry["evidence"] = line.split(":", 1)[1].strip()
        elif lowered.startswith("detalle:"):
            current_entry["detail"] = line.split(":", 1)[1].strip()

    if current_entry.get("name"):
        parsed_entries.append(current_entry)

    source_name = parsed_entries[0]["name"] if parsed_entries else None
    source_org = parsed_entries[0]["source"] if parsed_entries else None
    first_entry = parsed_entries[0] if parsed_entries else {}
    snippet_parts = [
        f"Estado: {first_entry.get('status')}" if first_entry.get("status") else None,
        f"Riesgo: {first_entry.get('risk')}" if first_entry.get("risk") else None,
        f"Evidencia: {first_entry.get('evidence')}" if first_entry.get("evidence") else None,
        first_entry.get("detail"),
    ]
    snippet = " | ".join([part for part in snippet_parts if part]) if parsed_entries else None

    related_entities: List[Dict[str, str]] = []
    seen_names = set()
    for entry in parsed_entries[:5]:
        name = (entry.get("name") or "").strip()
        source = (entry.get("source") or "").strip()
        if not name or name.lower() in seen_names:
            continue
        seen_names.add(name.lower())
        status = (entry.get("status") or "").strip()
        risk = (entry.get("risk") or "").strip()
        evidence = (entry.get("evidence") or "").strip()

        relation = "top match"
        if source:
            relation = f"top match ({source})"
        extras = []
        if status:
            extras.append(f"estado: {status}")
        if risk:
            extras.append(f"riesgo: {risk}")
        if evidence:
            extras.append(f"evidencia: {evidence}")
        if extras:
            relation = f"{relation} | {'; '.join(extras)}"
        related_entities.append(
            {
                "name": name,
                "relationship": relation,
                "type": "entity",
            }
        )

    return {
        "source": {
            "name": source_name,
            "organization": source_org,
            "date": None,
            "snippet": snippet,
            "url": None,
        }
        if any([source_name, source_org, snippet])
        else None,
        "related_entities": related_entities,
    }


def _ensure_session_access(session_obj: AIChatSession, current_user: User) -> None:
    if session_obj.user_id == current_user.id:
        return
    if current_user.is_superuser or current_user.role in ["admin", "auditor"]:
        return
    raise HTTPException(status_code=403, detail="Not authorized to access this session")


async def list_sessions(
    db: AsyncSession,
    current_user: User,
    skip: int,
    limit: int,
    status: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    base_query = select(AIChatSession)
    total_query = select(func.count()).select_from(AIChatSession)

    if not (current_user.is_superuser or current_user.role in ["admin", "auditor"]):
        base_query = base_query.where(AIChatSession.user_id == current_user.id)
        total_query = total_query.where(AIChatSession.user_id == current_user.id)

    if status:
        base_query = base_query.where(AIChatSession.status == status)
        total_query = total_query.where(AIChatSession.status == status)

    base_query = base_query.order_by(AIChatSession.updated_at.desc()).offset(skip).limit(limit)
    sessions_result = await db.execute(base_query)
    sessions = sessions_result.scalars().all()

    total = await db.scalar(total_query)
    session_items: List[Dict[str, Any]] = []
    for session_obj in sessions:
        last_message_query = (
            select(AIChatMessage.content)
            .where(AIChatMessage.session_id == session_obj.id)
            .order_by(AIChatMessage.created_at.desc())
            .limit(1)
        )
        last_message = await db.scalar(last_message_query)
        preview = (last_message[:120] + "...") if last_message and len(last_message) > 120 else last_message
        session_items.append(
            {
                "id": session_obj.id,
                "title": session_obj.title,
                "status": session_obj.status,
                "last_message_preview": preview,
                "updated_at": session_obj.updated_at,
                "created_at": session_obj.created_at,
            }
        )

    return session_items, int(total or 0)


async def create_session(
    db: AsyncSession,
    current_user: User,
    title: str,
    initial_context: Optional[Dict[str, Any]],
) -> AIChatSession:
    session_obj = AIChatSession(
        user_id=current_user.id,
        title=title.strip(),
        status="open",
        initial_context=initial_context,
    )
    db.add(session_obj)
    await db.commit()
    await db.refresh(session_obj)
    return session_obj


async def get_session_or_404(db: AsyncSession, session_id: int) -> AIChatSession:
    result = await db.execute(select(AIChatSession).where(AIChatSession.id == session_id))
    session_obj = result.scalar_one_or_none()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_obj


async def update_session(
    db: AsyncSession,
    session_obj: AIChatSession,
    title: Optional[str] = None,
    status: Optional[str] = None,
) -> AIChatSession:
    if title is not None:
        session_obj.title = title.strip()
    if status is not None:
        session_obj.status = status
    session_obj.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session_obj)
    return session_obj


async def delete_session(db: AsyncSession, session_obj: AIChatSession) -> None:
    session_obj.status = "archived"
    session_obj.updated_at = datetime.now(timezone.utc)
    await db.commit()


async def list_messages(
    db: AsyncSession,
    session_id: int,
    skip: int,
    limit: int,
) -> Tuple[List[AIChatMessage], int]:
    query = (
        select(AIChatMessage)
        .where(AIChatMessage.session_id == session_id)
        .order_by(AIChatMessage.created_at.asc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    items = result.scalars().all()

    total_query = select(func.count()).select_from(AIChatMessage).where(AIChatMessage.session_id == session_id)
    total = await db.scalar(total_query)
    return items, int(total or 0)


async def create_message_and_analysis(
    db: AsyncSession,
    session_obj: AIChatSession,
    query: str,
    options: Optional[AnalysisOptions],
) -> Dict[str, Any]:
    prompt = _sanitize_text(query)
    if options and options.redact_pii:
        prompt = _redact_pii(prompt)

    user_message = AIChatMessage(
        session_id=session_obj.id,
        role="user",
        content=prompt,
    )
    db.add(user_message)
    await db.flush()

    start_time = time.perf_counter()
    context_text = await retrieve_context(prompt)
    context_payload = _build_context_payload(context_text)
    model_name = options.model if options and options.model else "gpt-4-turbo"

    chain = get_rag_chain()
    response = await chain.ainvoke({"context": context_text, "question": prompt})

    if is_ambiguous_query(prompt, context_text):
        response = (
            f"{response}\n\n"
            "Sugerencia para mejorar la búsqueda: incluye un identificador único. "
            "Ejemplo: 'Juan Carlos Araiza Arambula RFC AAAJ830204PA9 en SAT 69-B' "
            "o 'Juan Perez fuente MEX_SANCIONADOS referencia EXP-12345'."
        )

    latency_ms = int((time.perf_counter() - start_time) * 1000)

    usage = {
        "prompt_tokens": None,
        "completion_tokens": None,
        "latency_ms": latency_ms,
    }

    assistant_message = AIChatMessage(
        session_id=session_obj.id,
        role="assistant",
        content=response,
        context=context_payload,
        usage=usage,
        model_version=model_name,
    )
    db.add(assistant_message)

    session_obj.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(assistant_message)

    return {
        "message_id": assistant_message.id,
        "analysis": assistant_message.content,
        "context": assistant_message.context,
        "usage": assistant_message.usage,
        "model_version": assistant_message.model_version,
        "created_at": assistant_message.created_at,
    }


async def create_attachment(
    db: AsyncSession,
    session_id: int,
    upload: UploadFile,
) -> AIChatAttachment:
    content = await upload.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    storage_dir = os.path.join("uploads", "ai_chat", str(session_id))
    os.makedirs(storage_dir, exist_ok=True)
    safe_name = os.path.basename(upload.filename or "attachment.bin")
    timestamp = int(time.time())
    storage_path = os.path.join(storage_dir, f"{timestamp}_{safe_name}")

    with open(storage_path, "wb") as file_obj:
        file_obj.write(content)

    attachment = AIChatAttachment(
        session_id=session_id,
        file_name=safe_name,
        mime_type=upload.content_type or "application/octet-stream",
        size=len(content),
        status="processed",
        storage_path=storage_path,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return attachment


def build_attachment_response(attachment: AIChatAttachment) -> Dict[str, Any]:
    return {
        "id": attachment.id,
        "file_name": attachment.file_name,
        "mime_type": attachment.mime_type,
        "size": attachment.size,
        "status": attachment.status,
        "file_url": f"/api/v1/intelligence/sessions/{attachment.session_id}/attachments/{attachment.id}/download",
        "created_at": attachment.created_at,
    }


async def get_attachment_or_404(
    db: AsyncSession,
    session_id: int,
    attachment_id: int,
) -> AIChatAttachment:
    query = select(AIChatAttachment).where(
        AIChatAttachment.session_id == session_id,
        AIChatAttachment.id == attachment_id,
    )
    result = await db.execute(query)
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return attachment


async def list_attachments(
    db: AsyncSession,
    session_id: int,
    skip: int,
    limit: int,
) -> Tuple[List[AIChatAttachment], int]:
    query = (
        select(AIChatAttachment)
        .where(AIChatAttachment.session_id == session_id)
        .order_by(AIChatAttachment.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    items = result.scalars().all()

    total_query = select(func.count()).select_from(AIChatAttachment).where(AIChatAttachment.session_id == session_id)
    total = await db.scalar(total_query)
    return items, int(total or 0)


async def build_export_payload(
    db: AsyncSession,
    session_obj: AIChatSession,
    include: List[str],
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "session": {
            "id": session_obj.id,
            "title": session_obj.title,
            "status": session_obj.status,
            "created_at": session_obj.created_at.isoformat() if session_obj.created_at else None,
            "updated_at": session_obj.updated_at.isoformat() if session_obj.updated_at else None,
            "initial_context": session_obj.initial_context,
        }
    }

    include_set = set(include)

    if "messages" in include_set:
        messages_query = (
            select(AIChatMessage)
            .where(AIChatMessage.session_id == session_obj.id)
            .order_by(AIChatMessage.created_at.asc())
        )
        messages_result = await db.execute(messages_query)
        messages = messages_result.scalars().all()
        payload["messages"] = [
            {
                "id": item.id,
                "role": item.role,
                "content": item.content,
                "context": item.context,
                "usage": item.usage,
                "model_version": item.model_version,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in messages
        ]

    if "metadata" in include_set:
        payload["metadata"] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "module": "intelligence",
        }

    if "sources" in include_set and "messages" in payload:
        sources = []
        for message in payload["messages"]:
            source = (message.get("context") or {}).get("source") if message.get("context") else None
            if source:
                sources.append(source)
        payload["sources"] = sources

    if "entities" in include_set and "messages" in payload:
        entities = []
        for message in payload["messages"]:
            related = (message.get("context") or {}).get("related_entities") if message.get("context") else None
            if related:
                entities.extend(related)
        payload["entities"] = entities

    return payload


def build_pdf_from_payload(payload: Dict[str, Any]) -> bytes:
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=letter)
    width, height = letter
    y = height - 50

    lines = ["AI Chat Case Export", ""]
    lines.append(f"Session ID: {payload.get('session', {}).get('id')}")
    lines.append(f"Title: {payload.get('session', {}).get('title')}")
    lines.append(f"Status: {payload.get('session', {}).get('status')}")
    lines.append("")

    for message in payload.get("messages", []):
        lines.append(f"[{message.get('role')}] {message.get('created_at')}")
        lines.append(message.get("content", ""))
        lines.append("")

    for line in lines:
        if y < 50:
            pdf.showPage()
            y = height - 50
        pdf.drawString(50, y, str(line)[:120])
        y -= 14

    pdf.save()
    output.seek(0)
    return output.read()


def build_json_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
