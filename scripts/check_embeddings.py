import asyncio
import sys
import os

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import async_session
from app.models.sanction import Sanction
from sqlalchemy import select

async def check():
    async with async_session() as db:
        # Check IDs mentioned by user
        stmt = select(Sanction.id, Sanction.entity_name, Sanction.embedding).filter(Sanction.id.in_([1454, 1455])).limit(5)
        result = await db.execute(stmt)
        rows = result.all()
        
        print(f"Checking {len(rows)} records:")
        for row in rows:
            has_embedding = row.embedding is not None
            print(f"ID: {row.id}, Name: {row.entity_name}, Has Embedding: {has_embedding}")
            if has_embedding:
                print(f"Embedding check: {row.embedding[:5]}...")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check())
