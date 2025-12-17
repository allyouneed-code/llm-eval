from sqlmodel import SQLModel
from typing import List, Optional
from datetime import datetime

# 基础字段
class TaskBase(SQLModel):
    model_id: int
    pass

# 1. 创建任务请求 (前端传来的)
class TaskCreate(SQLModel):
    model_id: int
    # 变更点：改为 config_ids，明确指向 DatasetConfig 表的主键
    config_ids: List[int]  # 例如: [1, 5, 8] (对应 GSM8K-Gen, C-Eval-PPL 等)

# 2. 读取任务响应 (返回给前端的)
class TaskRead(SQLModel):
    id: int
    model_id: int
    status: str
    progress: int
    # 这里返回的是配置ID列表的 JSON 字符串，例如 '[1, 5, 8]'
    # 前端获取后，可以拿着这些 ID 去 DatasetConfig 接口查询具体名称，或者后端在详情接口做聚合
    datasets_list: str 
    result_summary: Optional[str] = None
    created_at: datetime
    error_msg: Optional[str] = None