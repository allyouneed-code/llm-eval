import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload 

from app.core.database import get_session
from app.models.dataset import DatasetConfig
from app.models.scheme import EvaluationScheme
from app.schemas.scheme_schema import EvaluationSchemeCreate, EvaluationSchemeRead

router = APIRouter()

@router.post("/", response_model=EvaluationSchemeRead)
def create_scheme(scheme_in: EvaluationSchemeCreate, session: Session = Depends(get_session)):
    # 1. 查重
    existing = session.exec(select(EvaluationScheme).where(EvaluationScheme.name == scheme_in.name)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Scheme name already exists")
    
    # 2. 创建方案基础对象
    db_scheme = EvaluationScheme(
        name=scheme_in.name,
        description=scheme_in.description
    )
    # 先 add 但不 commit，为了让它生成 ID
    session.add(db_scheme)
    
    # 3. 处理关联 (Many-to-Many)
    current_config_ids = []
    if scheme_in.dataset_config_ids:
        # 查询出实际存在的 configs
        statement = select(DatasetConfig).where(DatasetConfig.id.in_(scheme_in.dataset_config_ids))
        configs = session.exec(statement).all()
        
        if not configs and scheme_in.dataset_config_ids:
            # 如果传了ID但数据库查不到，说明ID无效
            print(f"⚠️ Warning: Config IDs {scheme_in.dataset_config_ids} not found in DB.")
        
        # SQLModel 魔法：直接赋值对象列表，它会自动维护中间表
        db_scheme.configs = configs
        # 记录一下 ID 用于直接返回，防止 refresh 后懒加载失效
        current_config_ids = [c.id for c in configs]
        
    session.commit()
    session.refresh(db_scheme)
    
    # 4. 返回
    return EvaluationSchemeRead(
        id=db_scheme.id,
        name=db_scheme.name,
        description=db_scheme.description,
        # 手动填入刚才关联的 ID
        dataset_config_ids=current_config_ids, 
        created_at=db_scheme.created_at
    )

@router.get("/", response_model=List[EvaluationSchemeRead])
def read_schemes(session: Session = Depends(get_session)):
    statement = select(EvaluationScheme).options(selectinload(EvaluationScheme.configs))
    schemes = session.exec(statement).all()
    
    results = []
    for s in schemes:
        results.append(EvaluationSchemeRead(
            id=s.id,
            name=s.name,
            description=s.description,
            # 提取关联对象的 ID
            dataset_config_ids=[c.id for c in s.configs],
            created_at=s.created_at
        ))
    return results

@router.delete("/{scheme_id}")
def delete_scheme(scheme_id: int, session: Session = Depends(get_session)):
    scheme = session.get(EvaluationScheme, scheme_id)
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")
    
    session.delete(scheme)
    session.commit()
    return {"ok": True}