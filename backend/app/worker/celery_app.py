import json
import time
from celery import Celery
from sqlmodel import Session, select
from app.core.database import engine
from app.models.task import EvaluationTask
# 引入新模型以获取详细信息
from app.models.dataset import DatasetConfig, DatasetMeta

celery_app = Celery(
    "worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
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
    
    # 0. 获取任务信息和配置详情
    with Session(engine) as session:
        task = session.get(EvaluationTask, task_id)
        if not task:
            return "Task Not Found"
            
        config_ids = json.loads(task.datasets_list)
        # 查询详细配置信息用于生成报告
        configs = session.exec(
            select(DatasetConfig).where(DatasetConfig.id.in_(config_ids))
        ).all()
        
        # 预先准备好报告用的名称列表
        # 格式示例: "GSM8K (gen)", "C-Eval (ppl)"
        report_items = []
        for cfg in configs:
            # 注意：这里需要由于 lazy loading，可能需要手动加载 meta，或者确保 session 没关
            # 如果配置了 Relationship，可以直接访问 cfg.meta.name
            dataset_name = cfg.meta.name if cfg.meta else "Unknown"
            report_items.append({
                "name": f"{dataset_name} ({cfg.mode})",
                "capability": cfg.meta.category, # 假设 category 是能力维度
                "metric": cfg.display_metric
            })

    # 1. 初始化
    _update_task(task_id, progress=5, status="running")
    time.sleep(1)
    
    # 2. 模拟加载模型
    _update_task(task_id, progress=20)
    time.sleep(2)
    
    # 3. 模拟评测数据集
    total_steps = len(report_items) # 根据实际选择的数据集数量
    if total_steps == 0: total_steps = 1
    
    table_data = []
    
    for i, item in enumerate(report_items):
        # 更新进度
        current_progress = 20 + int(((i + 1) / total_steps) * 60)
        _update_task(task_id, progress=current_progress)
        
        time.sleep(1.5) # 模拟推理
        
        # 生成该数据集的模拟分数
        import random
        score = round(random.uniform(50, 95), 1)
        
        table_data.append({
            "dataset": item["name"],
            "capability": item["capability"],
            "metric": item["metric"],
            "score": score
        })

    # 4. 构造最终结果 
    final_result = {
        "radar": [
            # 这里简化处理，实际应该根据 table_data 聚合 capability 分数
            {"name": "Knowledge", "max": 100, "score": 85.5},
            {"name": "Reasoning", "max": 100, "score": 62.1},
            {"name": "Coding", "max": 100, "score": 78.4},
        ],
        "table": table_data, # 使用动态生成的数据
        "files": [
            {"name": "prediction_results.jsonl", "size": "12MB", "type": "json"}
        ]
    }
    
    # 5. 完成
    _update_task(task_id, progress=100, status="success", result=final_result)
    print(f"✅ [Worker] 任务 {task_id} 完成")
    return f"Task {task_id} Success"