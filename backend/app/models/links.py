from typing import Optional
from sqlmodel import SQLModel, Field

# 这是一个纯关联表，用于连接 EvaluationTask 和 DatasetConfig
class TaskDatasetLink(SQLModel, table=True):
    __tablename__ = "task_dataset_links"
    
    # 复合主键：Task ID + Config ID
    task_id: int = Field(foreign_key="evaluation_tasks.id", primary_key=True)
    dataset_config_id: int = Field(foreign_key="dataset_configs.id", primary_key=True)
    
    # 🌟 核心优化：配置快照
    # 在任务创建时，把 DatasetConfig 的内容转成 JSON 存下来。
    # 即使未来 DatasetConfig 被修改了，这个任务的历史记录依然是准确的。
    config_snapshot: Optional[str] = Field(default=None)