from typing import List, Optional
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime

# ==========================================
# 1. 数据集元数据表 (DatasetMeta)
# ==========================================
class DatasetMeta(SQLModel, table=True):
    __tablename__ = "dataset_metas"

    id: Optional[int] = Field(default=None, primary_key=True)
    
    name: str = Field(index=True, unique=True)
    category: str = Field(default="Base")
    description: Optional[str] = None
    
    configs: List["DatasetConfig"] = Relationship(back_populates="meta")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ==========================================
# 2. 评测配置变体表 (DatasetConfig)
# ==========================================
class DatasetConfig(SQLModel, table=True):
    __tablename__ = "dataset_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 外键
    meta_id: int = Field(foreign_key="dataset_metas.id")
    meta: Optional[DatasetMeta] = Relationship(back_populates="configs")

    # 标识
    config_name: str = Field(index=True)
    
    # 🌟 修复点：补回文件路径字段
    file_path: str 
    
    # 评测模式
    mode: str = Field(default="gen")         # gen / ppl
    prompt_version: Optional[str] = None

    # 🌟 修复点：补回前端展示用的指标字段 (对应 API 中的 metric_name)
    display_metric: str = Field(default="Accuracy") 
    
    # 复杂配置 (存 JSON)
    reader_cfg: str = Field(default="{}") 
    infer_cfg: str = Field(default="{}")
    metric_config: str = Field(default="{}") # 对应 evaluator_config
    
    metrics: List["EvaluationMetric"] = Relationship(back_populates="config")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ==========================================
# 3. 评估指标表 (EvaluationMetric)
# ==========================================
class EvaluationMetric(SQLModel, table=True):
    __tablename__ = "evaluation_metrics"

    id: Optional[int] = Field(default=None, primary_key=True)
    
    config_id: int = Field(foreign_key="dataset_configs.id")
    config: Optional[DatasetConfig] = Relationship(back_populates="metrics")
    
    evaluator_type: str
    name: str
    eval_cfg: str = Field(default="{}")