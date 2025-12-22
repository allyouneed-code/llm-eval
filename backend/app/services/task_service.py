import json
import time
import random
from fastapi import HTTPException
from sqlmodel import Session, select
from typing import List, Optional

from app.models.task import EvaluationTask
from app.models.llm_model import LLMModel
from app.models.dataset import DatasetConfig
from app.models.links import TaskDatasetLink
from app.models.result import EvaluationResult
from app.schemas.task_schema import TaskCreate

class TaskService:
    def __init__(self, session: Session):
        self.session = session

    def create_task(self, task_in: TaskCreate) -> EvaluationTask:
        """
        创建评测任务：验证数据、写入任务表、写入关联快照
        """
        # 1. 检查模型是否存在
        model = self.session.get(LLMModel, task_in.model_id)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # 2. 检查配置是否存在
        statement = select(DatasetConfig).where(DatasetConfig.id.in_(task_in.config_ids))
        configs = self.session.exec(statement).all()
        
        if len(configs) != len(task_in.config_ids):
            raise HTTPException(status_code=400, detail="部分评测配置不存在")
        
        # 3. 创建任务 (保留 datasets_list 字符串以兼容旧前端)
        datasets_json = json.dumps(task_in.config_ids)
        
        db_task = EvaluationTask(
            model_id=task_in.model_id,
            datasets_list=datasets_json,
            status="pending",
            progress=0
        )
        self.session.add(db_task)
        self.session.commit()
        self.session.refresh(db_task)
        
        # 4. [优化] 写入 TaskDatasetLink 中间表 (带快照)
        for config in configs:
            snapshot_json = json.dumps(config.model_dump(mode='json'), default=str)
            link = TaskDatasetLink(
                task_id=db_task.id,
                dataset_config_id=config.id,
                config_snapshot=snapshot_json
            )
            self.session.add(link)
        
        self.session.commit()
        return db_task

    def get_task(self, task_id: int) -> Optional[EvaluationTask]:
        return self.session.get(EvaluationTask, task_id)

    def get_all_tasks(self) -> List[EvaluationTask]:
        return self.session.exec(select(EvaluationTask)).all()

    def run_evaluation_logic(self, task_id: int):
        """
        执行评测的具体逻辑 (供 Worker 调用)
        """
        # 0. 获取任务
        task = self.get_task(task_id)
        if not task:
            print(f"❌ [Service] Task {task_id} not found")
            return "Task Not Found"
            
        # 解析配置 IDs (这里使用 datasets_list 兼容字段，也可以改用 TaskDatasetLink 查询)
        config_ids = json.loads(task.datasets_list)
        configs = self.session.exec(
            select(DatasetConfig).where(DatasetConfig.id.in_(config_ids))
        ).all()
        
        # 预处理：构建待评测列表
        eval_queue = []
        for cfg in configs:
            dataset_name = cfg.meta.name if cfg.meta else f"Dataset-{cfg.id}"
            eval_queue.append({
                "config_id": cfg.id,
                "name": dataset_name,
                "mode": cfg.mode,
                "capability": cfg.meta.category if cfg.meta else "Unknown",
                "metric": cfg.display_metric
            })

        # 1. 更新状态：Running
        task.progress = 5
        task.status = "running"
        self.session.add(task)
        self.session.commit()
        
        # 2. 模拟加载模型
        time.sleep(1)
        task.progress = 10
        self.session.add(task)
        self.session.commit()
        
        # 3. 逐个评测数据集
        total_steps = len(eval_queue)
        table_data = [] 
        
        for i, item in enumerate(eval_queue):
            # 模拟推理耗时
            time.sleep(1.5) 
            
            # 模拟分数生成
            score = round(random.uniform(50, 95), 1)
            
            # === 写入 EvaluationResult ===
            db_result = EvaluationResult(
                task_id=task_id,
                dataset_config_id=item["config_id"],
                dataset_name=item["name"],
                metric_name=item["metric"],
                score=score,
                details={"full_log": "mock_log_path.txt"} 
            )
            self.session.add(db_result)

            # 维护前端 Table 数据
            table_data.append({
                "dataset": f"{item['name']} ({item['mode']})",
                "capability": item["capability"],
                "metric": item["metric"],
                "score": score
            })
            
            # 更新进度 (每处理一个数据集更新一次，避免频繁 Commit)
            current_progress = 10 + int(((i + 1) / total_steps) * 80)
            task.progress = current_progress
            self.session.add(task)
            self.session.commit()

        # 4. 构造最终摘要并完成
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
        task.finished_at = time.strftime('%Y-%m-%d %H:%M:%S') # 简单记录时间
        
        self.session.add(task)
        self.session.commit()
        
        print(f"✅ [Service] 任务 {task_id} 逻辑执行完毕")
        return f"Task {task_id} Success"