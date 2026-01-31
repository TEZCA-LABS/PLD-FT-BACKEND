
import asyncio
import sys
import os

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

async def main():
    print("🔧 Fixing Alembic Version Table...")
    
    engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI, future=True)
    
    async with engine.begin() as conn:
        print("Cleaning alembic_version table...")
        # We can either drop the table or delete rows. Deleting rows is safer if we want to re-stamp.
        # But if the table is corrupt or weird, maybe drop?
        # Let's try deleting rows first.
        try:
            await conn.execute(text("DELETE FROM alembic_version"))
            print("✅ Cleared `alembic_version` table.")
        except Exception as e:
            print(f"⚠️ Error clearing table (maybe it doesn't exist?): {e}")
            
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
