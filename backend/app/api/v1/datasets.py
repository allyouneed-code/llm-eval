from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from typing import List

# 导入复用的数据库依赖
from app.core.database import get_session
# 导入数据表定义
from app.models.dataset import Dataset
# 导入刚才写的 Schema
from app.schemas.dataset_schema import DatasetCreate, DatasetRead

router = APIRouter()

# ==========================================
# 接口 1: 注册数据集
# ==========================================
@router.post("/", response_model=DatasetRead)
def create_dataset(dataset_in: DatasetCreate, session: Session = Depends(get_session)):
    # 1. 查重
    statement = select(Dataset).where(Dataset.name == dataset_in.name)
    existing = session.exec(statement).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Dataset name already exists")
    
    # 2. 入库
    db_dataset = Dataset.model_validate(dataset_in)
    session.add(db_dataset)
    session.commit()
    session.refresh(db_dataset)
    
    return db_dataset

# ==========================================
# 接口 2: 获取数据集列表
# ==========================================
@router.get("/", response_model=List[DatasetRead])
def read_datasets(session: Session = Depends(get_session)):
    datasets = session.exec(select(Dataset)).all()
    return datasets

# ==========================================
# 接口 3: 删除数据集 (本次新增，方便调试)
# ==========================================
@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: int, session: Session = Depends(get_session)):
    dataset = session.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    session.delete(dataset)
    session.commit()
    return {"ok": True}