from typing import Optional
from sqlmodel import SQLModel
from datetime import datetime

class DictItemBase(SQLModel):
    category: str
    code: str
    label: str
    sort_order: int = 0
    description: Optional[str] = None

class DictItemCreate(DictItemBase):
    pass

class DictItemRead(DictItemBase):
    id: int
    created_at: datetime

class DictItemUpdate(SQLModel):
    category: Optional[str] = None
    code: Optional[str] = None
    label: Optional[str] = None
    sort_order: Optional[int] = None
    description: Optional[str] = None