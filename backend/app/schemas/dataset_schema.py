import json
from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel
from pydantic import field_validator, model_validator

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
    
    # 🆕 新增：任务类型 (规范约定：qa / multiple_choice / cloze)
    # 用于前端回显和业务逻辑分流
    task_type: str = "qa" 
    
    mode: str = "gen" # gen / ppl
    prompt_version: Optional[str] = None
    
    # 🌟 UI展示用的指标名称 (如 "Accuracy", "BLEU")
    display_metric: str = "Accuracy"
    
    # 配置详情 (JSON 字符串)
    reader_cfg: str = "{}"
    infer_cfg: str = "{}"
    metric_config: str = "{}" # 对应 evaluator_config

    # 🆕 新增字段 (Base中定义，Create/Read自动继承)
    post_process_cfg: str = "{}"  # 答案提取配置
    few_shot_cfg: str = "{}"      # 少样本配置

# 🌟 新增：用于创建配置的 Schema，包含校验逻辑
class DatasetConfigCreate(DatasetConfigBase):
    meta_id: int
    file_path: str  # 必须指定文件路径

    # --- 校验 1: 确保所有 cfg 字段都是合法的 JSON ---
    @field_validator('reader_cfg', 'infer_cfg', 'metric_config', 'post_process_cfg', 'few_shot_cfg')
    def must_be_valid_json(cls, v):
        try:
            parsed = json.loads(v)
            if not isinstance(parsed, dict):
                raise ValueError("Content must be a JSON object (dict)")
            return v
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON string format")

    # --- 校验 2: Reader 必须包含规范约定的字段 ---
    @field_validator('reader_cfg')
    def validate_reader(cls, v):
        try:
            cfg = json.loads(v)
            
            # 1. 检查 OpenCompass 运行必需字段
            if 'input_columns' not in cfg or 'output_column' not in cfg:
                raise ValueError("Reader Config must contain 'input_columns' and 'output_column'")
            
            # 🆕 2. 检查前端回显必需字段 (规范约定)
            # 强制要求必须存 mapping，否则拒绝创建
            if 'mapping' not in cfg:
                raise ValueError("Reader Config must contain 'mapping' for frontend display")
            
            if not isinstance(cfg['mapping'], dict):
                raise ValueError("'mapping' field must be a dictionary")
                
        except json.JSONDecodeError:
            pass # 格式错误会在 validate_json 中被捕获，这里忽略
        except Exception as e:
            # 抛出具体业务错误
            raise ValueError(f"Reader Config convention error: {str(e)}")
        return v

    # --- 校验 3: PPL 模式下的特殊逻辑 ---
    @model_validator(mode='after')
    def validate_mode_logic(self):
        # ... (保持原有逻辑不变) ...
        if self.mode == 'ppl':
            try:
                infer_data = json.loads(self.infer_cfg)
                prompt_cfg = infer_data.get('prompt_template', {})
                template = prompt_cfg.get('template')
                
                if template and not isinstance(template, dict):
                    raise ValueError("In PPL mode, prompt_template.template must be a dictionary mapping options to prompts")
            except Exception as e:
                if "dictionary" in str(e):
                    raise e
        return self

class DatasetConfigRead(DatasetConfigBase):
    id: int
    created_at: datetime = datetime.utcnow()
    file_path: str
    
    metrics: List[EvaluationMetricRead] = []

# ==========================================
# Level 1: 数据集元数据 (Meta)
# ==========================================
class DatasetMetaBase(SQLModel):
    name: str
    category: str = "Base"
    description: Optional[str] = None
    modality: str = "Text"
    
    # 🆕 保持之前添加的软删除字段定义（如果之前在 Model 加了，Schema 最好也体现，或者在 Read 中体现）
    # 但通常 Base 里不放 is_deleted 避免创建时被篡改，这里只需 Read 里有即可
    # is_deleted: bool = False 

class DatasetMetaCreate(DatasetMetaBase):
    pass

class DatasetMetaRead(DatasetMetaBase):
    id: int
    created_at: datetime
    # 🆕 软删除标记
    is_deleted: bool 
    
    # 🌟 关键：在列表页直接返回 configs
    configs: List[DatasetConfigRead] = []

class DatasetMetaDetail(DatasetMetaRead):
    pass

class DatasetPaginationResponse(SQLModel):
    total: int
    items: List[DatasetMetaRead]

# === 🌟 新增：分类统计结构 ===
class CategoryStat(SQLModel):
    category: str
    count: int