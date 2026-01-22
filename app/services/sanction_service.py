from typing import Dict, List, Any
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete

from app.models.sanction import Sanction
from app.services.xml_handler import parse_un_sanctions_xml

logger = logging.getLogger(__name__)

async def sync_sanctions_data(db: AsyncSession, xml_content: bytes) -> Dict[str, int]:
    """
    Synchronizes the database with the provided XML content.
    1. Parses XML.
    2. Upserts (Update/Insert) all records from XML.
    3. Deletes records in DB that are NOT in the XML (Source of Truth).
    """
    try:
        parsed_data = parse_un_sanctions_xml(xml_content)
    except Exception as e:
        logger.error(f"Failed to parse XML for sync: {e}")
        raise e

    xml_data_ids = set()
    count_created = 0
    count_updated = 0
    
    # 1. Upsert Logic
    for item in parsed_data:
        data_id = item.get("data_id")
        if not data_id:
            continue
            
        xml_data_ids.add(data_id)
        
        # Check existence
        result = await db.execute(select(Sanction).filter(Sanction.data_id == data_id))
        existing_sanction = result.scalars().first()
        
        if existing_sanction:
            # Update
            for key, value in item.items():
                setattr(existing_sanction, key, value)
            count_updated += 1
        else:
            # Insert
            new_sanction = Sanction(**item)
            db.add(new_sanction)
            count_created += 1
            
    # Commit upserts to ensure data is consistent before delete? 
    # Or do it all in one transaction? One transaction is safer.
    
    # 2. Delete Logic
    # Find IDs in DB that are NOT in xml_data_ids
    # We can do this efficiently if the dataset is not massive. 
    # For UN List (~1000s records), fetching all IDs is feasible.
    
    result_all = await db.execute(select(Sanction.data_id))
    db_data_ids = set(result_all.scalars().all())
    
    # IDs to delete = DB IDs - XML IDs
    ids_to_delete = db_data_ids - xml_data_ids
    count_deleted = len(ids_to_delete)
    
    if ids_to_delete:
        # Batch delete or individual? 
        # Using 'in_' clause might hit limits if massive, but for UN Sanctions it's likely fine.
        # delete(Sanction).where(Sanction.data_id.in_(ids_to_delete))
        await db.execute(delete(Sanction).where(Sanction.data_id.in_(ids_to_delete)))
        
    await db.commit()
    
    logger.info(f"Sync complete. Created: {count_created}, Updated: {count_updated}, Deleted: {count_deleted}")
    
    return {
        "created": count_created,
        "updated": count_updated,
        "deleted": count_deleted,
        "total_active": len(xml_data_ids)
    }
