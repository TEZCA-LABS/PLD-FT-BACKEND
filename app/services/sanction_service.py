from typing import Dict, List, Any
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from app.models.sanction import Sanction
from app.services.xml_handler import parse_un_sanctions_xml

logger = logging.getLogger(__name__)

async def sync_sanctions_data(db: AsyncSession, xml_content: bytes) -> Dict[str, int]:
    """
    Synchronizes the database with the provided XML content.
    1. Parses XML.
    2. Bulk Upserts (Insert/Update) all records from XML using PostgreSQL native ON CONFLICT.
    3. Deletes records in DB that are NOT in the XML (Source of Truth).
    """
    try:
        parsed_data = parse_un_sanctions_xml(xml_content)
    except Exception as e:
        logger.error(f"Failed to parse XML for sync: {e}")
        raise e

    if not parsed_data:
        logger.warning("No data found in XML.")
        return {
            "created": 0,
            "updated": 0,
            "deleted": 0,
            "total_active": 0
        }

    # Extract all data_ids from the parsed data for the deletion logic later
    xml_data_ids = {item["data_id"] for item in parsed_data if item.get("data_id")}
    
    # 1. Bulk Upsert Logic
    # Prepare the statement
    stmt = insert(Sanction).values(parsed_data)
    
    # Define what to do on conflict (update all fields except the primary key and constraint)
    # We construct the set_ dictionary dynamically based on the keys available in the first item
    # or by inspecting the model. However, 'parsed_data' acts as the source.
    # A safer approach for strict models is to use the table columns.
    
    # We want to update everything that came in the new data.
    # excluded contains the values we tried to insert.
    
    update_dict = {
        c.name: c
        for c in stmt.excluded
        if c.name not in ["id", "data_id"]
    }
    
    on_conflict_stmt = stmt.on_conflict_do_update(
        index_elements=[Sanction.data_id],
        set_=update_dict
    )
    
    # Execute the upsert
    # Note: determining exact counts of created vs updated is harder with a single query 
    # without returning xmax or similar, but for sync purposes knowing total processed is often enough.
    # We can approximate or just track total "touched".
    await db.execute(on_conflict_stmt)
    
    # 2. Delete Logic
    # specific columns are required to form a set
    result_all = await db.execute(select(Sanction.data_id))
    db_data_ids = set(result_all.scalars().all())
    
    ids_to_delete = db_data_ids - xml_data_ids
    count_deleted = len(ids_to_delete)
    
    if ids_to_delete:
         await db.execute(delete(Sanction).where(Sanction.data_id.in_(ids_to_delete)))
        
    await db.commit()
    
    # Calculating created/updated exactly would require more complex queries or returning rows.
    # For now, we report the total active and deleted.
    
    logger.info(f"Sync complete. Total Processing: {len(parsed_data)}, Deleted: {count_deleted}")
    
    return {
        "created": -1, # optimized out exact count
        "updated": -1, # optimized out exact count
        "deleted": count_deleted,
        "total_active": len(xml_data_ids)
    }
