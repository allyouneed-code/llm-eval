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
    
    def create_task(self, task_in: TaskCreate) -> EvaluationTask:
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
    # 🌟 核心逻辑
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

            # 5. 执行评测
            print(f"🚀 [Task {task_id}] Running OpenCompass...")
            runner.run(config_path)
            
            # 运行完成后，进度跳到 90%
            task.progress = 90
            self.session.add(task)
            self.session.commit()

            # 6. 解析结果并入库
            print(f"📊 [Task {task_id}] Parsing results...")
            raw_results = runner.parse_results()
            
            table_data = [] # 用于前端展示的摘要表
            
            for res in raw_results:
                # 寻找对应的 config 对象
                matched_config = None
                dataset_abbr = res['dataset']
                
                for cfg in configs:
                    # 模糊匹配 config name
                    if cfg.meta.name in dataset_abbr or dataset_abbr in cfg.meta.name:
                        matched_config = cfg
                        break
                
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
        【改进】统一量纲 (0-1 -> 0-100) 并处理特殊指标
        """
        if not table_data:
            return {"radar": [], "table": []}

        capability_stats = {}
        
        for item in table_data:
            cat = item['capability']
            try:
                raw_score = float(item['score'])
            except (ValueError, TypeError):
                raw_score = 0.0
                
            metric = str(item['metric']).lower()
            
            # --- 归一化逻辑 ---
            norm_score = raw_score
            
            # 1. 识别负向指标 (越小越好)
            # 例如: ppl (Perplexity), loss, bpb (Bits Per Byte)
            # 这类指标不适合直接参与 0-100 的雷达图平均，暂时打标跳过或保留原值
            # (如果同一能力维度下混合了 Acc 和 PPL，直接平均会很奇怪，所以这里策略是尽量只取正向指标平均)
            is_negative_metric = any(x in metric for x in ['ppl', 'bpb', 'loss'])
            
            if is_negative_metric:
                # 负向指标暂时不参与雷达图的“能力得分”计算
                # 除非你希望显示一个很低的分数（因为 PPL 越低越好，但在雷达图上低分会被认为是弱）
                continue 
            else:
                # 2. 识别 0-1 分数 (Acc, BLEU, ROUGE 等)
                # 启发式规则：如果分数在 0.0 到 1.0 之间，大概率是小数制，转换为百分制
                if 0.0 <= raw_score <= 1.0:
                    norm_score = raw_score * 100.0
            
            if cat not in capability_stats:
                capability_stats[cat] = []
            
            capability_stats[cat].append(norm_score)
        
        radar_data = []
        for cat, scores in capability_stats.items():
            if not scores:
                # 如果该维度下只有 PPL 指标，可能 scores 为空
                # 这种情况下，给一个默认显示（比如 0 或者不显示）
                continue

            # 计算平均分
            avg_score = sum(scores) / len(scores)
            
            # 限制最大显示为 100 (防止部分异常指标溢出)
            display_score = min(avg_score, 100.0)
            
            radar_data.append({
                "name": cat,
                "max": 100,
                "score": round(display_score, 1)
            })
            
        return {
            "radar": radar_data,
            "table": table_data
        }