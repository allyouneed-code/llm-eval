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
    mode: str = "gen" # gen / ppl
    prompt_version: Optional[str] = None
    
    # 🌟 UI展示用的指标名称 (如 "Accuracy", "BLEU")
    # API 创建时会自动根据 metric_config 覆盖此字段，但在 Base 里保留默认值
    display_metric: str = "Accuracy"
    
    # 配置详情 (JSON 字符串)
    reader_cfg: str = "{}"
    infer_cfg: str = "{}"
    metric_config: str = "{}" # 对应 evaluator_config

# 🌟 新增：用于创建配置的 Schema，包含校验逻辑
class DatasetConfigCreate(DatasetConfigBase):
    meta_id: int
    file_path: str  # 必须指定文件路径

    # --- 校验 1: 确保所有 cfg 字段都是合法的 JSON ---
    @field_validator('reader_cfg', 'infer_cfg', 'metric_config')
    def must_be_valid_json(cls, v):
        try:
            parsed = json.loads(v)
            if not isinstance(parsed, dict):
                raise ValueError("Content must be a JSON object (dict)")
            return v
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON string format")

    # --- 校验 2: Reader 必须包含输入输出定义 ---
    @field_validator('reader_cfg')
    def validate_reader(cls, v):
        try:
            cfg = json.loads(v)
            if 'input_columns' not in cfg or 'output_column' not in cfg:
                raise ValueError("Reader Config must contain 'input_columns' and 'output_column'")
        except:
            pass # 上面的 JSON 校验会先拦截，这里忽略解析错误
        return v

    # --- 校验 3: PPL 模式下的特殊逻辑 ---
    @model_validator(mode='after')
    def validate_mode_logic(self):
        if self.mode == 'ppl':
            try:
                infer_data = json.loads(self.infer_cfg)
                # 兼容不同层级结构，这里假设标准结构是 prompt_template -> template
                # 如果结构不同，需根据实际情况调整
                prompt_cfg = infer_data.get('prompt_template', {})
                template = prompt_cfg.get('template')
                
                # 如果取不到 template，可能是结构差异，暂不强行报错，防止误杀
                if template and not isinstance(template, dict):
                    raise ValueError("In PPL mode, prompt_template.template must be a dictionary mapping options to prompts (e.g., {'0': '...', '1': '...'})")
            except Exception as e:
                # 只在明确解析失败或类型错误时报错
                if "dictionary" in str(e):
                    raise e
        return self

class DatasetConfigRead(DatasetConfigBase):
    id: int
    created_at: datetime = datetime.utcnow()
    # file_path 通常不返回给前端，或根据需要返回
    
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
    configs: List[DatasetConfigRead] = []

class DatasetMetaDetail(DatasetMetaRead):
    pass