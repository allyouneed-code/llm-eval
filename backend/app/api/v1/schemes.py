import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload 

from app.core.database import get_session
from app.models.dataset import DatasetConfig
from app.models.scheme import EvaluationScheme
from app.schemas.scheme_schema import EvaluationSchemeCreate, EvaluationSchemeRead

# === 引入权限依赖 ===
from app.deps import get_current_active_user, get_current_admin
from app.models.user import User

router = APIRouter()

# 🔒 权限: 登录用户
@router.post("/", response_model=EvaluationSchemeRead)
def create_scheme(
    scheme_in: EvaluationSchemeCreate, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user) # <--- 仅需登录
):
    # 1. 查重 (注意：这里查的是所有，包括已删除的，保证数据库唯一性约束不冲突)
    existing = session.exec(select(EvaluationScheme).where(EvaluationScheme.name == scheme_in.name)).first()
    if existing:
        if not existing.is_active:
             raise HTTPException(status_code=400, detail="Scheme with this name exists but is deleted. Please restore it or use a different name.")
        raise HTTPException(status_code=400, detail="Scheme name already exists")
    
    # 2. 创建方案基础对象
    db_scheme = EvaluationScheme(
        name=scheme_in.name,
        description=scheme_in.description,
        is_active=True # 显式设为 True
    )
    session.add(db_scheme)
    
    # 3. 处理关联 (Many-to-Many)
    current_config_ids = []
    if scheme_in.dataset_config_ids:
        statement = select(DatasetConfig).where(DatasetConfig.id.in_(scheme_in.dataset_config_ids))
        configs = session.exec(statement).all()
        db_scheme.configs = configs
        current_config_ids = [c.id for c in configs]
        
    session.commit()
    session.refresh(db_scheme)
    
    return EvaluationSchemeRead(
        id=db_scheme.id,
        name=db_scheme.name,
        description=db_scheme.description,
        dataset_config_ids=current_config_ids, 
        created_at=db_scheme.created_at
    )

# 🔒 权限: 登录用户
@router.get("/", response_model=List[EvaluationSchemeRead])
def read_schemes(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user) # <--- 仅需登录
):
    # 🌟 修改点：只查询 is_active 为 True 的方案
    statement = select(EvaluationScheme).where(EvaluationScheme.is_active == True).options(selectinload(EvaluationScheme.configs))
    schemes = session.exec(statement).all()
    
    results = []
    for s in schemes:
        results.append(EvaluationSchemeRead(
            id=s.id,
            name=s.name,
            description=s.description,
            dataset_config_ids=[c.id for c in s.configs],
            created_at=s.created_at
        ))
    return results

# 🔒 权限: ⚠️ 仅管理员 (软删除)
@router.delete("/{scheme_id}")
def delete_scheme(
    scheme_id: int, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_admin) # <--- 强制管理员权限
):
    scheme = session.get(EvaluationScheme, scheme_id)
    # 如果找不到或者已经是 inactive 状态，都视为 404
    if not scheme or not scheme.is_active: 
        raise HTTPException(status_code=404, detail="Scheme not found")
    
    # 🌟 执行软删除
    scheme.is_active = False
    session.add(scheme)
    session.commit()
    
    return {"ok": True}