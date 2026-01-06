import json
import os
import shutil
import time
import glob
import pandas as pd
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
# 引入 Runners
from app.services.opencompass_runner import OpenCompassRunner
from app.services.multimodal_runner import MultimodalRunner

class TaskService:
    def __init__(self, session: Session):
        self.session = session

    # ====================================================
    # CRUD 操作 (保持不变)
    # ====================================================
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
    # 🌟 核心执行逻辑 (分流版)
    # ====================================================
    def run_evaluation_logic(self, task_id: int):
        """
        执行评测任务：支持文本与多模态混合执行
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

            # 3. 数据集分组 (文本 vs 多模态)
            text_configs = []
            multimodal_configs = []
            
            for cfg in configs:
                # 兼容旧数据，如果没有 modality 字段默认为 Text
                mod = getattr(cfg.meta, 'modality', 'Text')
                if not mod or mod == 'Text':
                    text_configs.append(cfg)
                else:
                    multimodal_configs.append(cfg)

            # 初始化 Workspace
            task_workspace = os.path.join(os.getcwd(), "workspace", "tasks", f"task_{task_id}")
            os.makedirs(task_workspace, exist_ok=True)
            
            start_time = time.time()
            
            # ========================================
            # 4. 执行文本评测 (OpenCompass)
            # ========================================
            if text_configs:
                print(f"📘 [Task {task_id}] Running Text Eval ({len(text_configs)} datasets)...")
                # 更新进度 10%
                task.progress = 10
                self.session.add(task)
                self.session.commit()
                
                text_runner = OpenCompassRunner(workspace=task_workspace)
                config_path = text_runner.generate_config(task_id, model, text_configs)
                text_runner.run(config_path)

            # ========================================
            # 5. 执行多模态评测 (MultimodalRunner)
            # ========================================
            if multimodal_configs:
                print(f"🌈 [Task {task_id}] Running Multimodal Eval ({len(multimodal_configs)} datasets)...")
                # 更新进度 50%
                task.progress = 50
                self.session.add(task)
                self.session.commit()
                
                mm_runner = MultimodalRunner(workspace=task_workspace)
                mm_runner.run(task_id, model, multimodal_configs)
            
            end_time = time.time()
            total_duration = end_time - start_time
            
            # 更新进度 90%
            task.progress = 90
            self.session.add(task)
            self.session.commit()

            # ========================================
            # 6. 统一解析结果 (Merge Results)
            # ========================================
            print(f"📊 [Task {task_id}] Parsing all results...")
            
            # 扫描 workspace 下所有的 summary csv
            # OpenCompass 和 MultimodalRunner 都会输出到 workspace/*/summary/summary_*.csv
            csv_pattern = os.path.join(task_workspace, "*", "summary", "summary_*.csv")
            csv_files = glob.glob(csv_pattern)
            
            if not csv_files:
                raise ValueError("No result CSVs found in workspace.")
            
            raw_results = []
            
            for csv_f in csv_files:
                print(f"   - Reading result: {csv_f}")
                try:
                    df = pd.read_csv(csv_f)
                    for _, row in df.iterrows():
                        row_dict = row.to_dict()
                        
                        dataset_abbr = row_dict.get("dataset", "Unknown")
                        metric = row_dict.get("metric", "score")
                        
                        # 智能提取分数
                        score = 0.0
                        for col in reversed(df.columns):
                            val = row_dict[col]
                            if isinstance(val, (int, float)) and col not in ['version', 'metric', 'mode']:
                                score = float(val)
                                break
                        
                        raw_results.append({
                            "dataset": dataset_abbr,
                            "metric": metric,
                            "score": score,
                            "raw_data": row_dict
                        })
                except Exception as parse_err:
                    print(f"⚠️ Warning: Failed to parse {csv_f}: {parse_err}")

            if not raw_results:
                raise ValueError("Parsed CSVs but found no valid data rows.")

            # 7. 入库与统计
            table_data = [] 
            
            for res in raw_results:
                # 寻找对应的 config 对象 (通过 dataset abbr 模糊匹配)
                matched_config = None
                dataset_abbr = res['dataset']
                
                # 优先完全匹配
                for cfg in configs:
                    if cfg.config_name == dataset_abbr:
                        matched_config = cfg
                        break
                
                # 其次模糊匹配
                if not matched_config:
                    for cfg in configs:
                        if cfg.meta.name in dataset_abbr or dataset_abbr in cfg.meta.name:
                            matched_config = cfg
                            break
                
                target_config_id = matched_config.id if matched_config else configs[0].id
                dataset_name_display = matched_config.meta.name if matched_config else dataset_abbr
                dataset_category = matched_config.meta.category if matched_config else "Unknown"
                
                # 写入数据库
                db_result = EvaluationResult(
                    task_id=task_id,
                    dataset_config_id=target_config_id,
                    dataset_name=dataset_name_display,
                    metric_name=res['metric'],
                    score=res['score'],
                    details=res['raw_data']
                )
                self.session.add(db_result)
                
                table_data.append({
                    "dataset": dataset_name_display,
                    "capability": dataset_category,
                    "metric": res['metric'],
                    "score": res['score']
                })

            # 8. 生成最终摘要
            final_summary = self._generate_summary(table_data)
            final_summary["time_stats"] = {
                "total_duration": round(total_duration, 2),
                "avg_per_dataset": round(total_duration / len(configs), 2) if configs else 0
            }
            
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

        capability_stats = {}
        
        for item in table_data:
            cat = item['capability']
            try:
                raw_score = float(item['score'])
            except (ValueError, TypeError):
                raw_score = 0.0
                
            metric = str(item['metric']).lower()
            norm_score = raw_score
            
            # 过滤负向指标，转换0-1分数
            is_negative_metric = any(x in metric for x in ['ppl', 'bpb', 'loss'])
            
            if is_negative_metric:
                continue 
            else:
                if 0.0 <= raw_score <= 1.0:
                    norm_score = raw_score * 100.0
            
            if cat not in capability_stats:
                capability_stats[cat] = []
            
            capability_stats[cat].append(norm_score)
        
        radar_data = []
        for cat, scores in capability_stats.items():
            if not scores:
                continue
            avg_score = sum(scores) / len(scores)
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

    def compare_tasks(self, task_ids: List[int]) -> Dict[str, Any]:
        """
        对比多个任务的结果 (必须基于同一 Scheme)
        """
        if len(task_ids) < 2:
            raise HTTPException(status_code=400, detail="至少选择两个任务进行对比")
            
        tasks = self.session.exec(
            select(EvaluationTask).where(EvaluationTask.id.in_(task_ids))
        ).all()
        
        if len(tasks) != len(task_ids):
             raise HTTPException(status_code=404, detail="部分任务未找到")

        base_scheme_id = tasks[0].scheme_id
        if not base_scheme_id:
             raise HTTPException(status_code=400, detail="无法对比未绑定方案的任务")
             
        for t in tasks:
            if t.scheme_id != base_scheme_id:
                raise HTTPException(status_code=400, detail="所有任务必须属于同一个评测方案")
        
        scheme = self.session.get(EvaluationScheme, base_scheme_id)
        scheme_name = scheme.name if scheme else "Unknown Scheme"

        models_meta = []
        task_id_to_model_name = {}
        
        for t in tasks:
            model = self.session.get(LLMModel, t.model_id)
            model_name = model.name if model else f"Unknown-{t.model_id}"
            display_name = f"{model_name} (#{t.id})"
            
            models_meta.append({
                "task_id": t.id,
                "model_name": model_name,
                "display_name": display_name,
                "finished_at": t.finished_at
            })
            task_id_to_model_name[t.id] = display_name

        table_map = {}
        capability_map = {t.id: {} for t in tasks}

        all_results = self.session.exec(
            select(EvaluationResult).where(EvaluationResult.task_id.in_(task_ids))
        ).all()
        
        for res in all_results:
            row_key = f"{res.dataset_name} ({res.metric_name})"
            if row_key not in table_map:
                table_map[row_key] = {
                    "dataset": res.dataset_name,
                    "metric": res.metric_name,
                    "scores": {} 
                }
            table_map[row_key]["scores"][res.task_id] = res.score
            
            config = self.session.get(DatasetConfig, res.dataset_config_id)
            if config:
                cat = config.meta.category
                if cat not in capability_map[res.task_id]:
                    capability_map[res.task_id][cat] = []
                
                score_val = res.score
                if 0 <= score_val <= 1.0: score_val *= 100
                capability_map[res.task_id][cat].append(score_val)

        final_table = []
        for key, info in table_map.items():
            row = {
                "dataset_metric": key,
                "dataset": info['dataset'],
                "metric": info['metric']
            }
            base_score = None
            
            for i, task_id in enumerate(task_ids):
                score = info["scores"].get(task_id, None)
                row[f"task_{task_id}"] = score
                
                if i == 0:
                    base_score = score
                else:
                    if base_score is not None and score is not None:
                        row[f"diff_{task_id}"] = round(score - base_score, 2)
                    else:
                        row[f"diff_{task_id}"] = None
            
            final_table.append(row)

        radar_indicators = [] 
        radar_series = []     
        
        all_categories = set()
        for t_map in capability_map.values():
            all_categories.update(t_map.keys())
        
        sorted_cats = sorted(list(all_categories))
        radar_indicators = [{"name": c, "max": 100} for c in sorted_cats]
        
        for task_id in task_ids:
            task_scores = []
            for cat in sorted_cats:
                scores_list = capability_map[task_id].get(cat, [])
                if scores_list:
                    avg = sum(scores_list) / len(scores_list)
                    task_scores.append(round(min(avg, 100), 1))
                else:
                    task_scores.append(0) 
            
            radar_series.append({
                "name": task_id_to_model_name[task_id],
                "value": task_scores
            })

        return {
            "scheme_name": scheme_name,
            "models": models_meta,
            "radar_indicators": radar_indicators,
            "radar_data": radar_series,
            "table_data": final_table
        }