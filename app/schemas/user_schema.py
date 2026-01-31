
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr

from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    AUDITOR = "auditor"
    CONSULTANT = "consultant"
    USER = "user"

class UserBase(BaseModel):
    email: EmailStr
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
    role: UserRole = UserRole.CONSULTANT

class UserCreate(UserBase):
    password: str
    master_password: Optional[str] = None

class UserUpdate(UserBase):
    password: Optional[str] = None

class UserInDBBase(UserBase):
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    created_by_id: Optional[int] = None

    class Config:
        from_attributes = True

class User(UserInDBBase):
    pass

class UserInDB(UserInDBBase):
    hashed_password: str
