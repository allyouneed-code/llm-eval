from sqlmodel import SQLModel
from typing import Optional, List
from datetime import datetime

# ==========================================
# Level 3: 评估指标 (Metric)
# ==========================================
class EvaluationMetricBase(SQLModel):
    evaluator_type: str
    name: str
    eval_cfg: str = "{}"

class EvaluationMetricRead(EvaluationMetricBase):
    id: int

# ==========================================
# Level 2: 评测配置 (Config)
# ==========================================
class DatasetConfigBase(SQLModel):
    config_name: str
    mode: str = "gen"
    prompt_version: Optional[str] = None
    
    # 🌟 新增：UI展示用的指标名称 (如 "Accuracy", "BLEU")
    # 这对应模型中的 display_metric 字段
    display_metric: str = "Accuracy"
    
    # 配置详情 (JSON 字符串)
    reader_cfg: str = "{}"
    infer_cfg: str = "{}"
    metric_config: str = "{}" # 对应 evaluator_config

class DatasetConfigRead(DatasetConfigBase):
    id: int
    # 注意：通常出于安全考虑，不将绝对路径 file_path 返回给前端
    # 前端下载或预览时只需使用 config.id 即可
    
    metrics: List[EvaluationMetricRead] = []

# ==========================================
# Level 1: 数据集元数据 (Meta)
# ==========================================
class DatasetMetaBase(SQLModel):
    name: str
    category: str = "Base"
    description: Optional[str] = None

class DatasetMetaCreate(DatasetMetaBase):
    pass

class DatasetMetaRead(DatasetMetaBase):
    id: int
    created_at: datetime
    
    # 🌟 关键：在列表页直接返回 configs
    # 这样前端 DatasetView 才能遍历显示 "Gen (Accuracy)" 等标签
    configs: List[DatasetConfigRead] = []

class DatasetMetaDetail(DatasetMetaRead):
    pass