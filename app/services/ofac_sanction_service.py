from typing import Dict, List, Any
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from app.models.sanction import Sanction
from app.services.ofac_xml_handler import parse_ofac_advanced_xml

logger = logging.getLogger(__name__)

async def _sync_ofac_data_batch(db: AsyncSession, xml_content: bytes, source_tag: str) -> Dict[str, int]:
    """
    Synchronizes the database with the provided OFAC XML content using batches.
    Source tag differentiates SDN from CONS.
    """
    try:
        generator = parse_ofac_advanced_xml(xml_content)
    except Exception as e:
        logger.error(f"Failed to initiate OFAC XML parsing: {e}")
        raise e

    batch_size = 1000
    batch = []
    xml_data_ids = set()
    total_processed = 0

    async def flush_batch(current_batch: List[Dict[str, Any]]):
        if not current_batch:
            return
        
        # Enforce source tag
        for item in current_batch:
            item["source"] = source_tag
            
        stmt = insert(Sanction).values(current_batch)
        update_dict = {
            c.name: c
            for c in stmt.excluded
            if c.name not in ["id", "data_id"]
        }
        
        on_conflict_stmt = stmt.on_conflict_do_update(
            index_elements=[Sanction.data_id],
            set_=update_dict
        )
        
        await db.execute(on_conflict_stmt)

    for item in generator:
        if item.get("data_id"):
            # We prefix OFAC IDs to ensure they don't collide with UN ones just in case, 
            # though they usually don't.
            item["data_id"] = f"{source_tag}_{item['data_id']}"
            xml_data_ids.add(item["data_id"])
            
        batch.append(item)
        total_processed += 1
        
        if len(batch) >= batch_size:
            await flush_batch(batch)
            batch = []

    # flush remaining
    await flush_batch(batch)

    # Deletion logic: delete records from THIS source that are no longer in the XML
    result_all = await db.execute(select(Sanction.data_id).where(Sanction.source == source_tag))
    db_data_ids = set(result_all.scalars().all())
    
    ids_to_delete = db_data_ids - xml_data_ids
    count_deleted = len(ids_to_delete)
    
    if ids_to_delete:
         # SQLAlchemy IN clause limits, let's chunk the deletion just in case
         ids_list = list(ids_to_delete)
         for i in range(0, len(ids_list), 1000):
             chunk = ids_list[i:i+1000]
             await db.execute(delete(Sanction).where(Sanction.data_id.in_(chunk)))
        
    await db.commit()
    
    logger.info(f"OFAC {source_tag} Sync complete. Total Processing: {total_processed}, Deleted: {count_deleted}")
    
    return {
        "created": -1, 
        "updated": -1, 
        "deleted": count_deleted,
        "total_active": len(xml_data_ids)
    }

async def sync_ofac_sdn_data(db: AsyncSession, xml_content: bytes) -> Dict[str, int]:
    return await _sync_ofac_data_batch(db, xml_content, "OFAC_SDN")

async def sync_ofac_cons_data(db: AsyncSession, xml_content: bytes) -> Dict[str, int]:
    return await _sync_ofac_data_batch(db, xml_content, "OFAC_CONS")
