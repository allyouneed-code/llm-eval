from sqlmodel import SQLModel
from typing import List, Optional
from datetime import datetime

# 基础字段
class TaskBase(SQLModel):
    model_id: int
    # 这里的 dataset_ids 纯粹是为了接收前端的 [1, 2, 3]
    # 我们不把它直接映射到数据库表（数据库表里叫 datasets_list，是字符串）
    pass

# 1. 创建任务请求 (前端传来的)
class TaskCreate(SQLModel):
    model_id: int
    dataset_ids: List[int] # 例如: [1, 2]

# 2. 读取任务响应 (返回给前端的)
class TaskRead(SQLModel):
    id: int
    model_id: int
    status: str
    progress: int
    datasets_list: str # 返回 JSON 字符串 '["GSM8K", "C-Eval"]' 让前端解析
    result_summary: Optional[str] = None
    created_at: datetime
    error_msg: Optional[str] = None