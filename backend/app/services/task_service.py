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
# 🆕 引入评测方案模型
from app.models.scheme import EvaluationScheme
from app.schemas.task_schema import TaskCreate

class TaskService:
    def __init__(self, session: Session):
        self.session = session

    def create_task(self, task_in: TaskCreate) -> EvaluationTask:
        """
        创建评测任务：
        支持两种模式：
        1. 基于 Scheme (方案): 从 task_in.scheme_id 读取配置
        2. 基于 Custom (自定义): 从 task_in.config_ids 读取配置
        """
        # 1. 检查模型是否存在
        model = self.session.get(LLMModel, task_in.model_id)
        if not model:
            raise HTTPException(status_code=404, detail="所选模型不存在 (Model not found)")
        
        # ==========================================
        # 🆕 核心逻辑变更：处理方案引用
        # ==========================================
        target_config_ids = task_in.config_ids or []

        if task_in.scheme_id:
            # A. 如果指定了方案 ID，则从方案中提取数据集
            scheme = self.session.get(EvaluationScheme, task_in.scheme_id)
            if not scheme:
                raise HTTPException(status_code=404, detail="所选评测方案不存在")
            
            # 利用 SQLModel 的 relationship 获取当前关联的所有有效配置
            # 这规避了"数据集被删但ID仍遗留在JSON字符串中"的风险
            scheme_configs = scheme.configs
            
            if not scheme_configs:
                raise HTTPException(status_code=400, detail="该评测方案未包含任何有效的数据集配置")
            
            # 覆盖 target_config_ids
            target_config_ids = [c.id for c in scheme_configs]
        
        # 2. 验证配置 ID 列表 (无论是手动传的还是从方案查出来的)
        if not target_config_ids:
            raise HTTPException(status_code=400, detail="未选择任何评测数据集")

        # 从数据库查询这些 Config 对象
        statement = select(DatasetConfig).where(DatasetConfig.id.in_(target_config_ids))
        configs = self.session.exec(statement).all()
        
        # 再次校验数量（防止手动模式下传了不存在的ID）
        # 注意：如果是从 scheme.configs 拿的，这里通常是一致的；如果是前端手动传 ID，这里能拦截错误
        if len(configs) != len(set(target_config_ids)):
             raise HTTPException(status_code=400, detail="部分评测配置不存在或ID重复")
        
        # 3. 创建任务 
        # (datasets_list 存为 JSON 字符串以保持对旧逻辑/Worker的兼容性)
        datasets_json = json.dumps([c.id for c in configs])
        
        db_task = EvaluationTask(
            model_id=task_in.model_id,
            datasets_list=datasets_json,
            # 🆕 记录方案 ID (如果不是基于方案创建，则为 None)
            scheme_id=task_in.scheme_id,
            status="pending",
            progress=0
        )
        self.session.add(db_task)
        self.session.commit()
        self.session.refresh(db_task)
        
        # 4. 写入 TaskDatasetLink 中间表 (带配置快照)
        # 这一步非常重要，它固化了任务执行时的配置参数
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
            
        # 解析配置 IDs (兼容旧字段 datasets_list)
        # 未来优化建议：改用 TaskDatasetLink 读取，以使用 snapshot 确保完全复现
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
        # 这里的雷达图数据目前是 Mock 的，实际应根据 table_data 按 capability 聚合计算
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
        task.finished_at = time.strftime('%Y-%m-%d %H:%M:%S') 
        
        self.session.add(task)
        self.session.commit()
        
        print(f"✅ [Service] 任务 {task_id} 逻辑执行完毕")
        return f"Task {task_id} Success"