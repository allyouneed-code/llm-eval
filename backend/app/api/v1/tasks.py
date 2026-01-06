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

router = APIRouter()

# ... (create_task 保持不变) ...
@router.post("/", response_model=TaskRead)
def create_task(
    task_in: TaskCreate, 
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
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

# ... (read_tasks 保持不变) ...
@router.get("/", response_model=TaskPagination) 
def read_tasks(
    page: int = 1,        
    page_size: int = 10,  
    session: Session = Depends(get_session)
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

# ... (read_task 保持不变) ...
@router.get("/{task_id}", response_model=TaskRead)
def read_task(task_id: int, session: Session = Depends(get_session)):
    task = session.get(EvaluationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

# ==========================================
# 🌟 新增：实时日志流接口
# ==========================================
@router.get("/{task_id}/log")
async def get_task_log(task_id: int, session: Session = Depends(get_session)):
    """
    流式返回任务运行日志 (Server-Sent Events 风格)
    """
    # 1. 确认任务存在
    task = session.get(EvaluationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    # 2. 定位日志文件
    # 路径规则需与 TaskService 保持一致
    workspace = os.path.join(os.getcwd(), "workspace", "tasks", f"task_{task_id}")
    log_path = os.path.join(workspace, "output.log")
    
    async def log_generator():
        """
        异步生成器：像 tail -f 一样读取文件
        """
        # A. 等待日志文件生成 (最多等 10秒)
        retries = 0
        while not os.path.exists(log_path):
            if retries > 20: # 10s
                yield "Waiting for log file creation timeout...\n"
                return
            yield f"Waiting for logs... (task status: {task.status})\n"
            await asyncio.sleep(0.5)
            retries += 1
            
        # B. 开始读取
        with open(log_path, "r", encoding="utf-8", errors='replace') as f:
            # 先读取已有内容
            yield f.read()
            
            # 持续监听新内容
            while True:
                line = f.readline()
                if line:
                    yield line
                else:
                    # 如果读不到新行，检查任务是否已结束
                    # 注意：为了性能，这里不频繁查库，而是依赖文件不再写入+一定超时，或者简单点一直挂着直到前端断开
                    # 为了更严谨，我们可以重新查询一次任务状态
                    session.refresh(task)
                    if task.status in ["success", "failed"]:
                        # 任务结束，且文件已读完 -> 退出流
                        break
                    
                    # 任务未结束，等待新日志写入
                    await asyncio.sleep(0.5)

    return StreamingResponse(log_generator(), media_type="text/plain")


# ... (delete_task 保持不变) ...
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

@router.post("/compare", response_model=TaskCompareResponse)
def compare_tasks_api(
    req: TaskCompareRequest, 
    session: Session = Depends(get_session)
):
    """
    对比指定的多个任务 (Task IDs)
    """
    task_service = TaskService(session)
    return task_service.compare_tasks(req.task_ids)

@router.get("/{task_id}/download")
def download_task_report(task_id: int, session: Session = Depends(get_session)):
    """
    下载评测生成的 CSV 汇总报告
    """
    # 1. 确认任务存在
    task = session.get(EvaluationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 2. 动态查找 CSV 文件
    # 目录结构: workspace/tasks/task_{id}/{timestamp}/summary/summary_{timestamp}.csv
    workspace = os.path.join(os.getcwd(), "workspace", "tasks", f"task_{task_id}")
    
    # 使用 glob 匹配 summary 目录下的 csv（跨过中间的时间戳目录）
    pattern = os.path.join(workspace, "*", "summary", "summary_*.csv")
    csv_files = glob.glob(pattern)
    
    if not csv_files:
        raise HTTPException(status_code=404, detail="Report file not found. The task might have failed or results are missing.")
        
    # 3. 获取最新的文件 (以防有多次运行残留)
    latest_csv = max(csv_files, key=os.path.getmtime)
    filename = os.path.basename(latest_csv)
    
    # 4. 返回文件
    return FileResponse(
        path=latest_csv, 
        filename=filename, 
        media_type='text/csv'
    )