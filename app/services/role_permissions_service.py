from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role_permission import RolePermission

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

def _get_role_keys() -> set[str]:
    return {role["key"] for role in ROLE_DEFINITIONS}


def _validate_permissions(permissions: List[Dict[str, Any]]) -> None:
    role_keys = _get_role_keys()

    for permission in permissions:
        invalid_roles = [role for role in permission.get("allowed_roles", []) if role not in role_keys]
        if invalid_roles:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid roles for permission '{permission.get('id')}': {', '.join(invalid_roles)}",
            )


def _to_permission_payload(permission: RolePermission) -> Dict[str, Any]:
    return {
        "id": permission.permission_id,
        "module": permission.module,
        "label": permission.label,
        "description": permission.description,
        "allowed_roles": permission.allowed_roles or [],
    }


async def _seed_defaults_if_empty(db: AsyncSession) -> List[RolePermission]:
    query = select(RolePermission).order_by(RolePermission.id.asc())
    result = await db.execute(query)
    rows = list(result.scalars().all())

    if rows:
        return rows

    for permission in DEFAULT_PERMISSIONS:
        row = RolePermission()
        row.permission_id = permission["id"]
        row.module = permission["module"]
        row.label = permission["label"]
        setattr(row, "description", permission.get("description"))
        row.allowed_roles = permission.get("allowed_roles", [])
        db.add(row)

    await db.commit()
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_role_permissions(db: AsyncSession) -> Dict[str, Any]:
    rows = await _seed_defaults_if_empty(db)
    permissions = [_to_permission_payload(row) for row in rows]
    _validate_permissions(permissions)

    latest_updated_at = max(
        (row.updated_at for row in rows if row.updated_at is not None),
        default=datetime.now(timezone.utc),
    )

    return {
        "roles": ROLE_DEFINITIONS,
        "permissions": permissions,
        "updated_at": latest_updated_at,
    }


async def update_role_permissions(db: AsyncSession, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = await _seed_defaults_if_empty(db)
    existing_permissions = [_to_permission_payload(row) for row in rows]

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

    rows_by_permission = {row.permission_id: row for row in rows}
    for permission in next_permissions:
        row = rows_by_permission.get(permission["id"])
        if not row:
            continue
        row.allowed_roles = permission.get("allowed_roles", [])

    await db.commit()

    refreshed = await db.execute(select(RolePermission).order_by(RolePermission.id.asc()))
    refreshed_rows = list(refreshed.scalars().all())
    latest_updated_at = max(
        (row.updated_at for row in refreshed_rows if row.updated_at is not None),
        default=datetime.now(timezone.utc),
    )

    refreshed_permissions = [_to_permission_payload(row) for row in refreshed_rows]

    return {
        "roles": ROLE_DEFINITIONS,
        "permissions": refreshed_permissions,
        "updated_at": latest_updated_at,
    }
