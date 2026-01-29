from typing import Dict, List, Any
import logging
import csv
import io
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete

from app.models.sanction import Sanction

logger = logging.getLogger(__name__)

def parse_mex_csv(csv_content: bytes) -> List[Dict[str, Any]]:
    """
    Parses the Mexican Sanctions CSV content.
    Returns a list of dictionaries mapped to the Sanction model fields.
    """
    decoded_content = csv_content.decode('utf-8')
    csv_reader = csv.DictReader(io.StringIO(decoded_content))
    
    parsed_data = []
    
    for row in csv_reader:
        try:
            # Map fields
            expediente = row.get('expediente', '').strip()
            if not expediente:
                continue
                
            data_id = f"MEX-{expediente}"
            
            # Name construction
            nombre = row.get('nombre', '').strip()
            paterno = row.get('apellido_paterno', '').strip()
            materno = row.get('apellido_materno', '').strip()
            entity_name = f"{nombre} {paterno} {materno}".strip()
            
            # Program construction
            dependencia = row.get('dependencia', '').strip()
            autoridad = row.get('autoridad', '').strip()
            program = f"{dependencia} - {autoridad}"
            
            # Remarks construction
            causa = row.get('causa', '').strip()
            sancion_impuesta = row.get('sancion_impuesta', '').strip()
            ley = row.get('ley', '').strip()
            remarks = f"{causa}. Sancion: {sancion_impuesta}. Ley: {ley}"
            
            # Dates
            fecha_resolucion_str = row.get('fecha_resolucion', '').strip()
            inicio_str = row.get('inicio', '').strip()
            
            listed_on = None
            if fecha_resolucion_str:
                try:
                    listed_on = datetime.fromisoformat(fecha_resolucion_str).date()
                except ValueError:
                    logger.warning(f"Could not parse listed_on date: {fecha_resolucion_str}")

            sanction_date = None
            if inicio_str:
                try:
                    sanction_date = datetime.fromisoformat(inicio_str).date()
                except ValueError:
                    logger.warning(f"Could not parse sanction_date: {inicio_str}")

            item = {
                "data_id": data_id,
                "entity_name": entity_name,
                "program": program,
                "remarks": remarks,
                "source": "MEX_SANCIONADOS",
                "reference_number": expediente,
                "listed_on": listed_on,
                "sanction_date": sanction_date,
                # Default empty for others
                "un_list_type": "National", 
                "designation": [],
                "aliases": [],
                "addresses": [],
                "birth_dates": [],
                "birth_places": [],
                "documents": []
            }
            parsed_data.append(item)
            
        except Exception as e:
            logger.error(f"Error parsing row: {row}. Error: {e}")
            continue
            
    return parsed_data

async def sync_mex_sanctions_data(db: AsyncSession, csv_content: bytes) -> Dict[str, int]:
    """
    Synchronizes the database with the Mexican Sanctions CSV.
    """
    try:
        parsed_data = parse_mex_csv(csv_content)
    except Exception as e:
        logger.error(f"Failed to parse CSV for sync: {e}")
        raise e

    csv_data_ids = set()
    count_created = 0
    count_updated = 0
    
    # 1. Upsert Logic
    for item in parsed_data:
        data_id = item.get("data_id")
        if not data_id:
            continue
            
        csv_data_ids.add(data_id)
        
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
            
    # 2. Delete Logic (Scoped to MEX_SANCIONADOS source)
    # Only delete records that belong to this source and are NOT in the new CSV
    
    result_all = await db.execute(select(Sanction.data_id).filter(Sanction.source == "MEX_SANCIONADOS"))
    db_data_ids = set(result_all.scalars().all())
    
    ids_to_delete = db_data_ids - csv_data_ids
    count_deleted = len(ids_to_delete)
    
    if ids_to_delete:
        await db.execute(delete(Sanction).where(Sanction.data_id.in_(ids_to_delete)))
        
    await db.commit()
    
    logger.info(f"Mexican Sanctions Sync complete. Created: {count_created}, Updated: {count_updated}, Deleted: {count_deleted}")
    
    return {
        "created": count_created,
        "updated": count_updated,
        "deleted": count_deleted,
        "total_active": len(csv_data_ids)
    }
