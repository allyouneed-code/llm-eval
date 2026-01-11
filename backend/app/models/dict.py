from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class DictItem(SQLModel, table=True):
    __tablename__ = "sys_dicts"

    id: Optional[int] = Field(default=None, primary_key=True)
    category: str = Field(index=True, description="字典分类，如 user_status")
    code: str = Field(index=True, description="字典键值，如 1")
    label: str = Field(description="字典显示名，如 启用")
    sort_order: int = Field(default=0, description="排序")
    description: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)