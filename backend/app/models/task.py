from typing import List, Optional, TYPE_CHECKING # 引入 TYPE_CHECKING 避免运行时循环导入
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from sqlalchemy import Column, Text
from app.models.links import TaskDatasetLink
from app.models.result import EvaluationResult
if TYPE_CHECKING:
    from app.models.dataset import DatasetConfig
    

class EvaluationTask(SQLModel, table=True):
    __tablename__ = "evaluation_tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    model_id: int = Field(index=True) 
    status: str = Field(default="pending")
    progress: int = Field(default=0)
    
    # --- 旧字段 (暂时保留，为了兼容前端) ---
    datasets_list: str 
    # ----------------------------------
    scheme_id: Optional[int] = Field(default=None) #关联的方案ID

    result_summary: Optional[str] = Field(default=None, sa_column=Column(Text))
    report_path: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = Field(default=None)
    error_msg: Optional[str] = Field(default=None)

    # 🌟 新增：多对多关系
    # link_model 指定了刚才新建的中间表
    datasets: List["DatasetConfig"] = Relationship(back_populates="tasks", link_model=TaskDatasetLink)
    results: List["EvaluationResult"] = Relationship(back_populates="task")