import asyncio
import sys
import os

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import async_session
from app.services.search_service import search_sanctions
from app.models.sanction import Sanction
from sqlalchemy import select

async def test_search():
    print("🚀 Starting Hybrid Search Test...")
    
    async with async_session() as session:
        # 1. Setup Data - Check if "EL CHAPO" exists (Just a test name)
        test_name = "JOAQUIN ARCHIVALDO GUZMAN LOERA"
        result = await session.execute(select(Sanction).filter(Sanction.entity_name == test_name))
        existing = result.scalars().first()
        
        if not existing:
            # Create dummy record
            print(f"Creating test record: {test_name}")
            new_s = Sanction(
                entity_name=test_name,
                source="TEST_DATA",
                data_id="TEST-001"
            )
            session.add(new_s)
            await session.commit()
        
        # 2. Test Exact Match
        print("\n--- Test 1: Exact Match 'GUZMAN' ---")
        results = await search_sanctions(session, "GUZMAN")
        print(f"Found {len(results)} matches.")
        for r in results:
            print(f" - {r.entity_name} ({r.source})")

        # 3. Test Fuzzy Match (Typo)
        print("\n--- Test 2: Fuzzy Match 'GUSMAN' (Typo) ---")
        # this relies on pg_trgm being enabled in the actual DB
        results = await search_sanctions(session, "GUSMAN")
        print(f"Found {len(results)} matches.")
        for r in results:
            print(f" - {r.entity_name} ({r.source})")

        # 4. Clean up
        if not existing:
             await session.delete(new_s)
             await session.commit()
             print("\nTest record deleted.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_search())
