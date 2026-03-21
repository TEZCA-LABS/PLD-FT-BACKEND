import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi import HTTPException

ROLE_DEFINITIONS = [
    {"key": "admin", "label": "Admin"},
    {"key": "consultant", "label": "Analista"},
    {"key": "auditor", "label": "Auditor"},
]

DEFAULT_PERMISSIONS = [
    {
        "id": "query_llm",
        "module": "consultas",
        "label": "Consultar LLM (IA Generativa)",
        "description": "Permite enviar consultas al asistente IA.",
        "allowed_roles": ["admin", "consultant"],
    },
    {
        "id": "advanced_entity_search",
        "module": "consultas",
        "label": "Busqueda avanzada de entidades",
        "description": "Permite ejecutar busquedas avanzadas en listas.",
        "allowed_roles": ["admin", "consultant", "auditor"],
    },
    {
        "id": "export_reg_reports",
        "module": "visualizacion",
        "label": "Exportar reportes regulatorios",
        "description": "Permite exportar expedientes en PDF/JSON.",
        "allowed_roles": ["admin", "auditor"],
    },
    {
        "id": "upload_sanctions_xml",
        "module": "operacion",
        "label": "Cargar XML de sanciones",
        "description": "Permite cargar y refrescar listas de sanciones.",
        "allowed_roles": ["admin"],
    },
    {
        "id": "view_audit_history",
        "module": "auditoria",
        "label": "Consultar historial de auditoria",
        "description": "Permite consultar eventos de auditoria.",
        "allowed_roles": ["admin", "auditor"],
    },
]

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "role_permissions.json"


def _get_role_keys() -> set[str]:
    return {role["key"] for role in ROLE_DEFINITIONS}


def _ensure_data_file_exists() -> None:
    if DATA_PATH.exists():
        return

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "permissions": DEFAULT_PERMISSIONS,
    }
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _validate_permissions(permissions: List[Dict[str, Any]]) -> None:
    role_keys = _get_role_keys()

    for permission in permissions:
        invalid_roles = [role for role in permission.get("allowed_roles", []) if role not in role_keys]
        if invalid_roles:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid roles for permission '{permission.get('id')}': {', '.join(invalid_roles)}",
            )


def get_role_permissions() -> Dict[str, Any]:
    _ensure_data_file_exists()

    raw = DATA_PATH.read_text(encoding="utf-8")
    payload = json.loads(raw)

    permissions = payload.get("permissions", [])
    _validate_permissions(permissions)

    updated_at = payload.get("updated_at")
    try:
        parsed_updated_at = datetime.fromisoformat(updated_at) if updated_at else datetime.now(timezone.utc)
    except ValueError:
        parsed_updated_at = datetime.now(timezone.utc)

    return {
        "roles": ROLE_DEFINITIONS,
        "permissions": permissions,
        "updated_at": parsed_updated_at,
    }


def update_role_permissions(updates: List[Dict[str, Any]]) -> Dict[str, Any]:
    current = get_role_permissions()
    existing_permissions = current["permissions"]

    update_map = {item["id"]: item.get("allowed_roles", []) for item in updates}

    next_permissions: List[Dict[str, Any]] = []
    for permission in existing_permissions:
        permission_id = permission["id"]
        next_permissions.append(
            {
                **permission,
                "allowed_roles": update_map.get(permission_id, permission.get("allowed_roles", [])),
            }
        )

    _validate_permissions(next_permissions)

    next_payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "permissions": next_permissions,
    }

    DATA_PATH.write_text(json.dumps(next_payload, ensure_ascii=True, indent=2), encoding="utf-8")

    return {
        "roles": ROLE_DEFINITIONS,
        "permissions": next_permissions,
        "updated_at": datetime.fromisoformat(next_payload["updated_at"]),
    }
