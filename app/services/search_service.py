from typing import List, Dict, Any, Optional, Tuple
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, String, cast, func, and_
from app.models.sanction import Sanction
from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

# ...

async def get_embedding(text: str) -> List[float]:
    # ... (unchanged)
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "sk-placeholder":
        logger.warning("OpenAI API Key not set. Skipping vector generation.")
        return []

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    try:
        response = await client.embeddings.create(
            input=text,
            model="text-embedding-ada-002"
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return []

def _build_common_filters(
    source: Optional[str] = None,
    program: Optional[str] = None,
    listed_after: Optional[Any] = None,
    listed_before: Optional[Any] = None,
):
    filters = []
    if source:
        filters.append(Sanction.source == source)
    if program:
        filters.append(Sanction.program.ilike(f"%{program}%"))
    if listed_after:
        filters.append(Sanction.listed_on >= listed_after)
    if listed_before:
        filters.append(Sanction.listed_on <= listed_before)
    return filters


def _clamp_score(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return round(value, 3)


async def search_sanctions(
    db: AsyncSession,
    query: str,
    limit: int = 10,
    threshold: float = 0.8,
    source: Optional[str] = None,
    program: Optional[str] = None,
    listed_after: Optional[Any] = None,
    listed_before: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Performs a hybrid search:
    1. Exact Match (High Priority)
    2. Fuzzy Match (Trigram)
    3. Vector Match (Semantic) - if configured
    """
    results: List[Dict[str, Any]] = []
    seen_ids = set()
    common_filters = _build_common_filters(
        source=source,
        program=program,
        listed_after=listed_after,
        listed_before=listed_before,
    )

    # 1. Exact Match (High Priority)
    stmt_exact = select(Sanction).filter(
        and_(
            or_(
                Sanction.entity_name.ilike(f"%{query}%"),
                cast(Sanction.aliases, String).ilike(f"%{query}%")
            ),
            *common_filters,
        )
    ).limit(limit)
    res_exact = await db.execute(stmt_exact)
    exact_matches = res_exact.scalars().all()
    
    for m in exact_matches:
        if m.id not in seen_ids:
            results.append(
                {
                    "sanction": m,
                    "score": 1.0,
                    "match_type": "exact",
                }
            )
            seen_ids.add(m.id)

    if len(results) >= limit:
        return await expand_clusters(db, results)

    # 2. Fuzzy Match (Trigram)
    # Requires pg_trgm extension enabled in DB
    try:
        async with db.begin_nested():
            # Note: 'similarity' function comes from pg_trgm. 
            # We order by similarity descending.
            similarity_expr = func.similarity(Sanction.entity_name, query)
            stmt_fuzzy = (
                select(Sanction, similarity_expr.label("similarity_score"))
                .filter(and_(similarity_expr > 0.3, *common_filters))
                .order_by(similarity_expr.desc())
                .limit(limit)
            )
            
            res_fuzzy = await db.execute(stmt_fuzzy, {"query": query})
            fuzzy_matches = res_fuzzy.all()
            
            for m, similarity_score in fuzzy_matches:
                if m.id not in seen_ids:
                    results.append(
                        {
                            "sanction": m,
                            "score": _clamp_score(float(similarity_score or 0.0)),
                            "match_type": "fuzzy",
                        }
                    )
                    seen_ids.add(m.id)
                
            if len(results) >= limit:
                return await expand_clusters(db, results[:limit])

    except Exception as e:
        logger.warning(f"Fuzzy search failed (ensure pg_trgm is enabled): {e}")

    # 3. Vector Search
    embedding = await get_embedding(query)
    if embedding:
        try:
             async with db.begin_nested():
                 # Using pgvector's cosine distance operator (<=>). 
                 # We want closest distance, so order by embedding <=> query_vector
                 distance_expr = Sanction.embedding.cosine_distance(embedding)
                 stmt_vector = (
                     select(Sanction, distance_expr.label("distance_score"))
                     .filter(and_(*common_filters))
                     .order_by(distance_expr)
                     .limit(limit)
                 )
                 
                 res_vector = await db.execute(stmt_vector)
                 vector_matches = res_vector.all()
                 
                 for m, distance_score in vector_matches:
                     if m.id not in seen_ids:
                         similarity_score = 1 - float(distance_score or 1.0)
                         results.append(
                             {
                                 "sanction": m,
                                 "score": _clamp_score(similarity_score),
                                 "match_type": "vector",
                             }
                         )
                         seen_ids.add(m.id)

        except Exception as e:
            logger.warning(f"Vector search failed (ensure pgvector is enabled): {e}")

    return await expand_clusters(db, results[:limit])

async def expand_clusters(db: AsyncSession, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    For each result, checks if it belongs to a profile.
    If so, fetches ALL other sanctions in that profile and adds them to the result set (if not present).
    This ensures that if we find "El Chapo", we return ALL his linked records (UN, MEX, SAT).
    """
    final_results: List[Dict[str, Any]] = []
    seen_ids = set()
    profile_base_meta: Dict[Any, Tuple[float, str]] = {}
    
    profile_ids_to_fetch = set()
    
    # First pass: collect results and profile IDs
    for item in results:
        r = item["sanction"]
        if r.id not in seen_ids:
            final_results.append(item)
            seen_ids.add(r.id)
            if r.profile_id:
                profile_ids_to_fetch.add(r.profile_id)
                profile_base_meta[r.profile_id] = (item["score"], item["match_type"])
                
    if not profile_ids_to_fetch:
        return final_results
        
    # Fetch all siblings
    stmt = select(Sanction).filter(Sanction.profile_id.in_(profile_ids_to_fetch))
    res = await db.execute(stmt)
    siblings = res.scalars().all()
    
    for s in siblings:
        if s.id not in seen_ids:
            inherited_score, inherited_type = profile_base_meta.get(s.profile_id, (0.5, "cluster"))
            final_results.append(
                {
                    "sanction": s,
                    "score": _clamp_score(float(inherited_score) - 0.05),
                    "match_type": f"cluster:{inherited_type}",
                }
            )
            seen_ids.add(s.id)
            
    return final_results
