from typing import List, Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from sqlalchemy import Column, Text
# 引入 Link 表
from app.models.links import TaskDatasetLink
from app.models.scheme import SchemeDatasetLink, EvaluationScheme

if TYPE_CHECKING:
    from app.models.task import EvaluationTask
    from app.models.result import EvaluationResult

# ==========================================
# 1. 数据集元数据表 (DatasetMeta)
# ==========================================
class DatasetMeta(SQLModel, table=True):
    __tablename__ = "dataset_metas"

    id: Optional[int] = Field(default=None, primary_key=True)
    
    name: str = Field(index=True, unique=True)
    category: str = Field(default="Base")
    description: Optional[str] = None
    
    # 🆕 新增：软删除标记
    is_deleted: bool = Field(default=False)

    modality: str = Field(default="Text") #数据模态 (Text, Image, Audio, Video)
    
    data_count: int = Field(default=0)
    # 关系定义保持原样，不需要加 cascade="all, delete-orphan" 了
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
    
    # 🌟 关键字段：确保这些都在！
    file_path: str 
    task_type: str = Field(default="multiple_choice", index=True)
    mode: str = Field(default="gen")         # gen / ppl
    prompt_version: Optional[str] = None
    display_metric: str = Field(default="Accuracy") 
    
    # 复杂配置 (存 JSON)
    reader_cfg: str = Field(default="{}", sa_column=Column(Text)) 
    infer_cfg: str = Field(default="{}", sa_column=Column(Text))
    metric_config: str = Field(default="{}", sa_column=Column(Text)) 
    
    # 后处理配置
    post_process_cfg: str = Field(default="{}", sa_column=Column(Text)) 
    
    # 少样本配置
    few_shot_cfg: str = Field(default="{}", sa_column=Column(Text))
    
    # =========================
    # 🆕 新增字段 End
    # =========================
    
    metrics: List["EvaluationMetric"] = Relationship(back_populates="config")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # 🌟 关系定义
    tasks: List["EvaluationTask"] = Relationship(back_populates="datasets", link_model=TaskDatasetLink)
    results: List["EvaluationResult"] = Relationship(back_populates="dataset_config")

    schemes: List[EvaluationScheme] = Relationship(
        back_populates="configs", 
        link_model=SchemeDatasetLink
    )

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