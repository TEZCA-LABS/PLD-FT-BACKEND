import asyncio
import sys
import os

# Add parent directory to Python path to ensure 'app' module is found
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.services.sat_service import sync_sat_sanctions_data

async def main():
    print("Downloading SAT CSV...")
    async with httpx.AsyncClient() as client:
        response = await client.get(settings.SAT_69B_CSV_URL, timeout=60.0)
        response.raise_for_status()
        csv_content = response.content
        print(f"Downloaded {len(csv_content)} bytes.")

    print("Connecting to DB...")
    engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI, future=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        print("Running Sync...")
        result = await sync_sat_sanctions_data(session, csv_content)
        print("Sync Result:", result)
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
