import os
import shutil
import json
import zipfile
import pandas as pd
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlmodel import Session, select, func, or_
from sqlalchemy.orm import selectinload 
from typing import List, Optional, Dict, Any
from sqlalchemy import desc, asc  # 🆕 确保引入排序函数

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
# 1. 核心工具：数据扁平化 (Flatten Logic)
# ==========================================

def _flatten_row(row: Dict[str, Any], parent_key: str = '', sep: str = '_') -> Dict[str, Any]:
    """
    递归扁平化 JSON 行，并智能处理 choices 列表
    """
    items = {}
    for k, v in row.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        
        if isinstance(v, dict):
            items.update(_flatten_row(v, new_key, sep=sep))
        elif isinstance(v, list):
            is_choice_list = False
            extracted = {}
            if v and isinstance(v[0], dict):
                first_keys = v[0].keys()
                label_key = next((lk for lk in ['label', 'key', 'option'] if lk in first_keys), None)
                text_key = next((tk for tk in ['text', 'content', 'value'] if tk in first_keys), None)
                if label_key and text_key:
                    is_choice_list = True
                    for item in v:
                        if label_key in item and text_key in item:
                            label_val = item[label_key]
                            col_name = f"{new_key}{sep}{label_val}"
                            extracted[col_name] = item[text_key]
            
            if is_choice_list:
                items.update(extracted)
            else:
                items[new_key] = v
        else:
            items[new_key] = v
    return items

def _handle_zip_upload(upload_file: UploadFile, dataset_name: str) -> str:
    base_dir = os.path.join(UPLOAD_DIR, dataset_name)
    os.makedirs(base_dir, exist_ok=True)
    zip_path = os.path.join(base_dir, "upload.zip")
    
    upload_file.file.seek(0)
    with open(zip_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
        
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(base_dir)
    except zipfile.BadZipFile:
        shutil.rmtree(base_dir)
        raise HTTPException(status_code=400, detail="无效的 ZIP 文件")
        
    found_file = None
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.lower().endswith(".jsonl"):
                found_file = os.path.join(root, file)
                break
        if found_file: break
        for file in files:
             if file.lower().endswith(".json"):
                found_file = os.path.join(root, file)
                break
        if found_file: break

    if not found_file:
        raise HTTPException(status_code=400, detail="ZIP 包中未找到 .jsonl 或 .json 索引文件")
        
    return found_file

def _process_and_save_file(upload_file: UploadFile, save_path: str) -> int:
    """
    读取上传文件，执行扁平化处理，保存到磁盘，并返回数据行数
    """
    filename = upload_file.filename.lower()
    row_count = 0 # 🆕 初始化计数器

    if filename.endswith(".jsonl") or filename.endswith(".json"):
        rows = []
        try:
            content = upload_file.file.read()
            upload_file.file.seek(0)
            
            if filename.endswith(".jsonl"):
                lines = content.decode('utf-8').splitlines()
                for line in lines:
                    if line.strip(): rows.append(json.loads(line))
            else:
                data = json.loads(content)
                if isinstance(data, list):
                    rows = data
                else:
                    rows = [data]
            
            # 🆕 获取行数
            row_count = len(rows)
            
            flattened_rows = [_flatten_row(row) for row in rows]
            df = pd.DataFrame(flattened_rows)
            
            if save_path.endswith(".jsonl"):
                df.to_json(save_path, orient='records', lines=True, force_ascii=False)
            else:
                df.to_json(save_path, orient='records', force_ascii=False)
                
        except Exception as e:
            print(f"Flattening failed: {e}, falling back to raw copy")
            upload_file.file.seek(0)
            with open(save_path, "wb") as buffer:
                shutil.copyfileobj(upload_file.file, buffer)
            # 如果解析失败，回退时尝试简单数行数（针对 jsonl）
            if filename.endswith('.jsonl'):
                try:
                    upload_file.file.seek(0)
                    row_count = sum(1 for _ in upload_file.file)
                except: pass
    else:
        # CSV/Excel 等其他格式
        upload_file.file.seek(0)
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
        # 尝试读取行数 (CSV)
        if filename.endswith('.csv'):
            try:
                upload_file.file.seek(0)
                row_count = sum(1 for _ in upload_file.file) - 1 # 减去表头
                if row_count < 0: row_count = 0
            except: pass

    return row_count # 🆕 返回行数

def _parse_preview_data(filepath_or_buffer, filename: str):
    filename = filename.lower()
    df = None
    try:
        is_path = isinstance(filepath_or_buffer, str)
        if filename.endswith(".jsonl") or filename.endswith(".json"):
            rows = []
            if is_path:
                with open(filepath_or_buffer, 'r', encoding='utf-8') as f:
                    if filename.endswith(".jsonl"):
                        for _ in range(5):
                            line = f.readline()
                            if not line: break
                            rows.append(json.loads(line))
                    else:
                        data = json.load(f)
                        rows = data[:5] if isinstance(data, list) else [data]
            else:
                if filename.endswith(".jsonl"):
                    for _ in range(5):
                        line = filepath_or_buffer.readline()
                        if not line: break
                        rows.append(json.loads(line))
                    filepath_or_buffer.seek(0)
                else:
                    content = filepath_or_buffer.read()
                    filepath_or_buffer.seek(0)
                    data = json.loads(content)
                    rows = data[:5] if isinstance(data, list) else [data]
            flat_rows = [_flatten_row(row) for row in rows]
            df = pd.DataFrame(flat_rows)
        elif filename.endswith(".csv"):
            df = pd.read_csv(filepath_or_buffer, nrows=5, on_bad_lines='skip')
        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            df = pd.read_excel(filepath_or_buffer, nrows=5)
        
        if df is not None:
            df = df.where(pd.notnull(df), None)
            return {"columns": list(df.columns), "rows": df.to_dict(orient="records")}
    except Exception as e:
        print(f"Parse Error: {e}")
    return {"columns": [], "rows": []}

def _extract_metric_name(eval_cfg_json: str, default: str = "Accuracy") -> str:
    try:
        data = json.loads(eval_cfg_json)
        evaluator = data.get('evaluator', {})
        etype = evaluator.get('type') if isinstance(evaluator, dict) else evaluator
        s_type = str(etype)
        if 'AccEvaluator' in s_type: return 'Accuracy'
        if 'BleuEvaluator' in s_type: return 'BLEU'
        if 'RougeEvaluator' in s_type: return 'ROUGE'
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
    if not meta or meta.is_deleted or not meta.configs:
        raise HTTPException(status_code=404, detail="未找到相关数据文件")
    config = meta.configs[0]
    if not os.path.exists(config.file_path):
        raise HTTPException(status_code=404, detail="文件在磁盘上不存在")
    return _parse_preview_data(config.file_path, config.file_path)

@router.get("/{meta_id}/download")
def download_dataset_file(meta_id: int, session: Session = Depends(get_session)):
    meta = session.get(DatasetMeta, meta_id)
    if not meta or meta.is_deleted or not meta.configs:
        raise HTTPException(status_code=404, detail="未找到文件")
    config = meta.configs[0]
    if not os.path.exists(config.file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    filename = os.path.basename(config.file_path)
    return FileResponse(path=config.file_path, filename=filename, media_type='application/octet-stream')

# ==========================================
# 3. 核心接口：创建与读取
# ==========================================

@router.get("/stats")
def get_dataset_stats(session: Session = Depends(get_session)):
    # 1. 分类统计
    statement = select(DatasetMeta.category, func.count(DatasetMeta.id))\
        .where(DatasetMeta.is_deleted == False)\
        .group_by(DatasetMeta.category)
    results = session.exec(statement).all()
    categories = [{"category": row[0], "count": row[1]} for row in results]
    
    # 2. 总题量统计
    total_stmt = select(func.sum(DatasetMeta.data_count)).where(DatasetMeta.is_deleted == False)
    total_questions = session.exec(total_stmt).one() or 0
    
    return {
        "categories": categories,
        "total_questions": total_questions
    }

@router.post("/", response_model=DatasetMetaRead)
def create_dataset(
    name: str = Form(...),
    category: str = Form(...),
    modality: str = Form("Text"),
    description: Optional[str] = Form(None),
    configs_json: str = Form(...), 
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    # 1. 检查或创建元数据
    statement = select(DatasetMeta).where(DatasetMeta.name == name)
    meta = session.exec(statement).first()
    
    if not meta:
        meta = DatasetMeta(name=name, category=category, modality=modality, description=description)
        session.add(meta)
        session.commit()
        session.refresh(meta)
    else:
        if meta.is_deleted:
            meta.is_deleted = False
        meta.category = category
        meta.modality = modality
        if description: meta.description = description
        session.add(meta)
        session.commit()
    
    # 2. 保存并处理文件
    file_ext = os.path.splitext(file.filename)[1].lower()
    final_file_path = ""
    current_count = 0 # 🆕 初始化当前文件行数

    if file_ext == ".zip":
        raw_index_path = _handle_zip_upload(file, name)
        save_name = f"{name}_processed.jsonl"
        final_file_path = os.path.join(os.path.dirname(raw_index_path), save_name)
        
        with open(raw_index_path, 'rb') as f:
            try:
                content = f.read()
                rows = []
                if raw_index_path.endswith(".jsonl"):
                    lines = content.decode('utf-8').splitlines()
                    for line in lines:
                        if line.strip(): rows.append(json.loads(line))
                else:
                    data = json.loads(content)
                    rows = data if isinstance(data, list) else [data]
                
                # 🆕 记录行数 (ZIP 情况)
                current_count = len(rows)

                flattened_rows = [_flatten_row(row) for row in rows]
                df = pd.DataFrame(flattened_rows)
                df.to_json(final_file_path, orient='records', lines=True, force_ascii=False)
                
            except Exception as e:
                print(f"ETL failed for zip content: {e}, using raw file")
                final_file_path = raw_index_path
                # 回退时如果可能，尝试简单计数
                try:
                    if raw_index_path.endswith('.jsonl'):
                        current_count = len(content.decode('utf-8').splitlines())
                except: pass
    else:
        if file_ext in ['.json', '.jsonl']:
            save_name = f"{name}_base.jsonl"
        else:
            save_name = f"{name}_base{file_ext}"
            
        save_path = os.path.join(UPLOAD_DIR, save_name)
        
        # 🆕 接收返回的行数 (单文件情况)
        current_count = _process_and_save_file(file, save_path)
        
        final_file_path = os.path.abspath(save_path)
    
    # 🆕 3. 关键步骤：更新 Meta.data_count
    if current_count > 0:
        meta.data_count = current_count
        session.add(meta)
        session.commit()

    abs_path = os.path.abspath(final_file_path)

    # 4. 解析配置
    try:
        configs_list = json.loads(configs_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"配置格式错误: {str(e)}")

    processed_count = 0
    errors = []

    for cfg_data in configs_list:
        try:
            cfg_data["meta_id"] = meta.id
            cfg_data["file_path"] = abs_path
            
            if not cfg_data.get("config_name"):
                mode_suffix = cfg_data.get("mode", "gen")
                cfg_data["config_name"] = f"{name}_{mode_suffix}"
            
            if not cfg_data.get("display_metric"):
                cfg_data["display_metric"] = _extract_metric_name(cfg_data.get("metric_config", "{}"))

            validated_config = DatasetConfigCreate(**cfg_data)
            
            existing = next((c for c in meta.configs if c.config_name == validated_config.config_name), None)
            if existing:
                existing.mode = validated_config.mode
                existing.file_path = validated_config.file_path
                existing.reader_cfg = validated_config.reader_cfg
                existing.infer_cfg = validated_config.infer_cfg
                existing.metric_config = validated_config.metric_config
                existing.display_metric = validated_config.display_metric
                existing.post_process_cfg = validated_config.post_process_cfg
                existing.few_shot_cfg = validated_config.few_shot_cfg
                session.add(existing)
            else:
                db_config = DatasetConfig(**validated_config.model_dump())
                session.add(db_config)
            
            processed_count += 1
            
        except Exception as e:
            errors.append(f"Config '{cfg_data.get('config_name', 'unknown')}': {str(e)}")
            continue

    if processed_count == 0 and errors:
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
    private_only: bool = False,
    sort_prop: Optional[str] = None,
    sort_order: Optional[str] = None
):
    offset = (page - 1) * page_size
    query = select(DatasetMeta).where(DatasetMeta.is_deleted == False)
    
    if category and category != 'All':
        query = query.where(DatasetMeta.category == category)
    if keyword:
        query = query.where(or_(DatasetMeta.name.contains(keyword), DatasetMeta.description.contains(keyword)))
    if private_only:
        query = query.join(DatasetConfig).where(DatasetConfig.file_path.not_like("official://%"))
        
    # 排序逻辑
    if sort_prop and sort_order:
        if hasattr(DatasetMeta, sort_prop):
            column = getattr(DatasetMeta, sort_prop)
            if sort_order == 'descending':
                query = query.order_by(column.desc())
            else:
                query = query.order_by(column.asc())
        else:
            query = query.order_by(DatasetMeta.id.desc())
    else:
        query = query.order_by(DatasetMeta.id.desc())
        
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
    
    files_to_delete = set()
    if meta.configs:
        for config in meta.configs:
            path = config.file_path
            if path and isinstance(path, str) and not path.startswith("official://"):
                files_to_delete.add(path)
    for file_path in files_to_delete:
        try:
            if os.path.exists(file_path) and os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"[Warning] 删除文件失败 {file_path}: {e}")
            
    meta.is_deleted = True
    session.add(meta)
    session.commit()
    return {"ok": True, "detail": "Dataset deleted"}

@router.get("/configs")
def get_all_dataset_configs(session: Session = Depends(get_session)):
    configs = session.exec(select(DatasetConfig)).all()
    return configs