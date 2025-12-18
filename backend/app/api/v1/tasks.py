import json
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from typing import List

from app.core.database import get_session
from app.models.task import EvaluationTask
from app.models.llm_model import LLMModel
from app.models.dataset import DatasetConfig
# 引入新定义的 Link 表
from app.models.links import TaskDatasetLink 
from app.schemas.task_schema import TaskCreate, TaskRead
from app.worker.celery_app import run_evaluation_task

router = APIRouter()

@router.post("/", response_model=TaskRead)
def create_task(task_in: TaskCreate, session: Session = Depends(get_session)):
    # 1. 检查模型是否存在
    model = session.get(LLMModel, task_in.model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # 2. 检查配置是否存在
    statement = select(DatasetConfig).where(DatasetConfig.id.in_(task_in.config_ids))
    configs = session.exec(statement).all()
    
    if len(configs) != len(task_in.config_ids):
        raise HTTPException(status_code=400, detail="部分评测配置不存在")
    
    # 3. 创建任务 (保留 datasets_list 字符串以兼容旧前端)
    datasets_json = json.dumps(task_in.config_ids)
    
    db_task = EvaluationTask(
        model_id=task_in.model_id,
        datasets_list=datasets_json, # 兼容旧字段
        status="pending",
        progress=0
    )
    session.add(db_task)
    session.commit()
    session.refresh(db_task) #以此获取 db_task.id
    
    # 🌟 4. [新增逻辑] 写入 TaskDatasetLink 中间表
    for config in configs:
        # 序列化当前配置，作为快照
        # model_dump() 是 Pydantic v2 / SQLModel 的方法
        # 如果你用的是旧版 Pydantic，可能需要用 .dict()
        snapshot_json = json.dumps(config.model_dump(mode='json'), default=str)
        
        link = TaskDatasetLink(
            task_id=db_task.id,
            dataset_config_id=config.id,
            config_snapshot=snapshot_json
        )
        session.add(link)
    
    # 再次提交，保存 Link 关系
    session.commit()
    
    # 5. 触发 Celery 任务
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