from sqlmodel import SQLModel
from typing import Optional
from datetime import datetime

# 基础字段：前后端交互的公约数
class DatasetBase(SQLModel):
    name: str
    path: str
    metric_name: str = "Accuracy" # 给前端展示的指标名
    # 给引擎看的配置 (JSON字符串)，默认给个最通用的
    evaluator_config: str = '{"type": "AccEvaluator"}' 
    description: Optional[str] = None

# 1. 创建时 (Create DTO)
class DatasetCreate(DatasetBase):
    pass

# 2. 读取时 (Read DTO)
class DatasetRead(DatasetBase):
    id: int
    created_at: datetime # 必须是 datetime 类型