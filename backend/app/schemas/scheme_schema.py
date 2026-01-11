# backend/app/schemas/scheme_schema.py

from typing import List, Optional
from sqlmodel import SQLModel
from datetime import datetime

# 基础字段
class EvaluationSchemeBase(SQLModel):
    name: str
    description: Optional[str] = None
    dataset_config_ids: List[int] = [] # 前端传数组，后端转字符串存储

# 创建时使用
class EvaluationSchemeCreate(EvaluationSchemeBase):
    pass

# 读取/返回时使用
class EvaluationSchemeRead(EvaluationSchemeBase):
    id: int
    created_at: datetime
    

# 更新时使用（可选）
class EvaluationSchemeUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    dataset_config_ids: Optional[List[int]] = None