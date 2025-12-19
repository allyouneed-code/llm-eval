import json
import time
import random #模拟用
import os
from celery import Celery
from sqlmodel import Session, select
from app.core.database import engine
from app.models.task import EvaluationTask
# 引入新模型以获取详细信息
from app.models.dataset import DatasetConfig
from app.models.result import EvaluationResult

REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)
celery_app.conf.broker_connection_retry_on_startup = True

def _update_task(task_id: int, progress: int = None, status: str = None, result: dict = None):
    with Session(engine) as session:
        task = session.get(EvaluationTask, task_id)
        if task:
            if progress is not None: task.progress = progress
            if status is not None: task.status = status
            if result is not None: task.result_summary = json.dumps(result)
            session.add(task)
            session.commit()

@celery_app.task
def run_evaluation_task(task_id: int):
    print(f"🚀 [Worker] 开始执行任务 {task_id}")
    
    # 打开 Session，注意这里我们扩大了 Session 的作用域，
    # 以便在循环中直接写入 EvaluationResult
    with Session(engine) as session:
        # 0. 获取任务信息
        task = session.get(EvaluationTask, task_id)
        if not task:
            return "Task Not Found"
            
        config_ids = json.loads(task.datasets_list)
        configs = session.exec(
            select(DatasetConfig).where(DatasetConfig.id.in_(config_ids))
        ).all()
        
        # 预处理：构建待评测列表，🌟 关键：保留 config.id 以便写入数据库
        eval_queue = []
        for cfg in configs:
            dataset_name = cfg.meta.name if cfg.meta else f"Dataset-{cfg.id}"
            eval_queue.append({
                "config_id": cfg.id,     # 🌟 必须传 ID 给后续写入使用
                "name": dataset_name,
                "mode": cfg.mode,
                "capability": cfg.meta.category,
                "metric": cfg.display_metric
            })

        # 1. 更新状态
        task.progress = 5
        task.status = "running"
        session.add(task)
        session.commit()
        
        # 2. 模拟加载模型
        time.sleep(1)
        task.progress = 10
        session.add(task)
        session.commit()
        
        # 3. 逐个评测数据集
        total_steps = len(eval_queue)
        table_data = [] # 用于最后生成前端大 JSON
        
        for i, item in enumerate(eval_queue):
            # 模拟推理耗时
            time.sleep(1.5) 
            
            # 模拟分数生成
            score = round(random.uniform(50, 95), 1)
            
            # === 🌟 核心修改 Start: 写入原子化结果表 ===
            db_result = EvaluationResult(
                task_id=task_id,
                dataset_config_id=item["config_id"], # 这里用到了上面保留的 ID
                dataset_name=item["name"],           # 冗余存个名字
                metric_name=item["metric"],
                score=score,
                details={"full_log": "mock_log_path.txt"} # 模拟存一些详情
            )
            session.add(db_result)
            # === 核心修改 End ===

            # 同时维护给前端看的 table_data (保持旧逻辑兼容)
            table_data.append({
                "dataset": f"{item['name']} ({item['mode']})",
                "capability": item["capability"],
                "metric": item["metric"],
                "score": score
            })
            
            # 更新进度
            current_progress = 10 + int(((i + 1) / total_steps) * 80)
            task.progress = current_progress
            session.add(task)
            session.commit()

        # 4. 构造最终摘要 (Radar + Table)
        # 这里依然生成 result_summary 是为了让前端 Dashboard 不用改代码也能跑
        final_summary = {
            "radar": [
                {"name": "Knowledge", "max": 100, "score": 85.5},
                {"name": "Reasoning", "max": 100, "score": 62.1},
            ],
            "table": table_data 
        }
        
        task.result_summary = json.dumps(final_summary)
        task.status = "success"
        task.progress = 100
        
        session.add(task)
        session.commit()
        
    print(f"✅ [Worker] 任务 {task_id} 完成，结果已存入 evaluation_results 表")
    return f"Task {task_id} Success"