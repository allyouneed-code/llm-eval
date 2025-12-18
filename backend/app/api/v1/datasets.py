import os
import shutil
import json
import pandas as pd
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlmodel import Session, select
from typing import List, Optional

from app.core.database import get_session
# 引入新模型
from app.models.dataset import DatasetMeta, DatasetConfig
# 引入新 Schema (包含 DatasetConfigCreate 校验逻辑)
from app.schemas.dataset_schema import DatasetMetaRead, DatasetConfigCreate

router = APIRouter()

UPLOAD_DIR = "data/datasets"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ==========================================
# 1. 辅助函数
# ==========================================

def _parse_preview_data(filepath_or_buffer, filename: str):
    """解析文件前几行用于预览"""
    filename = filename.lower()
    df = None
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(filepath_or_buffer, nrows=5, on_bad_lines='skip')
        elif filename.endswith(".json"):
            df = pd.read_json(filepath_or_buffer)
            df = df.head(5)
        elif filename.endswith(".jsonl"):
            with pd.read_json(filepath_or_buffer, lines=True, chunksize=5) as reader:
                for chunk in reader:
                    df = chunk
                    break
        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            df = pd.read_excel(filepath_or_buffer, nrows=5)
        
        if df is not None:
            df = df.where(pd.notnull(df), None)
            return {
                "columns": list(df.columns),
                "rows": df.to_dict(orient="records")
            }
    except Exception as e:
        print(f"Parse Error: {e}")
    return {"columns": [], "rows": []}

def _extract_metric_name(eval_cfg_json: str, default: str = "Accuracy") -> str:
    """从 metric_config JSON 中提取主要的指标名称"""
    try:
        data = json.loads(eval_cfg_json)
        # 兼容文档中的结构: evaluator -> type 或 evaluator: "AccEvaluator"
        evaluator = data.get('evaluator', {})
        etype = evaluator.get('type') if isinstance(evaluator, dict) else evaluator
        
        # 简单的映射表
        s_type = str(etype)
        if 'AccEvaluator' in s_type: return 'Accuracy'
        if 'BleuEvaluator' in s_type: return 'BLEU'
        if 'RougeEvaluator' in s_type: return 'ROUGE'
        if 'ToxicEvaluator' in s_type: return 'Toxicity'
        if 'Pass' in s_type or 'Code' in s_type: return 'Pass@k'
        return default
    except:
        return default

# ==========================================
# 2. 预览与下载接口
# ==========================================

@router.post("/preview")
def preview_dataset(file: UploadFile = File(...)):
    return _parse_preview_data(file.file, file.filename)

@router.get("/{meta_id}/preview")
def preview_saved_dataset(meta_id: int, session: Session = Depends(get_session)):
    """预览数据集：默认预览该数据集下的第一个配置对应的文件"""
    meta = session.get(DatasetMeta, meta_id)
    if not meta or not meta.configs:
        raise HTTPException(status_code=404, detail="未找到相关数据文件")
    
    config = meta.configs[0]
    if not os.path.exists(config.file_path):
        raise HTTPException(status_code=404, detail="文件在磁盘上不存在")
    
    return _parse_preview_data(config.file_path, config.file_path)

@router.get("/{meta_id}/download")
def download_dataset_file(meta_id: int, session: Session = Depends(get_session)):
    meta = session.get(DatasetMeta, meta_id)
    if not meta or not meta.configs:
        raise HTTPException(status_code=404, detail="未找到文件")
    
    config = meta.configs[0]
    if not os.path.exists(config.file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    filename = os.path.basename(config.file_path)
    return FileResponse(path=config.file_path, filename=filename, media_type='application/octet-stream')

# ==========================================
# 3. 核心接口：创建与读取
# ==========================================

@router.post("/", response_model=DatasetMetaRead)
def create_dataset(
    name: str = Form(...),
    category: str = Form(...),
    description: Optional[str] = Form(None),
    
    # === 配置相关字段 ===
    mode: str = Form("gen"),
    # 接收完整的 JSON 字符串配置
    reader_cfg: str = Form('{"input_columns":["input"], "output_column":"target"}'), 
    infer_cfg: str = Form('{}'),
    metric_config: str = Form('{"evaluator": {"type": "AccEvaluator"}}'),
    
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    """
    创建数据集 (Meta) + 默认配置 (Config) + 上传文件
    此处集成了 Pydantic 校验逻辑
    """
    
    # 1. 检查或创建元数据 (DatasetMeta)
    statement = select(DatasetMeta).where(DatasetMeta.name == name)
    meta = session.exec(statement).first()
    
    if not meta:
        meta = DatasetMeta(
            name=name,
            category=category,
            description=description
        )
        session.add(meta)
        session.commit()
        session.refresh(meta)
    
    # 2. 保存文件 (物理存储)
    file_ext = os.path.splitext(file.filename)[1]
    save_name = f"{name}_{mode}{file_ext}"
    save_path = os.path.join(UPLOAD_DIR, save_name)
    abs_path = os.path.abspath(save_path)
    
    file.file.seek(0)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 3. 准备配置数据
    # 🌟 自动提取 Display Metric
    auto_metric = _extract_metric_name(metric_config, default="Accuracy")
    
    config_data = {
        "meta_id": meta.id,
        "config_name": f"{name}_{mode}",
        "mode": mode,
        "file_path": abs_path,
        "reader_cfg": reader_cfg,
        "infer_cfg": infer_cfg,
        "metric_config": metric_config,
        "display_metric": auto_metric
    }

    # 4. 🌟 执行 Pydantic 校验
    # 如果 reader_cfg 缺少字段，或 JSON 格式错误，这里会直接抛出 422 错误
    try:
        validated_config = DatasetConfigCreate(**config_data)
    except ValueError as e:
        # 删除已上传的垃圾文件
        if os.path.exists(save_path):
            os.remove(save_path)
        raise HTTPException(status_code=400, detail=f"配置校验失败: {str(e)}")

    # 5. 存入数据库
    # 检查是否已存在同名同模式的配置
    existing_config = next((c for c in meta.configs if c.mode == mode), None)
    
    if existing_config:
        # 更新现有配置
        existing_config.file_path = validated_config.file_path
        existing_config.reader_cfg = validated_config.reader_cfg
        existing_config.infer_cfg = validated_config.infer_cfg
        existing_config.metric_config = validated_config.metric_config
        existing_config.display_metric = validated_config.display_metric
        session.add(existing_config)
    else:
        # 创建新配置
        # 注意：这里使用 validated_config.dict() 来确保使用的是清洗后的数据
        # 但 exclude 该 model 不包含的字段 (如 meta_id 已经在 db model 里定义了)
        db_config = DatasetConfig(**validated_config.model_dump())
        session.add(db_config)
    
    session.commit()
    session.refresh(meta)
    return meta

@router.get("/", response_model=List[DatasetMetaRead])
def read_datasets(session: Session = Depends(get_session)):
    # 这里的 DatasetMetaRead 包含 configs 列表
    # 确保 unique() 以避免 join 产生的重复行
    datasets = session.exec(select(DatasetMeta)).unique().all()
    return datasets

@router.delete("/{meta_id}")
def delete_dataset(meta_id: int, session: Session = Depends(get_session)):
    meta = session.get(DatasetMeta, meta_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # 级联删除文件
    for config in meta.configs:
        if os.path.exists(config.file_path):
            try:
                os.remove(config.file_path)
            except:
                pass
        
    session.delete(meta)
    session.commit()
    return {"ok": True}