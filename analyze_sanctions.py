import asyncio
import sys
import json
from sqlalchemy import select
from app.db.session import async_session
from app.models.sanction import Sanction

async def analyze_sanctions():
    async with async_session() as session:
        # Fetch a sample of records
        result = await session.execute(select(Sanction).limit(5))
        sanctions = result.scalars().all()
        
        if not sanctions:
            print("No sanctions found in the database.")
            return

        print(f"Found {len(sanctions)} records. analyzing samples:\n")
        
        for s in sanctions:
            data = {
                "Entity Name": s.entity_name,
                "List Type": s.un_list_type,
                "Program": s.program,
                "Remarks": s.remarks[:200] + "..." if s.remarks else None,
                "Designation": s.designation,
                "Ref Number": s.reference_number
            }
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("-" * 40)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(analyze_sanctions())
