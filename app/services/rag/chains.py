
import logging
import re

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from app.core.config import settings
from app.services.rag.vectorstore import search_similar_entities
from app.db.session import async_session
from app.services.search_service import search_sanctions

logger = logging.getLogger(__name__)


def _normalize_search_query(question: str) -> str:
    cleaned = re.sub(r"[^\w\s]", " ", question.lower())
    tokens = [token for token in cleaned.split() if token]
    stopwords = {
        "quien", "quién", "que", "qué", "es", "el", "la", "los", "las",
        "de", "del", "y", "o", "a", "en", "un", "una", "sobre", "para",
        "me", "dime", "analiza", "analizar", "riesgo", "riesgos", "cual", "cuál",
    }
    filtered = [token for token in tokens if token not in stopwords and len(token) > 1]

    if filtered:
        return " ".join(filtered[:3])
    return question.strip()


def _extract_sat_status(program: str, remarks: str) -> str:
    status_candidates = [program or "", remarks or ""]
    lowered = " ".join(status_candidates).lower()

    if "definit" in lowered:
        return "Definitivo"
    if "presunt" in lowered:
        return "Presunto"
    if "desvirt" in lowered:
        return "Desvirtuado"
    if "sentencia" in lowered and "favorable" in lowered:
        return "Sentencia favorable"
    return "No identificado"


def _derive_risk_level(source: str, program: str, remarks: str) -> str:
    source_name = (source or "").upper()
    status = _extract_sat_status(program, remarks).lower()

    if source_name == "SAT_69B":
        if "definit" in status:
            return "alto"
        if "presunt" in status:
            return "medio"
        if "desvirt" in status or "sentencia" in status:
            return "bajo"
        return "indeterminado"

    if source_name in {"UN_CONSOLIDATED", "MEX_SANCIONADOS"}:
        return "alto"

    return "indeterminado"

# Prompt designed to reduce hallucinations
RAG_PROMPT = """
Eres un analista experto en PLD/FT y cumplimiento financiero.

Responde la consulta basándote ÚNICAMENTE en el contexto proporcionado.
No inventes hechos, causas legales ni identificadores.
Si falta información, dilo explícitamente.

Objetivo de salida (en español, máximo 220 palabras):
1) Resultado de screening (coincidencia probable / no concluyente / sin coincidencias).
2) Fundamentación factual por fuente (ONU, MEX_SANCIONADOS, SAT_69B) indicando estatus y detalle relevante.
3) Evaluación de riesgo breve (alto/medio/bajo) con cautela si hay ambigüedad.
4) Fuentes consultadas con evidencia, usando el formato: [FUENTE|EVIDENCIA].

Reglas críticas:
- Si la consulta es ambigua o hay homónimos, indícalo y solicita identificador único (RFC, referencia, fecha de nacimiento).
- Para SAT 69-B, distingue explícitamente Presunto, Definitivo, Desvirtuado y Sentencia favorable.
- No afirmes delitos; limita la redacción a estatus administrativo y hallazgos del contexto.

Contexto:
{context}

Consulta: {question}
"""

async def retrieve_context(question: str):
    """
    Retrieve context from sanctions (primary source) and entity_documents (secondary source).
    """
    context_chunks = []
    sanction_query = _normalize_search_query(question)

    # 1) Primary source: sanctions table (official records)
    try:
        async with async_session() as db:
            sanction_results = await search_sanctions(db=db, query=sanction_query, limit=8)

        for entry in sanction_results:
            sanction = entry.get("sanction") if isinstance(entry, dict) else entry
            if sanction is None:
                continue

            details = []
            if sanction.program:
                details.append(f"Programa: {sanction.program}")
            if sanction.reference_number:
                details.append(f"Referencia: {sanction.reference_number}")
            if sanction.rfc:
                details.append(f"RFC: {sanction.rfc}")
            if sanction.listed_on:
                details.append(f"Publicado: {sanction.listed_on}")
            if sanction.remarks:
                details.append(f"Observaciones: {str(sanction.remarks)[:280]}")

            sat_status = _extract_sat_status(str(sanction.program or ""), str(sanction.remarks or ""))
            risk_level = _derive_risk_level(
                source=str(sanction.source or ""),
                program=str(sanction.program or ""),
                remarks=str(sanction.remarks or ""),
            )
            evidence_id = sanction.reference_number or sanction.rfc or sanction.data_id or "N/A"

            detail_text = " | ".join(details) if details else "Sin detalle adicional disponible."
            context_chunks.append(
                f"Nombre: {sanction.entity_name}\n"
                f"Fuente: {sanction.source}\n"
                f"Estado: {sat_status}\n"
                f"Riesgo: {risk_level}\n"
                f"Evidencia: {evidence_id}\n"
                f"Detalle: {detail_text}"
            )
    except Exception as exc:
        logger.warning(f"Failed to retrieve sanctions context: {exc}")

    # 2) Secondary source: curated/manual entity documents
    try:
        entity_docs = await search_similar_entities(question, limit=3)
        for doc in entity_docs:
            context_chunks.append(
                f"Nombre: {doc.name}\n"
                f"Fuente: {doc.source}\n"
                f"Estado: Documento contextual\n"
                f"Riesgo: indeterminado\n"
                f"Evidencia: ENTITY_DOC\n"
                f"Detalle: {str(doc.content)[:320]}"
            )
    except Exception as exc:
        logger.warning(f"Failed to retrieve entity_documents context: {exc}")

    if not context_chunks:
        return "No hay registros encontrados."

    return "\n\n".join(context_chunks)

def is_ambiguous_query(question: str, context_text: str) -> bool:
    normalized = _normalize_search_query(question)
    informative_tokens = [token for token in normalized.split() if token]
    match_count = context_text.lower().count("nombre:")
    return len(informative_tokens) <= 1 and match_count >= 3

def get_rag_chain():
    llm = ChatOpenAI(model="gpt-4-turbo", temperature=0, api_key=settings.OPENAI_API_KEY)
    prompt = ChatPromptTemplate.from_template(RAG_PROMPT)
    
    # We construct the chain manually to handle the async retrieval
    # In a full LangChain setup, we would wrap search_similar_entities in a Retriever
    
    chain = (
        prompt
        | llm
        | StrOutputParser()
    )
    return chain
