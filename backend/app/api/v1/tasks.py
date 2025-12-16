import json
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from typing import List

from app.core.database import get_session
from app.models.task import EvaluationTask
from app.models.llm_model import LLMModel
from app.models.dataset import Dataset
from app.schemas.task_schema import TaskCreate, TaskRead

# 导入我们的 Celery 任务
from app.worker.celery_app import run_evaluation_task

router = APIRouter()

# ==========================================
# 接口 1: 创建评测任务 (提交体检单)
# ==========================================
@router.post("/", response_model=TaskRead)
def create_task(task_in: TaskCreate, session: Session = Depends(get_session)):
    # 1. 校验模型是否存在
    model = session.get(LLMModel, task_in.model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # 2. 校验数据集是否存在，并获取它们的名字
    # 这是一个稍微复杂的 SQL IN 查询
    statement = select(Dataset).where(Dataset.id.in_(task_in.dataset_ids))
    datasets = session.exec(statement).all()
    
    if len(datasets) != len(task_in.dataset_ids):
        raise HTTPException(status_code=400, detail="Some datasets not found")
    
    # 3. 把数据集名字转成 JSON 字符串存入数据库
    # 例如: ["GSM8K", "My-QA"] -> '["GSM8K", "My-QA"]'
    dataset_names = [d.name for d in datasets]
    datasets_json = json.dumps(dataset_names)
    
    # 4. 创建数据库记录 (状态设为 pending)
    db_task = EvaluationTask(
        model_id=task_in.model_id,
        datasets_list=datasets_json,
        status="pending",
        progress=0
    )
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    
    # ==========================================
    # 🔥 关键一步：触发 Celery 异步任务
    # ==========================================
    # delay() 方法会立刻返回，不会阻塞 API
    run_evaluation_task.delay(db_task.id)
    
    return db_task

# ==========================================
# 接口 2: 获取任务列表
# ==========================================
@router.get("/", response_model=List[TaskRead])
def read_tasks(session: Session = Depends(get_session)):
    tasks = session.exec(select(EvaluationTask)).all()
    return tasks

# ==========================================
# 接口 3: 获取单个任务详情
# ==========================================
@router.get("/{task_id}", response_model=TaskRead)
def read_task(task_id: int, session: Session = Depends(get_session)):
    task = session.get(EvaluationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task