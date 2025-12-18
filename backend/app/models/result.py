from typing import Optional, Dict
from sqlmodel import SQLModel, Field, Column, JSON, Relationship
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.task import EvaluationTask
    from app.models.dataset import DatasetConfig

class EvaluationResult(SQLModel, table=True):
    __tablename__ = "evaluation_results"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 关联外键
    task_id: int = Field(foreign_key="evaluation_tasks.id", index=True)
    dataset_config_id: int = Field(foreign_key="dataset_configs.id", index=True)
    
    # 核心指标 (结构化字段，方便排序和筛选)
    metric_name: str  # 例如 "Accuracy", "BLEU", "Pass@1"
    score: float      # 例如 85.5, 62.0
    
    # 冗余字段 (可选，但建议加): 方便不查表就能知道是哪个数据集
    dataset_name: str 
    
    # 详细结果 (存 JSON)
    # 这里可以存更细的数据，比如混淆矩阵、分类报告等
    details: Optional[Dict] = Field(default={}, sa_column=Column(JSON))
    
    # 定义关系 (方便 ORM 操作)
    task: "EvaluationTask" = Relationship(back_populates="results")
    dataset_config: "DatasetConfig" = Relationship(back_populates="results")