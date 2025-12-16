from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from typing import List

from app.core.database import get_session
from app.models.llm_model import LLMModel
from app.schemas.model_schema import ModelCreate, ModelRead

router = APIRouter()


# ==========================================
# 接口 1: 注册新模型 (POST /api/v1/models/)
# ==========================================
@router.post("/", response_model=ModelRead)
def create_model(model_in: ModelCreate, session: Session = Depends(get_session)):
    # 1. 校验名称是否重复
    # SQL: SELECT * FROM llm_models WHERE name = 'xxx'
    statement = select(LLMModel).where(LLMModel.name == model_in.name)
    existing_model = session.exec(statement).first()
    
    if existing_model:
        raise HTTPException(status_code=400, detail="Model with this name already exists")
    
    # 2. 将 Schema (DTO) 转换为 Table Model
    # 这里的 from_orm 是 Pydantic/SQLModel 的魔法，自动把字段拷过去
    db_model = LLMModel.model_validate(model_in)
    
    # 3. 存入数据库
    session.add(db_model)
    session.commit()      # 提交事务
    session.refresh(db_model) # 刷新，拿到数据库自动生成的 id
    
    return db_model

# ==========================================
# 接口 2: 获取模型列表 (GET /api/v1/models/)
# ==========================================
@router.get("/", response_model=List[ModelRead])
def read_models(session: Session = Depends(get_session)):
    models = session.exec(select(LLMModel)).all()
    return models

# ==========================================
# 接口 3: 删除模型
# ==========================================
@router.delete("/{model_id}")
def delete_model(model_id: int, session: Session = Depends(get_session)):
    # 1. 根据 ID 查找模型
    model = session.get(LLMModel, model_id)
    
    # 2. 如果没找到，报 404
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # 3. 删除并提交
    session.delete(model)
    session.commit()
    
    return {"ok": True, "message": f"Model {model.name} deleted"}