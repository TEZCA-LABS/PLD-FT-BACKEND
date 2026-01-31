from typing import List, Dict, Any, Optional
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, or_, String, cast
from app.models.sanction import Sanction
from openai import AsyncOpenAI
import logging
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

async def search_sanctions(db: AsyncSession, query: str, limit: int = 10, threshold: float = 0.8) -> List[Sanction]:
    """
    Performs a hybrid search:
    1. Exact Match (High Priority)
    2. Fuzzy Match (Trigram)
    3. Vector Match (Semantic) - if configured
    """
    results = []
    seen_ids = set()

    # 1. Exact Match (High Priority)
    stmt_exact = select(Sanction).filter(
        or_(
            Sanction.entity_name.ilike(f"%{query}%"),
            cast(Sanction.aliases, String).ilike(f"%{query}%") # Search in aliases JSON
        )
    ).limit(limit)
    res_exact = await db.execute(stmt_exact)
    exact_matches = res_exact.scalars().all()
    
    for m in exact_matches:
        if m.id not in seen_ids:
            results.append(m)
            seen_ids.add(m.id)

    if len(results) >= limit:
        return await expand_clusters(db, results)

    # 2. Fuzzy Match (Trigram)
    # Requires pg_trgm extension enabled in DB
    try:
        async with db.begin_nested():
            # Note: 'similarity' function comes from pg_trgm. 
            # We order by similarity descending.
            stmt_fuzzy = select(Sanction).filter(
                text(f"similarity(entity_name, :query) > 0.3")
            ).order_by(text(f"similarity(entity_name, :query) DESC")).limit(limit)
            
            res_fuzzy = await db.execute(stmt_fuzzy, {"query": query})
            fuzzy_matches = res_fuzzy.scalars().all()
            
            for m in fuzzy_matches:
                if m.id not in seen_ids:
                    results.append(m)
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
                 stmt_vector = select(Sanction).order_by(
                     Sanction.embedding.cosine_distance(embedding)
                 ).limit(limit)
                 
                 res_vector = await db.execute(stmt_vector)
                 vector_matches = res_vector.scalars().all()
                 
                 for m in vector_matches:
                     if m.id not in seen_ids:
                         results.append(m)
                         seen_ids.add(m.id)

        except Exception as e:
            logger.warning(f"Vector search failed (ensure pgvector is enabled): {e}")

    return await expand_clusters(db, results[:limit])

from sqlalchemy.orm import selectinload

async def expand_clusters(db: AsyncSession, results: List[Sanction]) -> List[Sanction]:
    """
    For each result, checks if it belongs to a profile.
    If so, fetches ALL other sanctions in that profile and adds them to the result set (if not present).
    This ensures that if we find "El Chapo", we return ALL his linked records (UN, MEX, SAT).
    """
    final_results = []
    seen_ids = set()
    
    profile_ids_to_fetch = set()
    
    # First pass: collect results and profile IDs
    for r in results:
        if r.id not in seen_ids:
            final_results.append(r)
            seen_ids.add(r.id)
            if r.profile_id:
                profile_ids_to_fetch.add(r.profile_id)
                
    if not profile_ids_to_fetch:
        return final_results
        
    # Fetch all siblings
    stmt = select(Sanction).filter(Sanction.profile_id.in_(profile_ids_to_fetch))
    res = await db.execute(stmt)
    siblings = res.scalars().all()
    
    for s in siblings:
        if s.id not in seen_ids:
            final_results.append(s)
            seen_ids.add(s.id)
            
    return final_results
