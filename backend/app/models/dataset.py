from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class Dataset(SQLModel, table=True):
    __tablename__ = "datasets"

    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 1. 基础信息
    name: str = Field(index=True, unique=True) # 如 "GSM8K", "Bank_QA"
    capability: str = Field(default="Base", index=True)
    path: str # 数据集文件路径
    
    # 2. UI 展示字段 (给人看)
    # 用于前端列表展示，简单直观。
    # 例如: "Accuracy", "Bleu Score", "Pass@1", "LLM打分"
    metric_name: str = Field(default="Accuracy") 
    
    # 3. 引擎配置字段 (给机器看)
    # 用于生成 Python 评测脚本。
    # 例如: '{"type": "opencompass.openicl.icl_evaluator.AccEvaluator"}'
    evaluator_config: str = Field(default='{"type": "AccEvaluator"}')
    
    # 4. 其他
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)