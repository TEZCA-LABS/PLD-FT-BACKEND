import io
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Generator
import logging

logger = logging.getLogger(__name__)

def strip_ns(tag: str) -> str:
    """Removes the namespace from an XML tag."""
    if '}' in tag:
        return tag.split('}', 1)[1]
    return tag

def get_text(element: ET.Element, default: str = "") -> str:
    return element.text.strip() if element is not None and element.text else default

def parse_ofac_advanced_xml(content: bytes) -> Generator[Dict[str, Any], None, None]:
    """
    Iteratively parses the OFAC ASDM Advanced XML using iterparse to save memory.
    Yields a dictionary for each DistinctParty found.
    """
    # Create a file-like object from the bytes
    xml_file = io.BytesIO(content)
    
    # We only care about finding DistinctParty elements. 
    # Because of namespaces, we'll strip them to keep it simple.
    context = ET.iterparse(xml_file, events=('end',))
    
    # Track the reference value sets if needed, but for simplicity we will extract directly
    # from the DistinctParty tree.
    
    for event, elem in context:
        tag = strip_ns(elem.tag)
        
        if tag == "DistinctParty":
            # Extract basic identifiers
            data_id = elem.attrib.get("FixedRef")
            
            def find_all_by_tag(root, target_tag):
                return [child for child in root.iter() if strip_ns(child.tag) == target_tag]

            def find_first_by_tag(root, target_tag):
                for child in root.iter():
                    if strip_ns(child.tag) == target_tag:
                        return child
                return None
                
            # Find the primary comment
            remarks = ""
            comment_elem = find_first_by_tag(elem, "Comment")
            if comment_elem is not None:
                remarks = get_text(comment_elem)
                
            aliases = []
            documents = []
            entity_name = ""
            
            # Parse Profiles
            for profile in find_all_by_tag(elem, "Profile"):
                # Identities and Aliases
                for identity in find_all_by_tag(profile, "Identity"):
                    for alias in find_all_by_tag(identity, "Alias"):
                        low_quality = alias.attrib.get("LowQuality", "false").lower() == "true"
                        is_primary = alias.attrib.get("Primary", "false").lower() == "true"
                        
                        # Build the full name from DocumentedNamePart
                        name_parts = []
                        for part in find_all_by_tag(alias, "DocumentedNamePart"):
                            val = find_first_by_tag(part, "NamePartValue")
                            if val is not None:
                                name_parts.append(get_text(val))
                                
                        full_name = " ".join(name_parts)
                        
                        if is_primary and not entity_name:
                            entity_name = full_name
                        else:
                            aliases.append({
                                "name": full_name,
                                "quality": "weak" if low_quality else "strong",
                                "is_primary": is_primary
                            })
                            
                # Documents (if present inside Profile)
                for doc in find_all_by_tag(profile, "IDRegDocument"):
                    doc_val = find_first_by_tag(doc, "IDRegDocumentValue")
                    doc_type = find_first_by_tag(doc, "IDRegDocTypeID")
                    if doc_val is not None:
                        documents.append({
                            "value": get_text(doc_val),
                            "type_id": get_text(doc_type) if doc_type is not None else None
                        })
            
            # Sanctions entries (could be top level or inside Profile, we search from DistinctParty)
            programs = []
            for sanction in find_all_by_tag(elem, "SanctionsEntry"):
                for measure in find_all_by_tag(sanction, "SanctionsMeasure"):
                    comment = find_first_by_tag(measure, "Comment")
                    if comment is not None:
                        programs.append(get_text(comment))
                        
            program_str = ", ".join(programs) if programs else None
            
            # If no primary alias was marked, just use the first strong alias or anything available
            if not entity_name and aliases:
                entity_name = aliases[0]["name"]
                
            sanction_entry = {
                "data_id": data_id,
                "entity_name": entity_name,
                "remarks": remarks,
                "aliases": aliases,
                "documents": documents,
                "program": program_str,
                "addresses": [], # OFAC Address parsing could be expanded here
                "birth_dates": [],
                "birth_places": [],
                "designation": [],
                "gender": None,
                "nationality": None,
                "un_list_type": None,
                "reference_number": None,
                "source": "OFAC" # Will be overridden by the service
            }
            
            yield sanction_entry
            
            # Clear the element from memory to avoid RAM blowup
            elem.clear()
