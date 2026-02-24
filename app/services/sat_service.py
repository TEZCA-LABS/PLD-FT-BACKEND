from typing import List, Dict, Any, Optional
import logging
import csv
import unicodedata
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete

from app.models.sanction import Sanction

logger = logging.getLogger(__name__)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return normalized.encode("ascii", "ignore").decode("ascii").lower().strip()


def _parse_date_ddmmyyyy(raw: str) -> Optional[datetime.date]:
    raw = (raw or "").strip()
    if not raw:
        return None
    date_candidate = raw.split("-")[0].strip()
    try:
        return datetime.strptime(date_candidate, "%d/%m/%Y").date()
    except ValueError:
        return None


def _find_value(row_map: Dict[str, str], keyword_groups: List[List[str]]) -> str:
    for keywords in keyword_groups:
        for key, value in row_map.items():
            if all(token in key for token in keywords) and value:
                return value.strip()
    return ""


def _sat_risk_level(status: str) -> str:
    normalized = _normalize_text(status)
    if "definit" in normalized:
        return "alto"
    if "presunt" in normalized:
        return "medio"
    if "desvirt" in normalized or "sentencia" in normalized or "favorable" in normalized:
        return "bajo"
    return "indeterminado"


def _sat_reference_for_status(status: str, row_map: Dict[str, str]) -> str:
    normalized = _normalize_text(status)

    if "definit" in normalized:
        return _find_value(
            row_map,
            [
                ["oficio", "definitiv", "sat"],
                ["oficio", "definitiv", "dof"],
            ],
        )
    if "presunt" in normalized:
        return _find_value(
            row_map,
            [
                ["oficio", "presuncion", "sat"],
                ["oficio", "presuncion", "dof"],
            ],
        )
    if "desvirt" in normalized:
        return _find_value(
            row_map,
            [
                ["oficio", "desvirtuaron", "sat"],
                ["oficio", "desvirtuaron", "dof"],
            ],
        )
    if "sentencia" in normalized or "favorable" in normalized:
        return _find_value(
            row_map,
            [
                ["oficio", "sentencia", "favorable", "sat"],
                ["oficio", "sentencia", "favorable", "dof"],
            ],
        )

    return _find_value(
        row_map,
        [
            ["oficio", "definitiv"],
            ["oficio", "presuncion"],
            ["oficio", "desvirtuaron"],
            ["oficio", "sentencia", "favorable"],
        ],
    )


def _sat_date_for_status(status: str, row_map: Dict[str, str]) -> Optional[datetime.date]:
    normalized = _normalize_text(status)

    if "definit" in normalized:
        return _parse_date_ddmmyyyy(
            _find_value(
                row_map,
                [
                    ["publicacion", "sat", "definitiv"],
                    ["publicacion", "dof", "definitiv"],
                ],
            )
        )
    if "presunt" in normalized:
        return _parse_date_ddmmyyyy(
            _find_value(
                row_map,
                [
                    ["publicacion", "sat", "presunt"],
                    ["publicacion", "dof", "presunt"],
                ],
            )
        )
    if "desvirt" in normalized:
        return _parse_date_ddmmyyyy(
            _find_value(
                row_map,
                [
                    ["publicacion", "sat", "desvirtu"],
                    ["publicacion", "dof", "desvirtu"],
                ],
            )
        )
    if "sentencia" in normalized or "favorable" in normalized:
        return _parse_date_ddmmyyyy(
            _find_value(
                row_map,
                [
                    ["publicacion", "sat", "sentencia", "favorable"],
                    ["publicacion", "dof", "sentencia", "favorable"],
                ],
            )
        )

    return _parse_date_ddmmyyyy(
        _find_value(
            row_map,
            [
                ["publicacion", "sat", "definitiv"],
                ["publicacion", "sat", "presunt"],
                ["publicacion", "sat", "desvirtu"],
                ["publicacion", "sat", "sentencia"],
            ],
        )
    )


def _build_sat_remarks(status: str, reference_number: str, risk_level: str) -> str:
    status_clean = status or "No identificado"
    reference_clean = reference_number or "Sin oficio disponible"

    interpretation = {
        "alto": "El registro indica publicación definitiva en el procedimiento 69-B; considerar riesgo fiscal y de materialidad elevado.",
        "medio": "El registro está en etapa presunta; se requiere validación adicional y monitoreo de transición de estatus.",
        "bajo": "El registro aparece como desvirtuado o con sentencia favorable; riesgo mitigado bajo este artículo.",
        "indeterminado": "No fue posible inferir una categoría de riesgo a partir del estatus proporcionado.",
    }.get(risk_level, "")

    return (
        f"Estatus SAT 69-B: {status_clean}. "
        f"Nivel de riesgo estimado: {risk_level}. "
        f"Oficio relacionado: {reference_clean}. "
        f"Interpretación: {interpretation}"
    )

def parse_sat_csv(csv_content: bytes) -> List[Dict[str, Any]]:
    """
    Parses the SAT 69-B CSV content.
    Skips lines until header is found.
    Mappings:
      - RFC -> rfc
      - Nombre del Contribuyente -> entity_name
      - Situación del Contribuyente -> remarks / program
    """
    # Decode latin-1/windows-1252 or utf-8 variants (SAT files are inconsistent)
    try:
        decoded_content = csv_content.decode('utf-8-sig')
    except UnicodeDecodeError:
        try:
            decoded_content = csv_content.decode('cp1252')
        except UnicodeDecodeError:
            decoded_content = csv_content.decode('latin-1', errors='ignore')

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
            row_map = {
                _normalize_text(str(key)): (value or "").strip()
                for key, value in row.items()
                if key
            }

            rfc = _find_value(row_map, [["rfc"]])
            name = _find_value(row_map, [["nombre", "contribuyente"]])
            situation = _find_value(row_map, [["situ", "contribuyente"]])
            
            if not rfc or not name:
                continue

            risk_level = _sat_risk_level(situation)
            reference_number = _sat_reference_for_status(situation, row_map) or rfc
            sanction_date = _sat_date_for_status(situation, row_map)
            remarks = _build_sat_remarks(
                status=situation,
                reference_number=reference_number,
                risk_level=risk_level,
            )

            # Construct data_id
            data_id = f"SAT-69B-{rfc}"

            item = {
                "data_id": data_id,
                "entity_name": name,
                "rfc": rfc,
                "program": f"SAT 69-B - {situation or 'Sin estatus'}",
                "source": "SAT_69B",
                "remarks": remarks,
                "reference_number": reference_number,
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
