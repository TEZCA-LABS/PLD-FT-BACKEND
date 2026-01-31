
import asyncio
import sys
import os

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

async def main():
    print("🔧 Backfilling User Roles...")
    
    engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI, future=True)
    
    async with engine.begin() as conn:
        print("Updating users with NULL role...")
        try:
            # We use quotes for "user" because it is a reserved word in Postgres
            await conn.execute(text("UPDATE \"user\" SET role = 'consultant' WHERE role IS NULL"))
            print("✅ User roles updated.")
        except Exception as e:
            print(f"⚠️ Error updating roles: {e}")
            
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
