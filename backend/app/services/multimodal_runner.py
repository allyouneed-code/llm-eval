import os
import time
import json
import csv
import random
import logging
from typing import List, Dict, Any
from datetime import datetime

from app.models.dataset import DatasetConfig
from app.models.llm_model import LLMModel

logger = logging.getLogger(__name__)

class MultimodalRunner:
    """
    多模态评测运行器 (Simulation Version)
    目前用于模拟 VLMEvalKit 的行为：
    1. 检查图片/视频文件是否存在
    2. 模拟推理过程 (sleep)
    3. 生成伪造的 CSV 结果
    """

    def __init__(self, workspace: str):
        self.workspace = workspace
        os.makedirs(self.workspace, exist_ok=True)
        # 模拟 OpenCompass 的结果目录结构: {workspace}/{timestamp}/summary/
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = os.path.join(self.workspace, self.timestamp, "summary")
        os.makedirs(self.output_dir, exist_ok=True)

    def run(self, task_id: int, model: LLMModel, datasets: List[DatasetConfig]):
        """
        执行多模态评测 (Mock)
        """
        logger.info(f"🚀 [MultimodalRunner] Starting simulation for Task {task_id}...")
        
        # 1. 模拟环境检查与资源校验
        log_path = os.path.join(self.workspace, "multimodal_run.log")
        with open(log_path, "w", encoding="utf-8") as log_f:
            log_f.write(f"=== Multimodal Eval Simulation Start: {datetime.now()} ===\n")
            log_f.write(f"Model: {model.name} (Type: {model.type})\n")
            
            for ds in datasets:
                log_f.write(f"\nChecking dataset: {ds.config_name} ({ds.meta.modality})\n")
                
                # 检查 JSONL 文件是否存在
                if not os.path.exists(ds.file_path):
                    msg = f"❌ Index file not found: {ds.file_path}"
                    log_f.write(msg + "\n")
                    logger.error(msg)
                    # 真实场景可能会抛异常，模拟场景我们记录错误但继续
                    continue

                # 模拟：随机抽查几个资源文件是否存在
                # (这里简单读取 jsonl 的前几行来检查)
                try:
                    with open(ds.file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()[:5] # 只查前5行
                        for line in lines:
                            item = json.loads(line)
                            # 根据模态找字段
                            media_path = None
                            if ds.meta.modality == 'Image':
                                media_path = item.get('image')
                            elif ds.meta.modality == 'Video':
                                media_path = item.get('video')
                            elif ds.meta.modality == 'Audio':
                                media_path = item.get('audio')
                            
                            if media_path:
                                # 拼接绝对路径 (假设 jsonl 同级目录下)
                                base_dir = os.path.dirname(ds.file_path)
                                abs_media = os.path.join(base_dir, media_path)
                                if os.path.exists(abs_media):
                                    log_f.write(f"  ✅ Asset found: {media_path}\n")
                                else:
                                    log_f.write(f"  ⚠️ Asset MISSING: {media_path}\n")
                except Exception as e:
                    log_f.write(f"  ❌ Error reading index: {e}\n")

            # 2. 模拟推理耗时
            # 根据数据集数量，每个 sleep 2秒，假装在跑 GPU
            log_f.write("\nRunning inference on GPU (Simulated)...\n")
            time.sleep(2 * len(datasets)) 
            log_f.write("Inference finished.\n")

        # 3. 生成结果 CSV
        # 格式必须与 OpenCompassRunner.parse_results 兼容
        # 必需列: dataset, version, metric, mode, {model_name}
        
        csv_filename = f"summary_{self.timestamp}.csv"
        csv_path = os.path.join(self.output_dir, csv_filename)
        
        model_col_name = model.name  # 或者是 model.abbr
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            # 写入表头
            header = ['dataset', 'version', 'metric', 'mode', model_col_name]
            writer.writerow(header)
            
            for ds in datasets:
                # 生成一个 60~95 之间的随机分
                fake_score = round(random.uniform(60.0, 95.0), 2)
                
                # 为了看起来真实点，Image 任务可能分低一点
                if ds.meta.modality == 'Image':
                    fake_score = round(random.uniform(50.0, 85.0), 2)
                
                row = [
                    ds.config_name,       # dataset
                    '-',                  # version
                    ds.display_metric,    # metric (e.g. Accuracy)
                    'gen',                # mode
                    fake_score            # score
                ]
                writer.writerow(row)
        
        logger.info(f"✅ [MultimodalRunner] Simulation finished. Result: {csv_path}")
        return csv_path