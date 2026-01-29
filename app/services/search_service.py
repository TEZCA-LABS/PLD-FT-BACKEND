from typing import List, Dict, Any, Optional
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, or_
from app.models.sanction import Sanction
from openai import AsyncOpenAI
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# ...

async def get_embedding(text: str) -> List[float]:
    """
    Generates an embedding for the given text using OpenAI.
    """
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

    # 1. Exact Match
    stmt_exact = select(Sanction).filter(Sanction.entity_name.ilike(f"%{query}%")).limit(limit)
    res_exact = await db.execute(stmt_exact)
    exact_matches = res_exact.scalars().all()
    
    for m in exact_matches:
        if m.id not in seen_ids:
            results.append(m)
            seen_ids.add(m.id)

    if len(results) >= limit:
        return results

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
                return results[:limit]

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

    return results[:limit]
