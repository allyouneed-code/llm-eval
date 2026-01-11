from fastapi import APIRouter, HTTPException, Depends, Body
from sqlmodel import Session, select
from typing import List

from app.core.database import get_session
from app.models.llm_model import LLMModel
from app.schemas.model_schema import ModelCreate, ModelRead

from app.deps import get_current_active_user, get_current_admin
from app.models.user import User

import os
import requests

router = APIRouter()


# ==========================================
# 接口 1: 注册新模型 (POST /api/v1/models/)
# 🔒 权限: 仅管理员 (Admin)
# ==========================================
@router.post("/", response_model=ModelRead)
def create_model(
    model_in: ModelCreate, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_admin) # <--- 强制管理员权限
):
    # 1. 校验名称是否重复
    statement = select(LLMModel).where(LLMModel.name == model_in.name)
    existing_model = session.exec(statement).first()
    
    if existing_model:
        raise HTTPException(status_code=400, detail="Model with this name already exists")
    
    # 2. 将 Schema (DTO) 转换为 Table Model
    db_model = LLMModel.model_validate(model_in)
    
    # 3. 存入数据库
    session.add(db_model)
    session.commit()      
    session.refresh(db_model) 
    
    return db_model

# ==========================================
# 接口 2: 获取模型列表 (GET /api/v1/models/)
# 🔒 权限: 登录用户 (User/Admin)
# ==========================================
@router.get("/", response_model=List[ModelRead])
def read_models(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user) # <--- 仅需登录
):
    models = session.exec(select(LLMModel)).all()
    return models

# ==========================================
# 接口 3: 删除模型
# 🔒 权限: 仅管理员 (Admin)
# ==========================================
@router.delete("/{model_id}")
def delete_model(
    model_id: int, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_admin) # <--- 强制管理员权限
):
    # 1. 根据 ID 查找模型
    model = session.get(LLMModel, model_id)
    
    # 2. 如果没找到，报 404
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # 3. 删除并提交
    session.delete(model)
    session.commit()
    
    return {"ok": True, "message": f"Model {model.name} deleted"}

# 1. 校验名称唯一性
# 🔒 权限: 仅管理员 (通常是创建时的辅助接口)
@router.post("/validate/name")
def validate_name_uniqueness(
    name: str = Body(..., embed=True), 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_admin) # <--- 强制管理员权限
):
    statement = select(LLMModel).where(LLMModel.name == name)
    existing = session.exec(statement).first()
    return {"unique": not existing}