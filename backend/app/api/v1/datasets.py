import os
import shutil
import json
import pandas as pd
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlmodel import Session, select, func, or_
from sqlalchemy.orm import selectinload 
from typing import List, Optional

from app.core.database import get_session
from app.models.dataset import DatasetMeta, DatasetConfig
from app.schemas.dataset_schema import (
    DatasetMetaRead, DatasetConfigCreate, 
    DatasetPaginationResponse, CategoryStat
)

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
        evaluator = data.get('evaluator', {})
        etype = evaluator.get('type') if isinstance(evaluator, dict) else evaluator
        
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
# 3. 核心接口：创建与读取 (已重构支持多配置)
# ==========================================

@router.get("/stats", response_model=List[CategoryStat])
def get_dataset_stats(session: Session = Depends(get_session)):
    statement = select(DatasetMeta.category, func.count(DatasetMeta.id)).group_by(DatasetMeta.category)
    results = session.exec(statement).all()
    stats = [{"category": row[0], "count": row[1]} for row in results]
    return stats

@router.post("/", response_model=DatasetMetaRead)
def create_dataset(
    name: str = Form(...),
    category: str = Form(...),
    description: Optional[str] = Form(None),
    
    # 🔄 变更：接收 JSON 列表字符串，不再接收散装参数
    # 格式示例：[{"config_name": "v1", "mode": "gen", "reader_cfg": "...", "post_process_cfg": "..."}]
    configs_json: str = Form(...), 
    
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    """
    创建数据集 (Meta) + 批量创建配置 (Configs) + 上传文件
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
    # 优化：文件名不再绑定 mode，改为 base 或直接使用原始扩展名
    file_ext = os.path.splitext(file.filename)[1]
    save_name = f"{name}_base{file_ext}" # 使用 _base 后缀表示这是通用源文件
    save_path = os.path.join(UPLOAD_DIR, save_name)
    abs_path = os.path.abspath(save_path)
    
    file.file.seek(0)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 3. 解析并批量处理配置
    try:
        configs_list = json.loads(configs_json)
        if not isinstance(configs_list, list):
            raise ValueError("configs_json must be a list")
    except Exception as e:
        # 如果解析失败，清理刚上传的文件（如果是新建的）
        # 这里简单起见暂不删除，因为 meta 可能已存在
        raise HTTPException(status_code=400, detail=f"配置格式错误: {str(e)}")

    processed_count = 0
    errors = []

    for cfg_data in configs_list:
        try:
            # A. 自动补全必要字段
            cfg_data["meta_id"] = meta.id
            cfg_data["file_path"] = abs_path
            
            # B. 确保 config_name 存在，若无则自动生成
            if not cfg_data.get("config_name"):
                mode_suffix = cfg_data.get("mode", "gen")
                cfg_data["config_name"] = f"{name}_{mode_suffix}"
                
            # C. 自动提取 Display Metric (如果前端没传)
            if not cfg_data.get("display_metric"):
                cfg_data["display_metric"] = _extract_metric_name(
                    cfg_data.get("metric_config", "{}")
                )

            # D. Pydantic 校验 (包含对 post_process_cfg 等新字段的校验)
            validated_config = DatasetConfigCreate(**cfg_data)
            
            # E. 查重与入库
            # 检查该 Meta 下是否已存在同名配置
            existing = next((c for c in meta.configs if c.config_name == validated_config.config_name), None)
            
            if existing:
                # 更新模式
                existing.mode = validated_config.mode
                existing.file_path = validated_config.file_path # 更新路径
                existing.reader_cfg = validated_config.reader_cfg
                existing.infer_cfg = validated_config.infer_cfg
                existing.metric_config = validated_config.metric_config
                existing.display_metric = validated_config.display_metric
                
                # 🆕 更新新字段
                existing.post_process_cfg = validated_config.post_process_cfg
                existing.few_shot_cfg = validated_config.few_shot_cfg
                
                session.add(existing)
            else:
                # 创建模式
                db_config = DatasetConfig(**validated_config.model_dump())
                session.add(db_config)
            
            processed_count += 1
            
        except Exception as e:
            errors.append(f"Config '{cfg_data.get('config_name', 'unknown')}': {str(e)}")
            continue

    if processed_count == 0 and errors:
        # 如果一个都没成功，抛出第一个错误
        raise HTTPException(status_code=400, detail=f"导入失败: {errors[0]}")

    session.commit()
    session.refresh(meta)
    return meta

@router.get("/", response_model=DatasetPaginationResponse)
def read_datasets(
    session: Session = Depends(get_session),
    page: int = 1,
    page_size: int = 10,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    private_only: bool = False
):
    offset = (page - 1) * page_size
    
    query = select(DatasetMeta)
    
    if category and category != 'All':
        query = query.where(DatasetMeta.category == category)
    
    if keyword:
        query = query.where(
            or_(
                DatasetMeta.name.contains(keyword),
                DatasetMeta.description.contains(keyword)
            )
        )
    
    if private_only:
        query = query.join(DatasetConfig).where(DatasetConfig.file_path.not_like("official://%"))
        
    count_statement = select(func.count()).select_from(query.subquery())
    total = session.exec(count_statement).one()
    
    query = query.options(selectinload(DatasetMeta.configs))
    query = query.offset(offset).limit(page_size)
    items = session.exec(query).unique().all()
    
    return DatasetPaginationResponse(total=total, items=items)

@router.delete("/{meta_id}")
def delete_dataset(meta_id: int, session: Session = Depends(get_session)):
    meta = session.get(DatasetMeta, meta_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    for config in meta.configs:
        if os.path.exists(config.file_path):
            try:
                os.remove(config.file_path)
            except:
                pass
        
    session.delete(meta)
    session.commit()
    return {"ok": True}