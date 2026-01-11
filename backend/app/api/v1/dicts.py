from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.database import get_session
from app.models.dict import DictItem
from app.schemas.dict_schema import DictItemCreate, DictItemRead, DictItemUpdate
from app.deps import get_current_active_user, get_current_admin

router = APIRouter()

# 获取字典列表（支持按分类筛选）
@router.get("/", response_model=List[DictItemRead])
def read_dicts(
    category: str = None,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_active_user)
):
    query = select(DictItem)
    if category:
        query = query.where(DictItem.category == category)
    query = query.order_by(DictItem.category, DictItem.sort_order)
    return session.exec(query).all()

# 创建字典
@router.post("/", response_model=DictItemRead)
def create_dict(
    item_in: DictItemCreate,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_admin) # 建议仅管理员可操作
):
    # 检查同一分类下的 code 是否重复
    existing = session.exec(
        select(DictItem).where(DictItem.category == item_in.category, DictItem.code == item_in.code)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该分类下已存在相同的 Code")
        
    db_item = DictItem.from_orm(item_in)
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item

# 删除字典
@router.delete("/{item_id}")
def delete_dict(
    item_id: int,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_admin)
):
    item = session.get(DictItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="字典项不存在")
    session.delete(item)
    session.commit()
    return {"ok": True}