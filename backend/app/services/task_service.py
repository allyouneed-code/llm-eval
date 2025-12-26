import json
import os
import shutil
from datetime import datetime
from fastapi import HTTPException
from sqlmodel import Session, select
from typing import List, Optional, Dict, Any

from app.models.task import EvaluationTask
from app.models.llm_model import LLMModel
from app.models.dataset import DatasetConfig
from app.models.links import TaskDatasetLink
from app.models.result import EvaluationResult
from app.models.scheme import EvaluationScheme
from app.schemas.task_schema import TaskCreate
# 🆕 引入 Runner
from app.services.opencompass_runner import OpenCompassRunner

class TaskService:
    def __init__(self, session: Session):
        self.session = session

    # create_task, delete_task, get_task 等方法保持不变...
    # (此处省略未修改的方法，请保留原文件中的这些代码)
    
    def create_task(self, task_in: TaskCreate) -> EvaluationTask:
        # ... (保持原有的 create_task 逻辑不变) ...
        # 请确保把原文件中的 create_task 代码完整保留在这里
        model = self.session.get(LLMModel, task_in.model_id)
        if not model:
            raise HTTPException(status_code=404, detail="所选模型不存在")
        
        target_config_ids = task_in.config_ids or []

        if task_in.scheme_id:
            scheme = self.session.get(EvaluationScheme, task_in.scheme_id)
            if not scheme:
                raise HTTPException(status_code=404, detail="所选评测方案不存在")
            scheme_configs = scheme.configs
            if not scheme_configs:
                raise HTTPException(status_code=400, detail="该评测方案未包含任何有效的数据集配置")
            target_config_ids = [c.id for c in scheme_configs]
        
        if not target_config_ids:
            raise HTTPException(status_code=400, detail="未选择任何评测数据集")

        statement = select(DatasetConfig).where(DatasetConfig.id.in_(target_config_ids))
        configs = self.session.exec(statement).all()
        
        if len(configs) != len(set(target_config_ids)):
             raise HTTPException(status_code=400, detail="部分评测配置不存在或ID重复")
        
        datasets_json = json.dumps([c.id for c in configs])
        
        db_task = EvaluationTask(
            model_id=task_in.model_id,
            datasets_list=datasets_json,
            scheme_id=task_in.scheme_id,
            status="pending",
            progress=0
        )
        self.session.add(db_task)
        self.session.commit()
        self.session.refresh(db_task)
        
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

    def delete_task(self, task_id: int) -> bool:
        task = self.get_task(task_id)
        if not task:
            return False
        results = self.session.exec(select(EvaluationResult).where(EvaluationResult.task_id == task_id)).all()
        for r in results:
            self.session.delete(r)
        links = self.session.exec(select(TaskDatasetLink).where(TaskDatasetLink.task_id == task_id)).all()
        for l in links:
            self.session.delete(l)  
        self.session.delete(task)
        self.session.commit()
        return True

    def get_task(self, task_id: int) -> Optional[EvaluationTask]:
        return self.session.get(EvaluationTask, task_id)

    def get_all_tasks(self) -> List[EvaluationTask]:
        return self.session.exec(select(EvaluationTask)).all()

    # ====================================================
    # 🌟 核心修改：真实的评测逻辑
    # ====================================================
    def run_evaluation_logic(self, task_id: int):
        """
        执行评测任务 (Real Implementation)
        """
        # 1. 获取任务与上下文
        task = self.get_task(task_id)
        if not task:
            return "Task Not Found"

        # 更新状态为 Running
        task.status = "running"
        task.progress = 1
        task.error_msg = None
        self.session.add(task)
        self.session.commit()

        try:
            # 2. 准备数据对象
            model = self.session.get(LLMModel, task.model_id)
            if not model:
                raise ValueError(f"Model {task.model_id} not found")

            # 解析数据集配置
            config_ids = []
            try:
                config_ids = json.loads(task.datasets_list)
            except:
                pass
            
            configs = self.session.exec(
                select(DatasetConfig).where(DatasetConfig.id.in_(config_ids))
            ).all()

            if not configs:
                raise ValueError("No datasets found for this task")

            # 3. 初始化 Runner
            # 为每个任务创建一个独立的工作目录，避免冲突
            # 路径示例: workspace/tasks/task_123
            task_workspace = os.path.join(os.getcwd(), "workspace", "tasks", f"task_{task_id}")
            runner = OpenCompassRunner(workspace=task_workspace)
            
            # 更新进度
            task.progress = 5
            self.session.add(task)
            self.session.commit()

            # 4. 生成配置文件
            print(f"📄 [Task {task_id}] Generating config...")
            config_path = runner.generate_config(task_id, model, configs)
            
            task.progress = 10
            self.session.add(task)
            self.session.commit()

            # 5. 执行评测 (这是一个耗时阻塞操作)
            print(f"🚀 [Task {task_id}] Running OpenCompass...")
            # TODO: 未来可以传入 callback 函数来实时更新 10%~90% 的进度
            runner.run(config_path)
            
            # 运行完成后，进度跳到 90%
            task.progress = 90
            self.session.add(task)
            self.session.commit()

            # 6. 解析结果并入库
            print(f"📊 [Task {task_id}] Parsing results...")
            raw_results = runner.parse_results()
            
            table_data = [] # 用于前端展示的摘要表

            # 建立一个 config_name -> config 对象的映射，方便查找 meta 信息
            # 假设 dataset 的 abbr (OpenCompass输出的dataset列) 与我们的 config_name 或 name 对应
            # 这里做一个模糊匹配或简化处理：尝试匹配 config_name 或 meta.name
            
            for res in raw_results:
                # 寻找对应的 config 对象
                matched_config = None
                dataset_abbr = res['dataset']
                
                for cfg in configs:
                    # OpenCompass 的 abbr 通常由我们生成的配置文件中的 abbr 字段决定
                    # 在 config_factory 或 runner 中我们可能用 name 作为 abbr
                    # 这里做一个简单的包含匹配
                    if cfg.meta.name in dataset_abbr or dataset_abbr in cfg.meta.name:
                        matched_config = cfg
                        break
                
                # 如果没匹配到，选第一个（兜底），或者跳过
                target_config_id = matched_config.id if matched_config else configs[0].id
                dataset_name_display = matched_config.meta.name if matched_config else dataset_abbr
                dataset_category = matched_config.meta.category if matched_config else "Unknown"
                
                # 写入数据库 EvaluationResult
                db_result = EvaluationResult(
                    task_id=task_id,
                    dataset_config_id=target_config_id,
                    dataset_name=dataset_name_display,
                    metric_name=res['metric'],
                    score=res['score'],
                    details=res['raw_data']
                )
                self.session.add(db_result)
                
                # 收集前端展示数据
                table_data.append({
                    "dataset": dataset_name_display,
                    "capability": dataset_category,
                    "metric": res['metric'],
                    "score": res['score']
                })

            # 7. 生成最终的任务摘要 (Radar + Table)
            final_summary = self._generate_summary(table_data)
            
            task.result_summary = json.dumps(final_summary)
            task.status = "success"
            task.progress = 100
            task.finished_at = datetime.now()
            
            print(f"✅ [Task {task_id}] Finished successfully.")

        except Exception as e:
            import traceback
            traceback.print_exc()
            task.status = "failed"
            task.error_msg = str(e)
            print(f"❌ [Task {task_id}] Failed: {e}")
        
        finally:
            self.session.add(task)
            self.session.commit()
            return f"Task {task_id} processed"

    def _generate_summary(self, table_data: List[Dict]) -> Dict:
        """
        根据结果生成雷达图和表格数据
        """
        if not table_data:
            return {"radar": [], "table": []}

        # 1. 计算能力维度的平均分 (Radar Data)
        capability_stats = {}
        for item in table_data:
            cat = item['capability']
            if cat not in capability_stats:
                capability_stats[cat] = []
            capability_stats[cat].append(item['score'])
        
        radar_data = []
        for cat, scores in capability_stats.items():
            avg_score = sum(scores) / len(scores) if scores else 0
            radar_data.append({
                "name": cat,
                "max": 100,
                "score": round(avg_score, 1)
            })
            
        return {
            "radar": radar_data,
            "table": table_data
        }