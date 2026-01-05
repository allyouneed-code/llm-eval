from typing import List, Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime

if TYPE_CHECKING:
    from app.models.dataset import DatasetConfig

# ==========================================
# 🆕 中间表：方案 <-> 数据集配置
# ==========================================
class SchemeDatasetLink(SQLModel, table=True):
    __tablename__ = "scheme_dataset_links"
    
    scheme_id: Optional[int] = Field(
        default=None, foreign_key="evaluation_schemes.id", primary_key=True
    )
    dataset_config_id: Optional[int] = Field(
        default=None, foreign_key="dataset_configs.id", primary_key=True
    )

# ==========================================
# 评测方案表
# ==========================================
class EvaluationScheme(SQLModel, table=True):
    __tablename__ = "evaluation_schemes"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: Optional[str] = None

    is_active: bool = Field(default=True)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # 🌟 核心变化：不再存 JSON，而是通过 relationship 关联
    configs: List["DatasetConfig"] = Relationship(
        back_populates="schemes", 
        link_model=SchemeDatasetLink
    )