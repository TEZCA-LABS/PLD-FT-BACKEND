
import logging
import re
import unicodedata

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.core.config import settings
from app.services.rag.vectorstore import search_similar_entities
from app.db.session import async_session
from app.services.search_service import search_sanctions

logger = logging.getLogger(__name__)

NEGATIVE_MATCH_PHRASES = (
    "sin coincidencias",
    "no se encontró",
    "no se encontro",
    "sin resultados",
    "no hay coincidencias",
    "sin hallazgos",
)

# Domain-aware expansions for ambiguous/generic search terms
AMBIGUOUS_TERM_MAPPINGS = {
    "trading": ["commercial", "import", "export", "goods", "commerce", "business", "comercio"],
    "group": ["holding", "subsidiary", "parent", "cluster", "corporacion", "grupo"],
    "company": ["entity", "organization", "enterprise", "sociedad", "empresa"],
    "llc": ["limited", "liability", "limited liability", "empresa"],
    "corp": ["corporation", "corporate", "corporacion", "empresa"],
    "import": ["import-export", "trading", "commerce", "goods"],
    "export": ["import-export", "trading", "commerce", "goods"],
    "finance": ["financial", "financing", "credit", "funding", "financiero"],
    "bank": ["banking", "financial", "credit", "institution", "bancario"],
    "consulting": ["consultant", "consultancy", "advisory", "services"],
}


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value or "")
    no_accents = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return no_accents.lower().strip()


def _tokenize(value: str) -> list[str]:
    cleaned = re.sub(r"[^\w\s]", " ", _normalize_text(value))
    return [token for token in cleaned.split() if len(token) > 1]


def _extract_target_entity_phrase(question: str) -> str:
    patterns = [
        r"(?i)\bsi\s+(.+?)\s+se\s+encuentra\b",
        r"(?i)\bsi\s+(.+?)\s+esta\b",
        r"(?i)\b(?:identifica|verifica|busca|consulta)\s+si\s+(.+?)\s+en\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, question)
        if not match:
            continue
        candidate = match.group(1).strip(" .,:;¿?\"'")
        if len(candidate.split()) >= 2:
            return candidate

    uppercase_match = re.search(r"\b[A-ZÁÉÍÓÚÑ]+(?:\s+[A-ZÁÉÍÓÚÑ]+){1,5}\b", question)
    if uppercase_match:
        return uppercase_match.group(0).strip()

    return ""


def _normalize_search_query(question: str) -> str:
    cleaned = re.sub(r"[^\w\s]", " ", _normalize_text(question))
    tokens = [token for token in cleaned.split() if token]
    stopwords = {
        "quien", "quién", "que", "qué", "es", "el", "la", "los", "las",
        "de", "del", "y", "o", "a", "en", "un", "una", "sobre", "para",
        "me", "dime", "analiza", "analizar", "riesgo", "riesgos", "cual", "cuál",
        "identifica", "encuentra", "lista", "busca", "muestra", "obtiene", "extrae",
        "verifica", "valida", "genera", "ordena", "revisa", "se", "encuentra",
        "alguna", "algunas", "listas", "lista",
    }
    filtered = [token for token in tokens if token not in stopwords and len(token) > 1]

    if filtered:
        return " ".join(filtered[:4])
    return question.strip()


def query_specificity_score(question: str) -> float:
    """
    Calculate how specific/unique a query is (0.0 = very generic, 1.0 = very specific).
    
    Factors:
    - Number of informative tokens (higher = more specific)
    - Presence of identifying info like RFC, dates, numbers (higher = more specific)
    - Generic term presence (lower = more specific)
    """
    normalized = _normalize_search_query(question)
    tokens = [t for t in normalized.split() if t]
    
    # Base score from token count
    base_score = min(len(tokens) / 5, 1.0)  # 5+ tokens = maximum
    
    # Boost for specific identifiers (RFC, dates, numbers)
    identifier_patterns = [
        r"\b[A-Z]{4}\d{6}[A-Z0-9]{3}\b",  # RFC format
        r"\d{1,2}[-/]\d{1,2}[-/]\d{4}",    # Date format
        r"RFC\b",
        r"SAT",
        r"OFAC",
    ]
    has_identifier = any(re.search(pattern, question, re.IGNORECASE) for pattern in identifier_patterns)
    if has_identifier:
        base_score = min(base_score + 0.3, 1.0)
    
    # Penalty for generic terms
    generic_keywords = set(AMBIGUOUS_TERM_MAPPINGS.keys())
    normalized_tokens = set(_normalize_text(t) for t in tokens)
    generic_count = len(normalized_tokens & generic_keywords)
    
    if generic_count > 0 and len(tokens) <= 2:
        base_score = max(base_score - 0.4, 0.0)
    
    return round(base_score, 2)


def expand_ambiguous_query(question: str) -> list[str]:
    """
    Expand generic/ambiguous terms to create additional search candidates.
    
    Returns a list of expanded terms to add to search candidates.
    Example: "TRADING" -> ["commercial", "import", "export", "goods", "commerce"]
    """
    expansions: list[str] = []
    cleaned = re.sub(r"[^\w\s]", " ", _normalize_text(question))
    tokens = [token for token in cleaned.split() if token and len(token) > 1]
    
    for token in tokens:
        normalized_token = _normalize_text(token)
        if normalized_token in AMBIGUOUS_TERM_MAPPINGS:
            # Add all expansions for this generic term
            expansions.extend(AMBIGUOUS_TERM_MAPPINGS[normalized_token])
    
    # Remove duplicates and return
    return list(set(expansions))


def _build_search_candidates(question: str) -> list[str]:
    target_entity = _extract_target_entity_phrase(question)
    target_normalized = _normalize_search_query(target_entity) if target_entity else ""
    normalized = _normalize_search_query(question)
    cleaned = re.sub(r"[^\w\s]", " ", _normalize_text(question))
    tokens = [token for token in cleaned.split() if len(token) > 1]

    # Prioritize extracted entity phrase first, then broader query and token fallbacks.
    candidates: list[str] = []
    if target_entity:
        candidates.append(_normalize_text(target_entity))
    if target_normalized and target_normalized not in candidates:
        candidates.append(target_normalized)
    if normalized:
        candidates.append(normalized)

    raw = _normalize_text(question.strip())
    if raw and raw not in candidates:
        candidates.append(raw)

    # Add domain-aware expansions if query is ambiguous
    ambiguous_expansions = expand_ambiguous_query(question)
    candidates.extend(ambiguous_expansions)

    for token in tokens:
        if token not in candidates:
            candidates.append(token)

    return candidates[:12]


def _extract_context_entries(context_text: str) -> list[dict[str, str]]:
    """Parse context text into structured entries with key-value pairs."""
    if not context_text:
        return []

    entries: list[dict[str, str]] = []
    blocks = [block.strip() for block in context_text.split("\n\n") if block.strip()]
    for block in blocks:
        entry: dict[str, str] = {}
        for line in block.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            entry[_normalize_text(key)] = value.strip()
        if entry.get("nombre"):
            entries.append(entry)
    return entries


def _has_target_match_in_name(target: str, name: str) -> bool:
    target_tokens = set(_tokenize(target))
    name_tokens = set(_tokenize(name))
    if not target_tokens or not name_tokens:
        return False

    if _normalize_text(target) in _normalize_text(name) or _normalize_text(name) in _normalize_text(target):
        return True

    common_tokens = target_tokens.intersection(name_tokens)
    min_common = 2 if len(target_tokens) <= 3 else 3
    return len(common_tokens) >= min_common


def context_has_target_match(question: str, context_text: str) -> bool:
    target = _extract_target_entity_phrase(question) or question
    entries = _extract_context_entries(context_text)
    return any(_has_target_match_in_name(target, entry.get("nombre", "")) for entry in entries)


def response_indicates_no_match(response_text: str) -> bool:
    normalized = _normalize_text(response_text)
    return any(phrase in normalized for phrase in NEGATIVE_MATCH_PHRASES)


def build_match_correction(question: str, context_text: str) -> str:
    target = _extract_target_entity_phrase(question) or question
    entries = _extract_context_entries(context_text)
    matching_entry = next(
        (entry for entry in entries if _has_target_match_in_name(target, entry.get("nombre", ""))),
        None,
    )
    if not matching_entry:
        return ""

    name = matching_entry.get("nombre", target)
    source = matching_entry.get("fuente", "N/A")
    evidence = matching_entry.get("evidencia", "N/A")
    status = matching_entry.get("estado", "No identificado")
    risk = matching_entry.get("riesgo", "indeterminado")

    return (
        "1) Resultado de screening: Coincidencia probable.\n"
        f"2) Fundamentación factual por fuente: Se identificó el registro '{name}' en la fuente {source} con estatus '{status}'.\n"
        f"3) Evaluación de riesgo: {risk.capitalize()}, con base en la evidencia recuperada en la fuente oficial.\n"
        f"4) Fuentes consultadas con evidencia: [{source}|{evidence}]"
    )


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

# Prompt designed to reduce hallucinations and handle ambiguity
RAG_PROMPT = """
Eres un analista experto en PLD/FT y cumplimiento financiero.

Responde la consulta basándote ÚNICAMENTE en el contexto proporcionado.
No inventes hechos, causas legales ni identificadores.
Si falta información, dilo explícitamente.

{ambiguity_alert}

Objetivo de salida (en español, máximo 220 palabras):
1) Resultado de screening (coincidencia probable / no concluyente / sin coincidencias).
2) Fundamentación factual por fuente (ONU, MEX_SANCIONADOS, SAT_69B) indicando estatus y detalle relevante.
3) Evaluación de riesgo breve (alto/medio/bajo) con cautela si hay ambigüedad.
4) Fuentes consultadas con evidencia, usando el formato: [FUENTE|EVIDENCIA].

Reglas críticas:
- Si la consulta es ambigua o hay homónimos, indícalo y solicita identificador único (RFC, referencia, fecha de nacimiento).
- Para SAT 69-B, distingue explícitamente Presunto, Definitivo, Desvirtuado y Sentencia favorable.
- No afirmes delitos; limita la redacción a estatus administrativo y hallazgos del contexto.
- Si se detecta ambigüedad (ver alerta arriba), prioriza una recomendación clara para refinar la búsqueda.

Contexto:
{context}

Consulta: {question}
"""

async def retrieve_context(question: str):
    """
    Retrieve context from sanctions (primary source) and entity_documents (secondary source).
    
    Returns:
        Tuple of (context_text: str, metadata: dict) where metadata contains:
        - needs_clarification: bool
        - specificity_score: float
        - match_tiers: dict with exact/strong/weak/semantic lists
    """
    context_chunks = []
    specificity = query_specificity_score(question)
    is_ambiguous = specificity < 0.4
    match_tiers = {
        "exact": [],
        "strong": [],
        "weak": [],
        "semantic": [],
    }
    search_candidates = _build_search_candidates(question)

    # 1) Primary source: sanctions table (official records)
    try:
        sanction_results = []
        seen_sanction_ids = set()

        async with async_session() as db:
            for idx, candidate in enumerate(search_candidates):
                # Enable extended field search for ambiguous queries
                candidate_results = await search_sanctions(
                    db=db,
                    query=candidate,
                    limit=8,
                    is_ambiguous=is_ambiguous,
                    search_extended_fields=is_ambiguous,
                )

                for entry in candidate_results:
                    sanction = entry.get("sanction") if isinstance(entry, dict) else entry
                    if sanction is None or sanction.id in seen_sanction_ids:
                        continue
                    seen_sanction_ids.add(sanction.id)
                    sanction_results.append(entry)

                # Avoid stopping on generic first candidates; allow broader retrieval first.
                if len(sanction_results) >= 12 and idx >= 2:
                    break

        # Organize results into tiers
        for entry in sanction_results:
            sanction = entry.get("sanction") if isinstance(entry, dict) else entry
            score = entry.get("score", 0.5) if isinstance(entry, dict) else 0.5
            
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
            context_entry = (
                f"Nombre: {sanction.entity_name}\n"
                f"Fuente: {sanction.source}\n"
                f"Estado: {sat_status}\n"
                f"Riesgo: {risk_level}\n"
                f"Evidencia: {evidence_id}\n"
                f"Detalle: {detail_text}"
            )
            
            context_chunks.append(context_entry)
            
            # Classify into tiers based on match score
            tier_data = {
                "name": sanction.entity_name,
                "source": sanction.source,
                "evidence_id": evidence_id,
                "score": score,
            }
            
            if score >= 0.9:
                match_tiers["exact"].append(tier_data)
            elif score >= 0.7:
                match_tiers["strong"].append(tier_data)
            elif score >= 0.5:
                match_tiers["weak"].append(tier_data)
            else:
                match_tiers["semantic"].append(tier_data)
                
    except Exception as exc:
        logger.warning(f"Failed to retrieve sanctions context: {exc}")

    # 2) Secondary source: curated/manual entity documents
    try:
        entity_docs = await search_similar_entities(question, limit=3)
        for doc in entity_docs:
            context_entry = (
                f"Nombre: {doc.name}\n"
                f"Fuente: {doc.source}\n"
                f"Estado: Documento contextual\n"
                f"Riesgo: indeterminado\n"
                f"Evidencia: ENTITY_DOC\n"
                f"Detalle: {str(doc.content)[:320]}"
            )
            context_chunks.append(context_entry)
            # Entity docs go to semantic tier
            match_tiers["semantic"].append({
                "name": doc.name,
                "source": doc.source,
                "evidence_id": "ENTITY_DOC",
                "score": 0.3,
            })
    except Exception as exc:
        logger.warning(f"Failed to retrieve entity_documents context: {exc}")

    # Build final context string
    if not context_chunks:
        context_text = "No hay registros encontrados."
    else:
        context_text = "\n\n".join(context_chunks)
    
    # Build ambiguity alert if needed
    clarification_suggestions = []
    has_weak_matches = bool(match_tiers.get("weak"))
    has_semantic_matches = bool(match_tiers.get("semantic"))
    
    if is_ambiguous and (has_weak_matches or has_semantic_matches):
        clarification_suggestions = [
            "RFC or specific identifier",
            "Business sector or activity",
            "Geographic location",
            "Date range",
        ]
    
    metadata = {
        "needs_clarification": is_ambiguous,
        "specificity_score": specificity,
        "match_tiers": match_tiers,
        "clarification_suggestions": clarification_suggestions,
    }
    
    return context_text, metadata

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
