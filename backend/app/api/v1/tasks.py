import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.models.task import EvaluationTask
from app.models.links import TaskDatasetLink
from app.models.scheme import EvaluationScheme 
from app.models.dataset import DatasetConfig # 需要引入 DatasetConfig
from app.schemas.task_schema import TaskCreate, TaskRead
from app.worker.celery_app import run_evaluation_task
from app.services.task_service import TaskService

router = APIRouter()

@router.post("/", response_model=TaskRead)
def create_task(
    task_in: TaskCreate, 
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """
    创建新的评测任务
    """
    final_config_ids = []
    
    # ==========================================
    # 🌟 核心修复：强制预加载 configs，防止懒加载失效
    # ==========================================
    if task_in.scheme_id:
        # 使用 select + selectinload 替代简单的 session.get
        # 这能确保 scheme.configs 100% 被加载出来
        statement = (
            select(EvaluationScheme)
            .where(EvaluationScheme.id == task_in.scheme_id)
            .options(selectinload(EvaluationScheme.configs))
        )
        scheme = session.exec(statement).first()
        
        if not scheme:
            raise HTTPException(status_code=404, detail="Selected Scheme not found")
        
        # 提取 ID
        final_config_ids = [c.id for c in scheme.configs]
        
        # 🐛 调试打印：看看后端到底读到了什么
        print(f"🔍 [CreateTask] Scheme={scheme.name}, ConfigIDs={final_config_ids}")

    else:
        final_config_ids = task_in.config_ids

    # 序列化存储
    json_list = json.dumps(final_config_ids)
    
    # 2. 创建任务对象
    db_task = EvaluationTask(
        model_id=task_in.model_id,
        scheme_id=task_in.scheme_id,
        status="pending",
        progress=0,
        datasets_list=json_list # 存入数据库
    )
    
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    
    # 3. 创建关联记录
    for cid in final_config_ids:
        link = TaskDatasetLink(task_id=db_task.id, dataset_config_id=cid)
        session.add(link)
    
    session.commit()
    
    # 4. 触发评测
    run_evaluation_task.delay(db_task.id)
    
    return db_task

@router.get("/", response_model=List[TaskRead])
def read_tasks(
    offset: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session)
):
    """
    获取任务列表 (包含方案名称)
    """
    statement = (
        select(EvaluationTask, EvaluationScheme.name)
        .outerjoin(EvaluationScheme, EvaluationTask.scheme_id == EvaluationScheme.id)
        .offset(offset)
        .limit(limit)
        .order_by(EvaluationTask.id.desc())
    )
    
    results = session.exec(statement).all()
    
    tasks_with_details = []
    for task, s_name in results:
        task_dict = task.dict()
        task_dict["scheme_name"] = s_name 
        tasks_with_details.append(task_dict)
        
    return tasks_with_details

@router.get("/{task_id}", response_model=TaskRead)
def read_task(task_id: int, session: Session = Depends(get_session)):
    task = session.get(EvaluationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.delete("/{task_id}")
def delete_task(
    task_id: int, 
    session: Session = Depends(get_session)
):
    task_service = TaskService(session)
    success = task_service.delete_task(task_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
        
    return {"status": "success", "message": f"Task {task_id} has been deleted"}