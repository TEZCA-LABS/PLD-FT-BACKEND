
import asyncio
import sys
import os

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.services.entity_resolution_service import cluster_entities

async def main():
    print("🚀 Triggering Entity Clustering...")
    
    print("Connecting to DB...")
    engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI, future=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        print("Running Clustering Logic...")
        await cluster_entities(session)
        print("✅ Clustering Complete.")
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
