from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class LLMModel(SQLModel, table=True):
    __tablename__ = "llm_models"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    
    # === 新增：参数量 ===
    # 用字符串存，方便存 "7B", "175B", "Unknown"
    param_size: str = Field(default="Unknown") 
    
    type: str = Field(default="local") # local 或 api
    path: str # 本地路径 或 API Base URL
    
    # === 优化：API Key 单独拎出来 ===
    # 无论是云端还是私有端，如果有 Key 就填，没 Key 就空着
    api_key: Optional[str] = Field(default=None)
    
    # 其他复杂配置 (如 context_window, template_type) 依然丢进 JSON
    config_json: Optional[str] = Field(default="{}") 
    
    created_at: datetime = Field(default_factory=datetime.utcnow)