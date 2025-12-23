import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select

from app.core.database import get_session
from app.models.task import EvaluationTask
from app.models.links import TaskDatasetLink
from app.models.scheme import EvaluationScheme  # 👈 必需：用于连表查询
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
    # 1. 序列化配置列表
    # (注意：如果 task_in.config_ids 是空，理论上应从 scheme_id 自动填充，
    # 但目前逻辑是前端已处理好 config_ids 传进来，这里直接存即可)
    json_list = json.dumps(task_in.config_ids)
    
    # 2. 创建任务对象
    db_task = EvaluationTask(
        model_id=task_in.model_id,
        scheme_id=task_in.scheme_id,  # 👈 关键：保存方案 ID
        status="pending",
        progress=0,
        datasets_list=json_list
    )
    
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    
    # 3. 创建关联表记录 (TaskDatasetLink)
    # 这用于后续统计某次任务包含哪些数据集
    for cid in task_in.config_ids:
        link = TaskDatasetLink(task_id=db_task.id, dataset_config_id=cid)
        session.add(link)
    
    session.commit()
    
    # 4. 异步触发 Celery 任务
    # 使用 Celery 的 delay 方法将任务推送到消息队列
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
    # 🌟 核心优化：连表查询 (Outer Join)
    # 同时查询 Task 表和 Scheme 表的 name 字段
    statement = (
        select(EvaluationTask, EvaluationScheme.name)
        .outerjoin(EvaluationScheme, EvaluationTask.scheme_id == EvaluationScheme.id)
        .offset(offset)
        .limit(limit)
        .order_by(EvaluationTask.id.desc())
    )
    
    results = session.exec(statement).all()
    
    # 组装返回数据
    tasks_with_details = []
    for task, s_name in results:
        # 将 SQLModel 对象转为字典，并手动注入 scheme_name
        # Pydantic (TaskRead) 会自动识别这个 extra 字段并输出
        task_dict = task.dict()
        task_dict["scheme_name"] = s_name 
        tasks_with_details.append(task_dict)
        
    return tasks_with_details

@router.get("/{task_id}", response_model=TaskRead)
def read_task(task_id: int, session: Session = Depends(get_session)):
    """
    获取单个任务详情
    """
    # 这里也可以加连表，但通常详情页已有 scheme_id，前端查 scheme 列表也行
    # 为了保持一致性，简单起见我们先只查 Task
    task = session.get(EvaluationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.delete("/{task_id}")
def delete_task(
    task_id: int, 
    session: Session = Depends(get_session)
):
    """
    删除任务 (级联删除结果和关联)
    """
    task_service = TaskService(session)
    success = task_service.delete_task(task_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
        
    return {"status": "success", "message": f"Task {task_id} has been deleted"}