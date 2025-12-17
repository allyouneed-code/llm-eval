import json
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from typing import List

from app.core.database import get_session
from app.models.task import EvaluationTask
from app.models.llm_model import LLMModel
# === 修正部分 ===
from app.models.dataset import DatasetConfig 
# ================
from app.schemas.task_schema import TaskCreate, TaskRead

from app.worker.celery_app import run_evaluation_task

router = APIRouter()

@router.post("/", response_model=TaskRead)
def create_task(task_in: TaskCreate, session: Session = Depends(get_session)):
    model = session.get(LLMModel, task_in.model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # === 修正部分 Start: 使用 config_ids ===
    # 验证前端传来的 config_ids 是否存在
    statement = select(DatasetConfig).where(DatasetConfig.id.in_(task_in.config_ids))
    configs = session.exec(statement).all()
    
    if len(configs) != len(task_in.config_ids):
        raise HTTPException(status_code=400, detail="部分评测配置(Dataset Config)不存在")
    
    # 存储 ID 列表
    datasets_json = json.dumps(task_in.config_ids)
    # === 修正部分 End ===
    
    db_task = EvaluationTask(
        model_id=task_in.model_id,
        datasets_list=datasets_json,
        status="pending",
        progress=0
    )
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    
    run_evaluation_task.delay(db_task.id)
    
    return db_task

@router.get("/", response_model=List[TaskRead])
def read_tasks(session: Session = Depends(get_session)):
    tasks = session.exec(select(EvaluationTask)).all()
    return tasks

@router.get("/{task_id}", response_model=TaskRead)
def read_task(task_id: int, session: Session = Depends(get_session)):
    task = session.get(EvaluationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task