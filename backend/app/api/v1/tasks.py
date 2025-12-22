from typing import List
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session

from app.core.database import get_session
from app.schemas.task_schema import TaskCreate, TaskRead
from app.services.task_service import TaskService
from app.worker.celery_app import run_evaluation_task

router = APIRouter()

@router.post("/", response_model=TaskRead)
def create_task(
    task_in: TaskCreate, 
    session: Session = Depends(get_session)
):
    # 初始化 Service
    service = TaskService(session)
    
    # 1. 调用 Service 创建任务 (包含验证和数据库操作)
    db_task = service.create_task(task_in)
    
    # 2. 触发异步任务 (Infrastructure 层操作，保留在 API 层或通过 Event 触发)
    run_evaluation_task.delay(db_task.id)
    
    return db_task

@router.get("/", response_model=List[TaskRead])
def read_tasks(session: Session = Depends(get_session)):
    service = TaskService(session)
    return service.get_all_tasks()

@router.get("/{task_id}", response_model=TaskRead)
def read_task(task_id: int, session: Session = Depends(get_session)):
    service = TaskService(session)
    task = service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task