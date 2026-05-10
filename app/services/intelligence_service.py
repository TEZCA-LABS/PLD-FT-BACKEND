import json
import os
import re
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, UploadFile
from fpdf import FPDF, XPos, YPos
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_chat_attachment import AIChatAttachment
from app.models.ai_chat_message import AIChatMessage
from app.models.ai_chat_session import AIChatSession
from app.models.user import User
from app.schemas.rag_schema import AnalysisOptions
from app.services.rag.chains import (
    build_match_correction,
    context_has_target_match,
    get_rag_chain,
    is_ambiguous_query,
    response_indicates_no_match,
    retrieve_context,
)


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
    
    # Retrieve context and ambiguity metadata
    context_text, context_metadata = await retrieve_context(prompt)
    context_payload = _build_context_payload(context_text)
    model_name = options.model if options and options.model else "gpt-4-turbo"
    
    # Extract ambiguity info from metadata
    needs_clarification = context_metadata.get("needs_clarification", False)
    specificity_score = context_metadata.get("specificity_score", 0.5)
    match_tiers = context_metadata.get("match_tiers", {})
    clarification_suggestions = context_metadata.get("clarification_suggestions", [])

    # Build ambiguity alert for LLM if needed
    ambiguity_alert = ""
    if needs_clarification and (match_tiers.get("weak") or match_tiers.get("semantic")):
        ambiguity_alert = (
            "\n\nAMBIGUEDAD DETECTADA:\n"
            f"- La consulta es genérica (especificidad: {specificity_score})\n"
            f"- Se encontraron {len(match_tiers.get('exact', []))} coincidencias exactas, "
            f"{len(match_tiers.get('strong', []))} fuertes, "
            f"{len(match_tiers.get('weak', []))} débiles\n"
            "- Se sugiere al usuario proporcionar: " + ", ".join(clarification_suggestions)
        )

    chain = get_rag_chain()
    response = await chain.ainvoke({
        "context": context_text,
        "question": prompt,
        "ambiguity_alert": ambiguity_alert,
    })

    if response_indicates_no_match(response) and context_has_target_match(prompt, context_text):
        correction = build_match_correction(prompt, context_text)
        if correction:
            response = correction

    # Improved ambiguity handling with new metadata
    if needs_clarification:
        response = (
            f"{response}\n\n"
            "**Sugerencia para mejorar la búsqueda:** Incluye un identificador único. "
            "Ejemplo: 'Juan Carlos Araiza Arambula RFC AAAJ830204PA9 en SAT 69-B' "
            "o 'Juan Perez fuente MEX_SANCIONADOS referencia EXP-12345'."
        )

    latency_ms = int((time.perf_counter() - start_time) * 1000)

    usage = {
        "prompt_tokens": None,
        "completion_tokens": None,
        "latency_ms": latency_ms,
    }
    
    # Determine confidence level based on match quality - must be valid enum value
    if match_tiers.get("exact"):
        confidence_level = "high"
    elif match_tiers.get("strong"):
        confidence_level = "medium"
    else:
        confidence_level = "low"

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
        "confidence": confidence_level,
        "ambiguity_detected": needs_clarification,
        "suggested_refinements": clarification_suggestions,
        "match_tiers": match_tiers,
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


class CasePDF(FPDF):
    """Custom PDF class for AI Chat case export with professional formatting"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.page_count = 0
        self.title_y = 0
        self.toc_y = 0
        
    def header(self):
        """Render PDF header on each page"""
        # Header background
        self.set_fill_color(26, 66, 122)  # #1a427a
        self.rect(0, 0, 210, 25, 'F')
        
        # Header text
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 16)
        self.set_xy(10, 8)
        self.cell(0, 8, 'Asistente de Cumplimiento IA', ln=True)
        
        self.set_font('Helvetica', '', 10)
        self.set_xy(10, 16)
        self.cell(0, 6, 'Exportacion de Caso - Analisis de Entidades', ln=True)
        
        # Reset text color and position for content
        self.set_text_color(0, 0, 0)
        self.set_xy(10, 32)

    
    def footer(self):
        """Render PDF footer on each page"""
        self.set_y(-15)
        
        # Classification banner
        self.set_fill_color(220, 38, 38)  # Red for classification
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 8)
        self.cell(0, 4, 'CLASIFICACION: CONFIDENCIAL', 0, 1, 'C', True)
        
        # Page number
        self.set_text_color(100, 116, 139)  # Gray
        self.set_font('Helvetica', '', 8)
        self.cell(0, 4, f'Pagina {self.page_no()}', 0, 0, 'C')


def _format_datetime(dt_string: str) -> str:
    """Format ISO datetime string to readable format"""
    try:
        dt = datetime.fromisoformat(str(dt_string).replace('Z', '+00:00'))
        return dt.strftime('%d/%m/%Y %H:%M:%S')
    except Exception:
        return str(dt_string)[:20]


def _wrap_text(text: str, max_length: int = 100) -> str:
    """Wrap text to max length"""
    if text is None:
        return 'N/A'
    text = str(text)
    if len(text) <= max_length:
        return text
    return text[:max_length] + '...'


def _normalize_text(value: Any, default: str = 'N/A') -> str:
    """Normalize optional values for PDF rendering."""
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _split_text_to_width(pdf: FPDF, text: Any, width: float) -> List[str]:
    """Split text into lines that fit the given cell width."""
    normalized = _normalize_text(text)
    max_width = max(width - 2, 1)
    lines: List[str] = []

    for paragraph in normalized.split('\n'):
        words = paragraph.split(' ')
        if not words:
            lines.append('')
            continue

        current = ''
        for word in words:
            candidate = word if not current else f'{current} {word}'
            if pdf.get_string_width(candidate) <= max_width:
                current = candidate
                continue

            if current:
                lines.append(current)
                current = ''

            if pdf.get_string_width(word) <= max_width:
                current = word
                continue

            # Hard-wrap words without spaces.
            chunk = ''
            for char in word:
                test_chunk = f'{chunk}{char}'
                if pdf.get_string_width(test_chunk) <= max_width:
                    chunk = test_chunk
                else:
                    if chunk:
                        lines.append(chunk)
                    chunk = char
            current = chunk

        if current:
            lines.append(current)

    if not lines:
        return ['']
    return lines


def _draw_table_row(
    pdf: FPDF,
    col_widths: List[float],
    values: List[Any],
    line_h: float = 3.5,
    fill: bool = False,
    aligns: Optional[List[str]] = None,
) -> None:
    """Draw a table row with dynamic height so full text is always visible."""
    if aligns is None:
        aligns = ['L'] * len(col_widths)

    row_lines = [_split_text_to_width(pdf, value, col_widths[idx]) for idx, value in enumerate(values)]
    max_lines = max(len(lines) for lines in row_lines) if row_lines else 1
    row_height = max_lines * line_h

    if pdf.get_y() + row_height > pdf.page_break_trigger:
        pdf.add_page()

    x_start = pdf.get_x()
    y_start = pdf.get_y()

    for idx, width in enumerate(col_widths):
        cell_text = '\n'.join(row_lines[idx])
        x = pdf.get_x()
        y = pdf.get_y()
        pdf.multi_cell(
            width,
            line_h,
            cell_text,
            border=1,
            align=aligns[idx],
            fill=fill,
            new_x=XPos.RIGHT,
            new_y=YPos.TOP,
        )
        pdf.set_xy(x + width, y)

    pdf.set_xy(x_start, y_start + row_height)


def build_pdf_from_payload(payload: Dict[str, Any]) -> bytes:
    """
    Build professional PDF from export payload using FPDF2.
    
    Generates a structured PDF with:
    - Professional header with branding (blue color scheme)
    - Session information section
    - Executive summary from first 3 messages
    - Complete conversation/analysis
    - Sources and entities tables
    - Document metadata
    - Proper UTF-8 encoding for special characters (á, é, í, ó, ú, ñ)
    - Classification footer on each page
    
    Args:
        payload: Dictionary with session, messages, sources, entities, metadata
        
    Returns:
        bytes: PDF file content
    """
    try:
        pdf = CasePDF()
        pdf.set_margins(left=15, top=20, right=15)
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()
        
        # Extract data
        session_data = payload.get("session", {})
        messages_data = payload.get("messages", [])
        sources_data = payload.get("sources", [])
        entities_data = payload.get("entities", [])
        metadata_data = payload.get("metadata", {})
        
        # ===== TITLE PAGE =====
        pdf.set_font('Helvetica', 'B', 20)
        pdf.set_text_color(26, 66, 122)
        pdf.ln(15)
        pdf.cell(0, 10, 'CASO DE ANALISIS', 0, 1, 'C')
        pdf.cell(0, 10, 'Asistente de Cumplimiento IA', 0, 1, 'C')
        
        pdf.ln(10)
        pdf.set_font('Helvetica', '', 11)
        pdf.set_text_color(0, 0, 0)
        
        # Session info on title page
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(40, 7, 'Titulo:', 0, 0)
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(0, 7, session_data.get('title', 'Sin titulo'), 0, 1)
        
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(40, 7, 'ID Sesion:', 0, 0)
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(0, 7, str(session_data.get('id', 'N/A')), 0, 1)
        
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(40, 7, 'Estado:', 0, 0)
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(0, 7, session_data.get('status', 'N/A'), 0, 1)
        
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(40, 7, 'Creada:', 0, 0)
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(0, 7, _format_datetime(session_data.get('created_at', '')), 0, 1)
        
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(40, 7, 'Generada:', 0, 0)
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(0, 7, _format_datetime(metadata_data.get('generated_at', '')), 0, 1)
        
        # Classification
        pdf.ln(15)
        pdf.set_fill_color(254, 243, 199)
        pdf.set_text_color(120, 53, 15)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 8, 'CLASIFICACION: INFORMACION CONFIDENCIAL', 0, 1, 'C', True)
        
        # ===== TABLE OF CONTENTS =====
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(26, 66, 122)
        pdf.cell(0, 10, 'TABLA DE CONTENIDOS', 0, 1)
        
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(5)
        
        toc_items = ['1. Analisis Detallado']
        next_section = 2

        if sources_data:
            toc_items.append(f'{next_section}. Fuentes Identificadas')
            next_section += 1
        if entities_data:
            toc_items.append(f'{next_section}. Entidades Relacionadas')
            next_section += 1

        toc_items.append(f'{next_section}. Informacion del Documento')
        
        for item in toc_items:
            pdf.cell(0, 7, f'  {item}', 0, 1)
        
        # ===== SECTION 1: DETAILED ANALYSIS =====
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(26, 66, 122)
        pdf.cell(0, 10, '1. ANALISIS DETALLADO', 0, 1)
        
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 8, 'Conversacion Completa', 0, 1)
        
        pdf.set_font('Helvetica', '', 9)
        pdf.ln(2)
        
        for idx, msg in enumerate(messages_data, 1):
            # Message header
            role_label = '[Consulta]' if msg.get('role') == 'user' else '[Respuesta]'
            timestamp = _format_datetime(msg.get('created_at', ''))
            
            # Background color based on role
            if msg.get('role') == 'user':
                pdf.set_fill_color(224, 231, 255)
            else:
                pdf.set_fill_color(219, 234, 254)
            
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_text_color(26, 66, 122)
            pdf.multi_cell(
                0,
                6,
                f'{role_label} [{timestamp}]',
                border=0,
                align='L',
                fill=True,
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )
            
            # Message content
            pdf.set_font('Helvetica', '', 8)
            pdf.set_text_color(0, 0, 0)
            
            content = msg.get('content', '')
            paragraphs = content.split('\n')
            for para in paragraphs:
                if para.strip():
                    pdf.multi_cell(
                        0,
                        4,
                        para.strip(),
                        border=0,
                        align='L',
                        new_x=XPos.LMARGIN,
                        new_y=YPos.NEXT,
                    )
            
            pdf.ln(1)
            
            # Check if we need a new page
            if pdf.get_y() > 250:
                pdf.add_page()
        
        # ===== SECTION 2+: SOURCES =====
        if sources_data:
            pdf.add_page()
            sources_section_num = 2
            pdf.set_font('Helvetica', 'B', 14)
            pdf.set_text_color(26, 66, 122)
            pdf.cell(0, 10, f'{sources_section_num}. FUENTES IDENTIFICADAS', 0, 1)
            
            pdf.set_font('Helvetica', '', 8)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(3)
            
            # Table header
            col_width = [45, 45, 40, 40]
            headers = ['Fuente', 'Organizacion', 'Fecha', 'Referencia']
            
            pdf.set_fill_color(26, 66, 122)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Helvetica', 'B', 8)
            
            for i, header in enumerate(headers):
                pdf.cell(col_width[i], 6, header, 1, 0, 'C', True)
            pdf.ln()
            
            # Table rows
            pdf.set_fill_color(248, 250, 252)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font('Helvetica', '', 7)
            
            for idx, source in enumerate(sources_data):
                fill_row = idx % 2 == 0
                row_values = [
                    _normalize_text(source.get('name')),
                    _normalize_text(source.get('organization')),
                    _normalize_text(source.get('date')),
                    _normalize_text(source.get('url')),
                ]
                _draw_table_row(
                    pdf,
                    col_width,
                    row_values,
                    line_h=3.5,
                    fill=fill_row,
                    aligns=['L', 'L', 'L', 'L'],
                )
        
        # ===== SECTION 2+/3+: ENTITIES =====
        if entities_data:
            pdf.add_page()
            section_num = 3 if sources_data else 2
            pdf.set_font('Helvetica', 'B', 14)
            pdf.set_text_color(26, 66, 122)
            pdf.cell(0, 10, f'{section_num}. ENTIDADES RELACIONADAS', 0, 1)
            
            pdf.set_font('Helvetica', '', 8)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(3)
            
            # Table header
            col_width = [55, 55, 50]
            headers = ['Entidad', 'Relacion', 'Tipo']
            
            pdf.set_fill_color(26, 66, 122)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Helvetica', 'B', 8)
            
            for i, header in enumerate(headers):
                pdf.cell(col_width[i], 6, header, 1, 0, 'C', True)
            pdf.ln()
            
            # Table rows
            pdf.set_fill_color(248, 250, 252)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font('Helvetica', '', 7)
            
            for idx, entity in enumerate(entities_data):
                name = entity.get('name') or entity.get('entity_name') or 'N/A'
                relation = entity.get('relation') or entity.get('relationship') or 'N/A'
                etype = entity.get('type') or 'domain'

                _draw_table_row(
                    pdf,
                    col_width,
                    [_normalize_text(name), _normalize_text(relation), _normalize_text(etype)],
                    line_h=3.5,
                    fill=idx % 2 == 0,
                    aligns=['L', 'L', 'L'],
                )
        
        # ===== FINAL SECTION: METADATA =====
        pdf.add_page()
        final_section = len(toc_items)
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(26, 66, 122)
        pdf.cell(0, 10, f'{final_section}. INFORMACION DEL DOCUMENTO', 0, 1)
        
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(5)
        
        # Metadata box
        pdf.set_fill_color(241, 245, 249)
        pdf.cell(0, 7, 'Metadatos de Generacion', 0, 1, fill=True)
        
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(50, 6, 'Modulo:', 0, 0)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, metadata_data.get('module') or 'N/A', 0, 1)
        
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(50, 6, 'Fecha Generacion:', 0, 0)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, _format_datetime(metadata_data.get('generated_at', '')), 0, 1)
        
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(50, 6, 'Total de Mensajes:', 0, 0)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, str(len(messages_data)), 0, 1)
        
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(50, 6, 'Fuentes Identificadas:', 0, 0)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, str(len(sources_data)), 0, 1)
        
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(50, 6, 'Entidades Relacionadas:', 0, 0)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, str(len(entities_data)), 0, 1)
        
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(50, 6, 'Clasificacion:', 0, 0)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, 'CONFIDENCIAL', 0, 1)
        
        pdf.ln(10)
        pdf.set_font('Helvetica', 'I', 8)
        pdf.set_text_color(100, 116, 139)
        pdf.multi_cell(180, 4, 
            'Este documento es confidencial y esta destinado exclusivamente para uso interno.\n' +
            'Su distribucion sin autorizacion esta prohibida.',
            border=0, align='C')
        
        # Get PDF content as bytes
        pdf_output = pdf.output()
        
        return bytes(pdf_output)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error generating PDF: {str(e)}"
        )


def build_json_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
