from typing import List, Dict, Any
import logging
import csv
import io
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete

from app.models.sanction import Sanction

logger = logging.getLogger(__name__)

def parse_sat_csv(csv_content: bytes) -> List[Dict[str, Any]]:
    """
    Parses the SAT 69-B CSV content.
    Skips lines until header is found.
    Mappings:
      - RFC -> rfc
      - Nombre del Contribuyente -> entity_name
      - Situación del Contribuyente -> remarks / program
    """
    # Decode latin-1 or utf-8 (SAT often uses latin-1/windows-1252)
    try:
        decoded_content = csv_content.decode('utf-8')
    except UnicodeDecodeError:
        decoded_content = csv_content.decode('latin-1')

    # Read lines
    lines = decoded_content.splitlines()
    
    # Find start line (header)
    start_index = 0
    header_found = False
    
    # Common headers: "No.", "RFC", "Nombre del Contribuyente"
    for i, line in enumerate(lines):
        if "RFC" in line and "Nombre del Contribuyente" in line:
            start_index = i
            header_found = True
            break
            
    if not header_found:
        logger.error("SAT CSV Header not found")
        return []

    # Parse content from start_index
    # We use DictReader but need to handle potential bad lines
    reader = csv.DictReader(lines[start_index:])
    parsed_data = []

    for row in reader:
        try:
            rfc = row.get("RFC", "").strip()
            name = row.get("Nombre del Contribuyente", "").strip()
            situation = row.get("Situación del Contribuyente", "").strip()
            
            # Additional fields if available
            # "Número de oficio global de presunción"
            # "Fecha de publicación página SAT presuntos"
            
            if not rfc or not name:
                continue

            # Construct data_id
            data_id = f"SAT-69B-{rfc}"
            
            # Construct remarks
            remarks = f"Situación: {situation}."
            
            # Dates (SAT format usually DD/MM/YYYY)
            sanction_date = None
            date_str = row.get("Fecha de publicación página SAT presuntos", "").strip()
            if date_str:
                try:
                     sanction_date = datetime.strptime(date_str, "%d/%m/%Y").date()
                except ValueError:
                    pass

            item = {
                "data_id": data_id,
                "entity_name": name,
                "rfc": rfc,
                "program": "SAT 69-B - Empresas Factureras",
                "source": "SAT_69B",
                "remarks": remarks,
                "reference_number": rfc, # Use RFC as reference
                "sanction_date": sanction_date,
                "listed_on": sanction_date,
                
                # Defaults
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
            logger.warning(f"Error parsing SAT row: {e}")
            continue
            
    return parsed_data

async def sync_sat_sanctions_data(db: AsyncSession, csv_content: bytes) -> Dict[str, int]:
    """
    Synchronizes the database with the SAT 69-B CSV.
    """
    try:
        parsed_data = parse_sat_csv(csv_content)
    except Exception as e:
        logger.error(f"Failed to parse SAT CSV for sync: {e}")
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
            
    # 2. Delete Logic (Scoped to SAT_69B source)
    
    result_all = await db.execute(select(Sanction.data_id).filter(Sanction.source == "SAT_69B"))
    db_data_ids = set(result_all.scalars().all())
    
    ids_to_delete = db_data_ids - csv_data_ids
    count_deleted = len(ids_to_delete)
    
    if ids_to_delete:
         await db.execute(delete(Sanction).where(Sanction.data_id.in_(ids_to_delete)))
        
    await db.commit()
    
    logger.info(f"SAT 69-B Sync complete. Created: {count_created}, Updated: {count_updated}, Deleted: {count_deleted}")
    
    return {
        "created": count_created,
        "updated": count_updated,
        "deleted": count_deleted,
        "total_active": len(csv_data_ids)
    }
