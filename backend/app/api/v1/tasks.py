import json
import os
import time
import glob
import asyncio
from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse  # 🌟 新增引入
from sqlmodel import Session, select, func
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.models.task import EvaluationTask
from app.models.links import TaskDatasetLink
from app.models.scheme import EvaluationScheme 
from app.models.dataset import DatasetConfig
from app.schemas.task_schema import TaskCreate, TaskRead, TaskPagination, TaskCompareRequest, TaskCompareResponse
from app.worker.celery_app import run_evaluation_task
from app.services.task_service import TaskService

from app.deps import get_current_active_user, get_current_admin
from app.models.user import User

router = APIRouter()

@router.post("/", response_model=TaskRead)
def create_task(
    task_in: TaskCreate, 
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user) # <--- 仅需登录
):
    final_config_ids = []
    
    if task_in.scheme_id:
        statement = (
            select(EvaluationScheme)
            .where(EvaluationScheme.id == task_in.scheme_id)
            .options(selectinload(EvaluationScheme.configs))
        )
        scheme = session.exec(statement).first()
        
        if not scheme:
            raise HTTPException(status_code=404, detail="Selected Scheme not found")
        
        final_config_ids = [c.id for c in scheme.configs]
    else:
        final_config_ids = task_in.config_ids

    json_list = json.dumps(final_config_ids)
    
    db_task = EvaluationTask(
        model_id=task_in.model_id,
        scheme_id=task_in.scheme_id,
        status="pending",
        progress=0,
        datasets_list=json_list
    )
    
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    
    for cid in final_config_ids:
        link = TaskDatasetLink(task_id=db_task.id, dataset_config_id=cid)
        session.add(link)
    
    session.commit()
    
    run_evaluation_task.delay(db_task.id)
    
    return db_task

@router.get("/", response_model=TaskPagination) 
def read_tasks(
    page: int = 1,        
    page_size: int = 10,  
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user) # <--- 仅需登录
):
    offset = (page - 1) * page_size
    count_statement = select(func.count()).select_from(EvaluationTask)
    total = session.exec(count_statement).one()

    statement = (
        select(EvaluationTask, EvaluationScheme.name)
        .outerjoin(EvaluationScheme, EvaluationTask.scheme_id == EvaluationScheme.id)
        .offset(offset)
        .limit(page_size)
        .order_by(EvaluationTask.id.desc())
    )
    
    results = session.exec(statement).all()
    
    tasks_with_details = []
    for task, s_name in results:
        task_dict = task.dict()
        task_dict["scheme_name"] = s_name 
        tasks_with_details.append(task_dict)
        
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": tasks_with_details
    }

@router.get("/{task_id}", response_model=TaskRead)
def read_task(
    task_id: int, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    task = session.get(EvaluationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

# ==========================================
# 🌟 新增：实时日志流接口
# ==========================================
@router.get("/{task_id}/log")
async def get_task_log(
    task_id: int, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    # 1. 确认任务存在
    task = session.get(EvaluationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    workspace = os.path.join(os.getcwd(), "workspace", "tasks", f"task_{task_id}")
    log_path = os.path.join(workspace, "output.log")
    
    async def log_generator():
        retries = 0
        while not os.path.exists(log_path):
            if retries > 20: 
                yield "Waiting for log file creation timeout...\n"
                return
            yield f"Waiting for logs... (task status: {task.status})\n"
            await asyncio.sleep(0.5)
            retries += 1
            
        with open(log_path, "r", encoding="utf-8", errors='replace') as f:
            yield f.read()
            while True:
                line = f.readline()
                if line:
                    yield line
                else:
                    session.refresh(task)
                    if task.status in ["success", "failed"]:
                        break
                    await asyncio.sleep(0.5)

    return StreamingResponse(log_generator(), media_type="text/plain")


# ... (delete_task 保持不变) ...
@router.delete("/{task_id}")
def delete_task(
    task_id: int, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_admin) # <--- 强制管理员权限
):
    task_service = TaskService(session)
    success = task_service.delete_task(task_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
        
    return {"status": "success", "message": f"Task {task_id} has been deleted"}

@router.post("/compare", response_model=TaskCompareResponse)
def compare_tasks_api(
    req: TaskCompareRequest, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    task_service = TaskService(session)
    return task_service.compare_tasks(req.task_ids)

@router.get("/{task_id}/download")
def download_task_report(
    task_id: int, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    task = session.get(EvaluationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    workspace = os.path.join(os.getcwd(), "workspace", "tasks", f"task_{task_id}")
    pattern = os.path.join(workspace, "*", "summary", "summary_*.csv")
    csv_files = glob.glob(pattern)
    
    if not csv_files:
        raise HTTPException(status_code=404, detail="Report file not found.")
        
    latest_csv = max(csv_files, key=os.path.getmtime)
    filename = os.path.basename(latest_csv)
    
    return FileResponse(path=latest_csv, filename=filename, media_type='text/csv')