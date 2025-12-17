from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class EvaluationTask(SQLModel, table=True):
    __tablename__ = "evaluation_tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 关联模型 (Foreign Key)
    model_id: int = Field(index=True) 
    
    # 任务状态
    status: str = Field(default="pending") # pending, running, success, failed, aborted
    
    # 进度条 (0-100)
    progress: int = Field(default=0)
    
    # 本次任务选了哪些数据集？存 JSON 列表，例如 '[1, 5, 8]' (对应 DatasetConfig 的 ID)
    datasets_list: str 
    
    # 评测结果摘要 (存 JSON，方便前端直接读取展示雷达图)
    # 例如: '{"gsm8k": 85.5, "ceval": 60.0, "total": 72.5}'
    result_summary: Optional[str] = Field(default=None)
    
    # 详细报告文件路径 (PDF/HTML)
    report_path: Optional[str] = Field(default=None)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = Field(default=None)
    
    # 错误信息 (如果失败)
    error_msg: Optional[str] = Field(default=None)