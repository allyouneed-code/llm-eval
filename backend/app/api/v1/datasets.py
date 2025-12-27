import os
import shutil
import json
import pandas as pd
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlmodel import Session, select, func, or_
from sqlalchemy.orm import selectinload 
from typing import List, Optional, Dict, Any

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
    例如: 
    input: { "question": { "stem": "Q1", "choices": [{"label": "A", "text": "Apple"}] } }
    output: { "question_stem": "Q1", "question_choices_A": "Apple" }
    """
    items = {}
    for k, v in row.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        
        if isinstance(v, dict):
            # 递归处理字典
            items.update(_flatten_row(v, new_key, sep=sep))
            
        elif isinstance(v, list):
            # 🌟 智能处理列表：尝试识别为选项列表
            is_choice_list = False
            extracted = {}
            
            # 检查是否符合 [{"label": "A", "text": "..."}] 或类似结构
            # 仅当列表非空且元素为字典时检查
            if v and isinstance(v[0], dict):
                # 收集所有可能的 key
                first_keys = v[0].keys()
                # 常见的 label key
                label_key = next((lk for lk in ['label', 'key', 'option'] if lk in first_keys), None)
                # 常见的 content key
                text_key = next((tk for tk in ['text', 'content', 'value'] if tk in first_keys), None)
                
                if label_key and text_key:
                    is_choice_list = True
                    for item in v:
                        if label_key in item and text_key in item:
                            label_val = item[label_key]
                            # 生成列名，如 question_choices_A
                            col_name = f"{new_key}{sep}{label_val}"
                            extracted[col_name] = item[text_key]
            
            if is_choice_list:
                items.update(extracted)
            else:
                # 如果不是标准选项列表，保留原样 (转字符串或保留对象)
                # 为了兼容 Pandas/CSV，通常转为 JSON 字符串更安全，但这里暂保留原值
                items[new_key] = v
        else:
            items[new_key] = v
            
    return items

def _process_and_save_file(upload_file: UploadFile, save_path: str):
    """
    读取上传文件，执行扁平化处理，并保存到磁盘
    """
    filename = upload_file.filename.lower()
    
    # 仅针对 JSONL/JSON 进行高级处理
    if filename.endswith(".jsonl") or filename.endswith(".json"):
        rows = []
        try:
            # 读取内容
            content = upload_file.file.read()
            # 重置指针以便后续可能的操作 (虽然这里读完就处理了)
            upload_file.file.seek(0)
            
            # 解析
            if filename.endswith(".jsonl"):
                # JSONL: 逐行解析
                lines = content.decode('utf-8').splitlines()
                for line in lines:
                    if line.strip():
                        rows.append(json.loads(line))
            else:
                # JSON: 整体解析
                data = json.loads(content)
                if isinstance(data, list):
                    rows = data
                else:
                    rows = [data]
            
            # 执行扁平化
            flattened_rows = [_flatten_row(row) for row in rows]
            
            # 转换为 DataFrame 并保存为 JSONL (标准化格式)
            # 即使原文件是 JSON，我们也存为 JSONL，因为 OpenCompass 对 JSONL 支持最好
            df = pd.DataFrame(flattened_rows)
            
            # 强制转换为 jsonl 格式保存，覆盖原始后缀逻辑
            # 但为了保持 save_path 的扩展名一致性，我们这里如果 save_path 是 .json，也写成 json 格式
            # 建议：统一内部存储为 .jsonl 格式更优，但为了逻辑简单，我们按扩展名输出
            
            if save_path.endswith(".jsonl"):
                df.to_json(save_path, orient='records', lines=True, force_ascii=False)
            else:
                df.to_json(save_path, orient='records', force_ascii=False)
                
        except Exception as e:
            print(f"Flattening failed: {e}, falling back to raw copy")
            # 如果解析失败，回退到直接拷贝
            upload_file.file.seek(0)
            with open(save_path, "wb") as buffer:
                shutil.copyfileobj(upload_file.file, buffer)
    else:
        # CSV/Excel 直接拷贝，不做处理
        upload_file.file.seek(0)
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)

def _parse_preview_data(filepath_or_buffer, filename: str):
    """解析文件前几行用于预览 (应用扁平化逻辑)"""
    filename = filename.lower()
    df = None
    try:
        # 如果是上传对象 (UploadFile.file)，读取内容并解析
        # 这里的 filepath_or_buffer 可能是 bytes IO，也可能是路径字符串
        
        is_path = isinstance(filepath_or_buffer, str)
        
        if filename.endswith(".jsonl") or filename.endswith(".json"):
            # 针对 JSON/JSONL，先手动读取前几行进行扁平化，而不是直接用 pd.read_json
            rows = []
            if is_path:
                # 读本地文件 (预览已保存的)
                with open(filepath_or_buffer, 'r', encoding='utf-8') as f:
                    if filename.endswith(".jsonl"):
                        for _ in range(5):
                            line = f.readline()
                            if not line: break
                            rows.append(json.loads(line))
                    else:
                        # JSON 只能全读 (或者读一部分但很难控制结构)，这里假设文件不大或只预览已保存的
                        data = json.load(f)
                        rows = data[:5] if isinstance(data, list) else [data]
            else:
                # 读内存流 (上传时的预览)
                # 注意：流只能读一次，读完要 seek 回去，或者只读一部分
                # 这里简单处理：读取前 5 行 (针对 JSONL)
                if filename.endswith(".jsonl"):
                    for _ in range(5):
                        line = filepath_or_buffer.readline()
                        if not line: break
                        rows.append(json.loads(line))
                    filepath_or_buffer.seek(0) # 重置
                else:
                    # JSON 流，全读
                    content = filepath_or_buffer.read()
                    filepath_or_buffer.seek(0)
                    data = json.loads(content)
                    rows = data[:5] if isinstance(data, list) else [data]
            
            # 扁平化预览数据
            flat_rows = [_flatten_row(row) for row in rows]
            df = pd.DataFrame(flat_rows)
            
        elif filename.endswith(".csv"):
            df = pd.read_csv(filepath_or_buffer, nrows=5, on_bad_lines='skip')
        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            df = pd.read_excel(filepath_or_buffer, nrows=5)
        
        if df is not None:
            # 处理 NaN
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
        return default
    except:
        return default

# ==========================================
# 2. 预览与下载接口
# ==========================================

@router.post("/preview")
def preview_dataset(file: UploadFile = File(...)):
    # 直接使用 file.file (SpooledTemporaryFile)
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

@router.get("/stats", response_model=List[CategoryStat])
def get_dataset_stats(session: Session = Depends(get_session)):
    statement = select(DatasetMeta.category, func.count(DatasetMeta.id))\
        .where(DatasetMeta.is_deleted == False)\
        .group_by(DatasetMeta.category)
    results = session.exec(statement).all()
    stats = [{"category": row[0], "count": row[1]} for row in results]
    return stats

@router.post("/", response_model=DatasetMetaRead)
def create_dataset(
    name: str = Form(...),
    category: str = Form(...),
    description: Optional[str] = Form(None),
    configs_json: str = Form(...), 
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    # 1. 检查或创建元数据
    statement = select(DatasetMeta).where(DatasetMeta.name == name)
    meta = session.exec(statement).first()
    
    if not meta:
        meta = DatasetMeta(name=name, category=category, description=description)
        session.add(meta)
        session.commit()
        session.refresh(meta)
    else:
        if meta.is_deleted:
            meta.is_deleted = False
            meta.category = category
            if description: meta.description = description
            session.add(meta)
            session.commit()
            session.refresh(meta)
    
    # 2. 保存并处理文件 (ETL)
    file_ext = os.path.splitext(file.filename)[1].lower()
    # 强制统一使用 jsonl 作为存储格式 (如果原文件是 JSON/JSONL)
    if file_ext in ['.json', '.jsonl']:
        save_name = f"{name}_base.jsonl"
    else:
        save_name = f"{name}_base{file_ext}"
        
    save_path = os.path.join(UPLOAD_DIR, save_name)
    abs_path = os.path.abspath(save_path)
    
    # 🌟 调用处理函数：保存并扁平化
    _process_and_save_file(file, save_path)
        
    # 3. 解析并批量处理配置
    try:
        configs_list = json.loads(configs_json)
        if not isinstance(configs_list, list):
            raise ValueError("configs_json must be a list")
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
    private_only: bool = False
):
    offset = (page - 1) * page_size
    query = select(DatasetMeta).where(DatasetMeta.is_deleted == False)
    
    if category and category != 'All':
        query = query.where(DatasetMeta.category == category)
    
    if keyword:
        query = query.where(or_(DatasetMeta.name.contains(keyword), DatasetMeta.description.contains(keyword)))
    
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
    
    # ==========================================
    # 🆕 新增逻辑：删除关联的物理文件
    # ==========================================
    files_to_delete = set()
    
    # 1. 收集该数据集关联的所有唯一文件路径
    if meta.configs:
        for config in meta.configs:
            path = config.file_path
            # 确保路径存在，且不是 'official://' 等特殊标识
            if path and isinstance(path, str) and not path.startswith("official://"):
                files_to_delete.add(path)
    
    # 2. 执行物理删除
    for file_path in files_to_delete:
        try:
            if os.path.exists(file_path) and os.path.isfile(file_path):
                os.remove(file_path)
                print(f"[Delete] 已删除文件: {file_path}")
        except Exception as e:
            # 打印错误但不阻断流程，防止因文件权限问题导致无法删除数据库记录
            print(f"[Warning] 删除文件失败 {file_path}: {e}")

    # ==========================================
    
    # 3. 数据库层面处理 (保持软删除或改为硬删除)
    # 既然文件都删了，通常建议这里也可以考虑直接硬删除：session.delete(meta)
    # 但为了保持与 create_dataset 中“同名复活”逻辑兼容，目前维持软删除逻辑是安全的。
    meta.is_deleted = True
    session.add(meta)
    session.commit()
    
    return {"ok": True, "detail": "Dataset deleted and associated files removed"}

@router.get("/configs")
def get_all_dataset_configs(session: Session = Depends(get_session)):
    configs = session.exec(select(DatasetConfig)).all()
    return configs