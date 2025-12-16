# backend/app/worker/celery_app.py
import json
import time
import random
from celery import Celery
from sqlmodel import Session, select
from app.core.database import engine
from app.models.task import EvaluationTask

celery_app = Celery(
    "worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)
celery_app.conf.broker_connection_retry_on_startup = True

def _update_task(task_id: int, progress: int = None, status: str = None, result: dict = None, append_log: str = None):
    """辅助函数：更新数据库中的任务状态"""
    with Session(engine) as session:
        task = session.get(EvaluationTask, task_id)
        if task:
            if progress is not None: task.progress = progress
            if status is not None: task.status = status
            if result is not None: task.result_summary = json.dumps(result)
            
            # 简单的日志模拟：实际场景建议用 Redis List 存日志
            # 这里我们不存数据库文本字段以免太长，我们只在前端模拟日志滚动，或者
            # 在这里打印到控制台，前端暂时用假日志模拟“实时感”。
            
            session.add(task)
            session.commit()

@celery_app.task
def run_evaluation_task(task_id: int):
    print(f"🚀 [Worker] 开始执行任务 {task_id}")
    
    # 1. 初始化
    _update_task(task_id, progress=5, status="running")
    time.sleep(1)
    
    # 2. 模拟加载模型
    _update_task(task_id, progress=20)
    time.sleep(2)
    
    # 3. 模拟评测数据集 (循环进度)
    total_steps = 5
    for i in range(total_steps):
        current_progress = 20 + int((i / total_steps) * 60)
        _update_task(task_id, progress=current_progress)
        time.sleep(1.5) # 模拟推理耗时
        
    # 4. 构造最终结果 
    # Layer 1: Radar Data (能力维度)
    # Layer 2: Table Data (数据集明细)
    # Layer 3: Files (中间文件)
    
    final_result = {
        "radar": [
            {"name": "Knowledge", "max": 100, "score": 85.5},
            {"name": "Reasoning", "max": 100, "score": 62.1},
            {"name": "Coding", "max": 100, "score": 78.4},
            {"name": "Understanding", "max": 100, "score": 90.2},
            {"name": "Safety", "max": 100, "score": 95.0}
        ],
        "table": [
            {"dataset": "GSM8K", "capability": "Reasoning", "metric": "Accuracy", "score": 64.2},
            {"dataset": "MMLU", "capability": "Knowledge", "metric": "Accuracy", "score": 81.5},
            {"dataset": "HumanEval", "capability": "Coding", "metric": "Pass@1", "score": 70.2},
            {"dataset": "C-Eval", "capability": "Knowledge", "metric": "Accuracy", "score": 89.5},
            {"dataset": "TruthfulQA", "capability": "Safety", "metric": "MC1", "score": 95.0}
        ],
        "files": [
            {"name": "prediction_results.jsonl", "size": "12MB", "type": "json"},
            {"name": "eval_metrics.csv", "size": "4KB", "type": "csv"},
            {"name": "bad_cases_analysis.html", "size": "1.5MB", "type": "html"}
        ]
    }
    
    # 5. 完成
    _update_task(task_id, progress=100, status="success", result=final_result)
    print(f"✅ [Worker] 任务 {task_id} 完成")
    return f"Task {task_id} Success"