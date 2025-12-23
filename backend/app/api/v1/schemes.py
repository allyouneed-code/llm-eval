# backend/app/api/v1/schemes.py

import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.database import get_session
from app.models.scheme import EvaluationScheme
from app.schemas.scheme_schema import EvaluationSchemeCreate, EvaluationSchemeRead
from app.models.dataset import DatasetConfig

router = APIRouter()

@router.post("/", response_model=EvaluationSchemeRead)
def create_scheme(scheme_in: EvaluationSchemeCreate, session: Session = Depends(get_session)):
    # ... 查重 ...

    # 1. 创建方案对象
    db_scheme = EvaluationScheme(
        name=scheme_in.name,
        description=scheme_in.description
    )
    session.add(db_scheme)
    session.commit()
    session.refresh(db_scheme)

    # 2. 建立关联 (写入 Link 表)
    if scheme_in.dataset_config_ids:
        # 查询出实际存在的 configs
        statement = select(DatasetConfig).where(DatasetConfig.id.in_(scheme_in.dataset_config_ids))
        configs = session.exec(statement).all()
        
        # SQLModel 会自动处理 Link 表的写入
        db_scheme.configs = configs
        session.add(db_scheme)
        session.commit()
    
    # 返回时，需手动提取 ID 列表给前端
    return EvaluationSchemeRead(
        id=db_scheme.id,
        name=db_scheme.name,
        description=db_scheme.description,
        dataset_config_ids=[c.id for c in db_scheme.configs], # 动态获取存在的ID
        created_at=db_scheme.created_at
    )

@router.get("/", response_model=List[EvaluationSchemeRead])
def read_schemes(session: Session = Depends(get_session)):
    schemes = session.exec(select(EvaluationScheme)).all()
    results = []
    for s in schemes:
        # 手动转换 dataset_config_ids
        try:
            ids = json.loads(s.dataset_config_ids)
        except:
            ids = []
            
        results.append(EvaluationSchemeRead(
            id=s.id,
            name=s.name,
            description=s.description,
            dataset_config_ids=ids,
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