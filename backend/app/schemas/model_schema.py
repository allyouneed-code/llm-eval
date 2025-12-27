from sqlmodel import SQLModel
from typing import Optional
from datetime import datetime

# 基础模型，包含共有字段
class ModelBase(SQLModel):
    name: str
    path: str
    type: str = "local"
    param_size: str = "Unknown"
    api_key: Optional[str] = None
    config_json: Optional[str] = "{}"
    description: Optional[str] = None
    base_url: Optional[str] = None

# 1. 接收前端创建请求的模型 (Create DTO)
# 用户只需要填这些，id 和 created_at 不需要填
class ModelCreate(ModelBase):
    pass

# 2. 返回给前端的模型 (Read DTO)
# 返回时，我们把数据库生成的 id 和 created_at 带上
class ModelRead(ModelBase):
    id: int
    created_at: datetime