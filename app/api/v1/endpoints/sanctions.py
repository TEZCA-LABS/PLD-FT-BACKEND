from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Any
import logging

from app.api import deps
from app.services.xml_handler import parse_un_sanctions_xml
from app.models.sanction import Sanction
from app.db.base import Base # Assuming session dependency provides db

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/upload-xml", status_code=status.HTTP_201_CREATED)
async def upload_sanctions_xml(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(deps.get_db), # Adjust based on actual dependency in deps.py
    current_user: Any = Depends(deps.get_current_active_superuser), # Security
) -> Any:
    """
    Upload and process UN Sanctions List XML.
    """
    if not file.filename.endswith('.xml'):
        raise HTTPException(status_code=400, detail="File must be an XML file")
    
    contents = await file.read()
    
    try:
        parsed_data = parse_un_sanctions_xml(contents)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    count_created = 0
    count_updated = 0
    
    for item in parsed_data:
        # Check if exists by data_id
        data_id = item.get("data_id")
        existing_sanction = None
        
        if data_id:
            result = await db.execute(select(Sanction).filter(Sanction.data_id == data_id))
            existing_sanction = result.scalars().first()
            
        if existing_sanction:
            # Update fields
            for key, value in item.items():
                setattr(existing_sanction, key, value)
            count_updated += 1
        else:
            # Create new
            new_sanction = Sanction(**item)
            db.add(new_sanction)
            count_created += 1
            
    try:
        await db.commit()
    except Exception as e:
        logger.error(f"Database commit error: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error saving data to database")
        
    return {
        "message": "XML processed successfully",
        "total_processed": len(parsed_data),
        "created": count_created,
        "updated": count_updated
    }
