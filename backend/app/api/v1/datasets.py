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
# 引入新 Schema (确保你之前已经更新了 schemas/dataset_schema.py)
from app.schemas.dataset_schema import DatasetMetaRead

router = APIRouter()

UPLOAD_DIR = "data/datasets"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def _parse_preview_data(filepath_or_buffer, filename: str):
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

@router.post("/preview")
def preview_dataset(file: UploadFile = File(...)):
    return _parse_preview_data(file.file, file.filename)

@router.get("/{meta_id}/preview")
def preview_saved_dataset(meta_id: int, session: Session = Depends(get_session)):
    """
    预览数据集：默认预览该数据集下的第一个配置对应的文件
    """
    meta = session.get(DatasetMeta, meta_id)
    if not meta or not meta.configs:
        raise HTTPException(status_code=404, detail="未找到相关数据文件")
    
    # 默认取第一个配置的文件
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

# === 核心修改：创建逻辑适配新模型 ===
@router.post("/", response_model=DatasetMetaRead)
def create_dataset(
    name: str = Form(...),
    category: str = Form(...), # 对应前端传来的 category (原 capability)
    mode: str = Form("gen"),   # 新增字段
    metric_name: str = Form("Accuracy"),
    evaluator_config: str = Form('{"type": "AccEvaluator"}'), 
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
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
    
    # 2. 保存文件
    file_ext = os.path.splitext(file.filename)[1]
    # 文件名增加 mode 区分，如 GSM8K_gen.jsonl
    save_name = f"{name}_{mode}{file_ext}"
    save_path = os.path.join(UPLOAD_DIR, save_name)
    
    file.file.seek(0)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 3. 创建配置 (DatasetConfig)
    abs_path = os.path.abspath(save_path)
    
    # 检查是否已存在同名同模式的配置
    existing_config = next((c for c in meta.configs if c.mode == mode), None)
    if existing_config:
        # 如果存在，更新路径和配置
        existing_config.file_path = abs_path
        existing_config.metric_config = evaluator_config
        existing_config.display_metric = metric_name
        session.add(existing_config)
    else:
        # 创建新配置
        config = DatasetConfig(
            meta_id=meta.id,
            config_name=f"{name}_{mode}",
            file_path=abs_path,
            mode=mode,
            metric_config=evaluator_config,
            display_metric=metric_name,
            reader_cfg=json.dumps({"path": abs_path}) # 简单存一下
        )
        session.add(config)
    
    session.commit()
    session.refresh(meta)
    return meta

@router.get("/", response_model=List[DatasetMetaRead])
def read_datasets(session: Session = Depends(get_session)):
    # 这里的 DatasetMetaRead 应该包含 configs 字段，以便前端展开
    datasets = session.exec(select(DatasetMeta)).unique().all()
    return datasets

@router.delete("/{meta_id}")
def delete_dataset(meta_id: int, session: Session = Depends(get_session)):
    meta = session.get(DatasetMeta, meta_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # 级联删除文件 (可选)
    for config in meta.configs:
        if os.path.exists(config.file_path):
            try:
                os.remove(config.file_path)
            except:
                pass
        
    session.delete(meta)
    session.commit()
    return {"ok": True}