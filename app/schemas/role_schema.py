from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class RoleDefinition(BaseModel):
    key: str
    label: str


class RolePermissionItem(BaseModel):
    id: str
    module: str
    label: str
    description: Optional[str] = None
    allowed_roles: List[str] = Field(default_factory=list)


class RolePermissionsResponse(BaseModel):
    roles: List[RoleDefinition]
    permissions: List[RolePermissionItem]
    updated_at: datetime


class RolePermissionUpdate(BaseModel):
    id: str
    allowed_roles: List[str] = Field(default_factory=list)


class RolePermissionsUpdateRequest(BaseModel):
    permissions: List[RolePermissionUpdate] = Field(default_factory=list)
