import asyncio
import sys
import os
import logging
from sqlalchemy import select

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import async_session
from app.models.sanction import Sanction
from app.services.search_service import get_embedding

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def backfill_embeddings():
    logger.info("🚀 Starting embedding backfill...")
    
    async with async_session() as db:
        # Fetch records without embeddings
        stmt = select(Sanction).filter(Sanction.embedding.is_(None))
        result = await db.execute(stmt)
        sanctions = result.scalars().all()
        
        logger.info(f"Found {len(sanctions)} records missing embeddings.")
        
        count = 0
        total = len(sanctions)
        
        for s in sanctions:
            count += 1
            if not s.entity_name:
                continue
                
            try:
                logger.info(f"[{count}/{total}] Generating for: {s.entity_name}")
                embedding = await get_embedding(s.entity_name)
                if embedding:
                    s.embedding = embedding
                    
                # Commit every 10 records to avoid huge transactions
                if count % 10 == 0:
                    await db.commit()
            except Exception as e:
                logger.error(f"Failed for {s.entity_name}: {e}")
                
        await db.commit()
        logger.info("✅ Backfill complete.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(backfill_embeddings())
