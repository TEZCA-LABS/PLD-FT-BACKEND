import xmltodict
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def parse_date(date_str: Optional[str]) -> Optional[str]:
    """Parses various date formats from XML."""
    if not date_str:
        return None
    try:
        # Try YYYY-MM-DD
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        pass
    
    try:
        # Try YYYY
        return datetime.strptime(date_str, "%Y").date()
    except ValueError:
        pass
    
    return None

def extract_list_value(data: Any, key: str = "VALUE") -> List[str]:
    """Extracts a list of strings from nested XML structures like <DESIGNATION><VALUE>...</VALUE></DESIGNATION>."""
    if not data:
        return []
    
    if isinstance(data, dict):
         # Single item or wrapper
         if key in data:
             val = data[key]
             if isinstance(val, list):
                 return val
             return [val]
         return []
    elif isinstance(data, list):
        results = []
        for item in data:
            if isinstance(item, dict) and key in item:
                results.append(item[key])
            elif isinstance(item, str):
                results.append(item)
        return results
    return []

def extract_aliases(alias_data: Any) -> List[Dict[str, str]]:
    """Extracts aliases."""
    if not alias_data:
        return []
    
    aliases = []
    items = alias_data if isinstance(alias_data, list) else [alias_data]
    
    for item in items:
        if isinstance(item, dict):
            aliases.append({
                "quality": item.get("QUALITY"),
                "name": item.get("ALIAS_NAME"),
                "note": item.get("NOTE")
            })
    return aliases

def extract_addresses(addr_data: Any) -> List[Dict[str, str]]:
    """Extracts addresses."""
    if not addr_data:
        return []
    
    addresses = []
    items = addr_data if isinstance(addr_data, list) else [addr_data]
    
    for item in items:
        if isinstance(item, dict):
            addresses.append({
                "city": item.get("CITY"),
                "country": item.get("COUNTRY"),
                "note": item.get("NOTE"),
                "state_province": item.get("STATE_PROVINCE"),
                "street": item.get("STREET")
            })
    return addresses

def parse_un_sanctions_xml(content: bytes) -> List[Dict[str, Any]]:
    """
    Parses the UN Sanctions XML content and returns a list of individual dictionaries ready for DB insertion.
    """
    try:
        data = xmltodict.parse(content)
    except Exception as e:
        logger.error(f"Failed to parse XML: {e}")
        raise ValueError(f"Invalid XML format: {e}")

    consolidated_list = data.get("CONSOLIDATED_LIST", {})
    individuals = consolidated_list.get("INDIVIDUALS", {}).get("INDIVIDUAL", [])
    
    if not individuals:
        return []
        
    if not isinstance(individuals, list):
        individuals = [individuals]

    parsed_individuals = []

    for indiv in individuals:
        # Basic Info
        first_name = indiv.get("FIRST_NAME", "")
        second_name = indiv.get("SECOND_NAME", "")
        third_name = indiv.get("THIRD_NAME", "")
        fourth_name = indiv.get("FOURTH_NAME", "")
        
        # Construct full entity name
        full_name_parts = [p for p in [first_name, second_name, third_name, fourth_name] if p]
        entity_name = " ".join(full_name_parts)

        # Dates
        listed_on_str = indiv.get("LISTED_ON")
        listed_on = parse_date(listed_on_str)
        
        last_updated_container = indiv.get("LAST_DAY_UPDATED", {})
        last_updated_vals = extract_list_value(last_updated_container)
        last_updated_str = last_updated_vals[-1] if last_updated_vals else None
        last_updated = parse_date(last_updated_str)

        # Lists
        app_designations = extract_list_value(indiv.get("DESIGNATION"))
        app_aliases = extract_aliases(indiv.get("INDIVIDUAL_ALIAS"))
        app_addresses = extract_addresses(indiv.get("INDIVIDUAL_ADDRESS"))
        
        # Nationality
        nationality_container = indiv.get("NATIONALITY", {})
        nationalities = extract_list_value(nationality_container)
        nationality = ", ".join(nationalities) if nationalities else None

        # Birth Info
        dob_container = indiv.get("INDIVIDUAL_DATE_OF_BIRTH")
        pob_container = indiv.get("INDIVIDUAL_PLACE_OF_BIRTH")
        
        # Documents
        docs_container = indiv.get("INDIVIDUAL_DOCUMENT")

        sanction_entry = {
            "data_id": indiv.get("DATAID"),
            "un_list_type": indiv.get("UN_LIST_TYPE"),
            "reference_number": indiv.get("REFERENCE_NUMBER"),
            "entity_name": entity_name,
            "gender": indiv.get("GENDER"),
            "remarks": indiv.get("COMMENTS1"),
            "listed_on": listed_on,
            "last_updated": last_updated,
            "nationality": nationality,
            "designation": app_designations,
            "aliases": app_aliases,
            "addresses": app_addresses,
            "birth_dates": dob_container if dob_container else [], # Keeping raw dict/list or simplified? Let's keep structure for JSON
            "birth_places": pob_container if pob_container else [],
            "documents": docs_container if docs_container else [],
            "program": indiv.get("UN_LIST_TYPE"), # Reuse list type or specific program
            "source": "UN_CONSOLIDATED",
            "sanction_date": listed_on # Mirroring
        }
        
        parsed_individuals.append(sanction_entry)
        
    return parsed_individuals
