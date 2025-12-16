import os
import shutil
import pandas as pd
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse # 新增：用于文件下载
from sqlmodel import Session, select
from typing import List, Optional

from app.core.database import get_session
from app.models.dataset import Dataset
from app.schemas.dataset_schema import DatasetRead

router = APIRouter()

UPLOAD_DIR = "data/datasets"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- 辅助函数：解析文件预览数据 ---
def _parse_preview_data(filepath_or_buffer, filename: str):
    filename = filename.lower()
    df = None
    
    if filename.endswith(".csv"):
        df = pd.read_csv(filepath_or_buffer, nrows=5, on_bad_lines='skip')
    elif filename.endswith(".json"):
        df = pd.read_json(filepath_or_buffer)
        df = df.head(5)
    elif filename.endswith(".jsonl"):
        # chunksize 返回的是 TextFileReader，需要迭代
        with pd.read_json(filepath_or_buffer, lines=True, chunksize=5) as reader:
            for chunk in reader:
                df = chunk
                break
    elif filename.endswith(".xlsx") or filename.endswith(".xls"):
        df = pd.read_excel(filepath_or_buffer, nrows=5)
    else:
        raise ValueError("不支持的文件格式")

    if df is not None:
        # 处理 NaN，防止 JSON 序列化报错
        df = df.where(pd.notnull(df), None)
        return {
            "columns": list(df.columns),
            "rows": df.to_dict(orient="records")
        }
    return {"columns": [], "rows": []}


# ==========================================
# 接口 1: 上传前预览 (接收 UploadFile)
# ==========================================
@router.post("/preview")
def preview_dataset(file: UploadFile = File(...)):
    try:
        return _parse_preview_data(file.file, file.filename)
    except Exception as e:
        print(f"Preview Error: {e}")
        raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")


# ==========================================
# 接口 2: 预览已保存的数据集 (接收 dataset_id)
# ==========================================
@router.get("/{dataset_id}/preview")
def preview_saved_dataset(dataset_id: int, session: Session = Depends(get_session)):
    dataset = session.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    
    if not os.path.exists(dataset.path):
        raise HTTPException(status_code=404, detail="源文件在服务器上已丢失")
    
    try:
        # 传入本地文件路径
        return _parse_preview_data(dataset.path, dataset.path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"读取文件失败: {str(e)}")


# ==========================================
# 接口 3: 下载数据集文件
# ==========================================
@router.get("/{dataset_id}/download")
def download_dataset_file(dataset_id: int, session: Session = Depends(get_session)):
    dataset = session.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    
    if not os.path.exists(dataset.path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 提取文件名
    filename = os.path.basename(dataset.path)
    
    return FileResponse(
        path=dataset.path, 
        filename=filename, 
        media_type='application/octet-stream'
    )


# ==========================================
# 接口 4: 创建数据集
# ==========================================
@router.post("/", response_model=DatasetRead)
def create_dataset(
    name: str = Form(...),
    capability: str = Form(...),
    metric_name: str = Form("Accuracy"),
    evaluator_config: str = Form('{"type": "AccEvaluator"}'), 
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    # 1. 查重
    statement = select(Dataset).where(Dataset.name == name)
    existing = session.exec(statement).first()
    if existing:
        raise HTTPException(status_code=400, detail="数据集名称已存在")
    
    # 2. 保存文件
    file_ext = os.path.splitext(file.filename)[1]
    save_name = f"{name}_{capability}{file_ext}"
    save_path = os.path.join(UPLOAD_DIR, save_name)
    
    file.file.seek(0)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 3. 入库
    abs_path = os.path.abspath(save_path)
    
    db_dataset = Dataset(
        name=name,
        capability=capability,
        metric_name=metric_name,
        description=description,
        path=abs_path,
        evaluator_config=evaluator_config 
    )
    
    session.add(db_dataset)
    session.commit()
    session.refresh(db_dataset)
    
    return db_dataset


@router.get("/", response_model=List[DatasetRead])
def read_datasets(session: Session = Depends(get_session)):
    datasets = session.exec(select(Dataset)).all()
    return datasets

@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: int, session: Session = Depends(get_session)):
    dataset = session.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    if os.path.exists(dataset.path):
        os.remove(dataset.path)
        
    session.delete(dataset)
    session.commit()
    return {"ok": True}