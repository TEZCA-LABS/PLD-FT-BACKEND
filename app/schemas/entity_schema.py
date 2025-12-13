
from typing import Optional
from pydantic import BaseModel

class EntityBase(BaseModel):
    name: str
    source: str
    content: str

class EntityCreate(EntityBase):
    pass

class Entity(EntityBase):
    id: int
    
    class Config:
        from_attributes = True
