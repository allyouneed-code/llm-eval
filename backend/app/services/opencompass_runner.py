import os
import subprocess
import glob
import logging
import torch
import pandas as pd
from typing import List, Dict, Any
from app.models.llm_model import LLMModel
from app.models.dataset import DatasetConfig

# 设置日志
logger = logging.getLogger(__name__)

class OpenCompassRunner:
    def __init__(self, workspace: str):
        """
        初始化运行器
        :param workspace: 任务的工作目录，用于存放 config.py, 日志和输出结果
        """
        self.workspace = workspace
        # 确保工作目录存在
        os.makedirs(self.workspace, exist_ok=True)

    def _detect_device_config(self) -> Dict[str, Any]:
        """
        【环境探测】
        检测当前运行环境（GPU/CPU），返回适配的运行参数
        """
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            logger.info(f"🚀 Detected {gpu_count} GPUs. Using GPU mode.")
            return {
                "device_map": "'auto'",
                "num_gpus": 1,          # 单个任务默认占用 1 张卡
                "max_out_len": 100,
                "batch_size": 8,        # 显存足够时调大，加快速度
            }
        else:
            logger.warning("⚠️ No GPU detected. Falling back to CPU mode (Very Slow).")
            return {
                "device_map": "'cpu'",
                "num_gpus": 0,
                "max_out_len": 20,      # CPU 模式下缩短输出长度
                "batch_size": 1,
            }

    def generate_config(self, task_id: int, model: LLMModel, datasets: List[DatasetConfig]) -> str:
        """
        【配置生成】
        基于“引用”模式生成配置文件。
        不重新定义数据集，而是直接引用数据库中存储的 dataset.path
        """
        run_cfg = self._detect_device_config()
        
        # 1. 准备数据集路径列表
        # 这里的 ds.path 应该是 OpenCompass 容器内的有效路径
        # 例如: 'configs/datasets/gsm8k/gsm8k_gen.py' (官方)
        # 或者: 'workspace/custom_configs/my_data_gen.py' (私有)
        dataset_paths_list = [f"'{ds.path}'" for ds in datasets]
        base_datasets_str = ",\n    ".join(dataset_paths_list)

        # 2. 拼接完整的 Python 配置字符串
        # 核心逻辑：
        # (1) 使用 _base_ 加载所有数据集文件
        # (2) 遍历 locals() 找到所有加载进来的数据集变量 (通常以 _datasets 结尾)
        # (3) 将它们合并到最终的 datasets 列表中
        config_content = f"""
from opencompass.models import HuggingFaceCausalLM

# 1. 引用外部数据集配置
_base_ = [
    {base_datasets_str}
]

# 2. 自动聚合数据集
# OpenCompass 的数据集配置文件通常会定义一个变量，如 gsm8k_datasets
# 这里我们需要把这些分散的变量收集到一个名为 datasets 的总列表中
datasets = []
for _k, _v in locals().items():
    if _k.endswith('_datasets') and isinstance(_v, list):
        datasets.extend(_v)

# 3. 定义模型
models = [
    dict(
        type=HuggingFaceCausalLM,
        abbr='{model.name}',
        path='{model.path}',           # 模型在容器内的绝对路径
        tokenizer_path='{model.path}',
        model_kwargs=dict(
            device_map={run_cfg['device_map']},
            trust_remote_code=True
        ),
        tokenizer_kwargs=dict(
            padding_side='left',
            truncation_side='left',
            trust_remote_code=True
        ),
        max_out_len={run_cfg['max_out_len']},
        max_seq_len=2048,
        batch_size={run_cfg['batch_size']},
        run_cfg=dict(num_gpus={run_cfg['num_gpus']}),
    )
]

# 4. 结果汇总配置 (可选，自动根据数据集生成汇总表)
# 简单的自动汇总配置
summarizer = dict(
    dataset_abbrs=[ds['abbr'] for ds in datasets],
    summary_groups=sum([ds.get('summary_groups', []) for ds in datasets], []),
)

# 5. 指定工作目录
work_dir = '{self.workspace}'
"""
        
        # 3. 写入文件
        config_path = os.path.join(self.workspace, f"task_{task_id}_config.py")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(config_content)
        
        logger.info(f"✅ Generated config file at: {config_path}")
        return config_path

    def run(self, config_path: str, log_file_name: str = "output.log"):
        """
        【进程执行】
        调用子进程执行 OpenCompass 命令
        """
        log_path = os.path.join(self.workspace, log_file_name)
        
        # 构造命令: opencompass config.py -w work_dir --debug
        cmd = [
            "opencompass", 
            config_path, 
            "-w", self.workspace,
            "--debug"  # 保持 debug 以便排错
        ]

        logger.info(f"▶️ Starting OpenCompass execution: {' '.join(cmd)}")

        with open(log_path, "w", encoding="utf-8") as f_log:
            # 使用 Popen 调用
            process = subprocess.Popen(
                cmd,
                stdout=f_log,
                stderr=subprocess.STDOUT,  # 将 stderr 合并到 stdout
                text=True,
                bufsize=1  # 行缓冲，保证日志实时写入
            )
            
            # 阻塞等待结束
            return_code = process.wait()
            
            if return_code != 0:
                logger.error(f"❌ OpenCompass failed with exit code {return_code}. Check logs at {log_path}")
                raise RuntimeError(f"OpenCompass execution failed. Log: {log_path}")
            
            logger.info("✅ OpenCompass execution finished successfully.")

    def parse_results(self) -> List[Dict[str, Any]]:
        """
        【结果解析】
        查找最新的 summary.csv 并解析结果
        """
        # OpenCompass 输出目录结构: workspace/{timestamp}/summary/summary.csv
        search_pattern = os.path.join(self.workspace, "*", "summary", "summary.csv")
        csv_files = glob.glob(search_pattern)
        
        if not csv_files:
            logger.warning("⚠️ No summary.csv found. Evaluation might have failed.")
            return []
        
        # 取最新的文件
        latest_csv = max(csv_files, key=os.path.getmtime)
        logger.info(f"📊 Parsing results from: {latest_csv}")
        
        try:
            # 读取 CSV
            df = pd.read_csv(latest_csv)
            
            results = []
            # 简单解析逻辑：假设我们要把每一行都存下来
            # 通常 summary.csv 的列包括 dataset, version, metric, mode, <model_name>
            
            # 为了通用性，我们将结果转换为字典列表，交给 TaskService 去决定存哪些字段
            # 例如: [{'dataset': 'GSM8K', 'accuracy': 88.5}, ...]
            
            for _, row in df.iterrows():
                # 转换整行为字典
                row_dict = row.to_dict()
                
                # 做一点简单的数据清洗
                # 提取数据集名称，通常第一列是 dataset
                clean_result = {
                    "dataset": row_dict.get("dataset", "Unknown"),
                    "metric": row_dict.get("metric", "score"),
                    "mode": row_dict.get("mode", "unknown"),
                    "raw_data": row_dict  # 保留原始数据以备不时之需
                }
                
                # 尝试查找分数：通常是最后一列，或者列名等于模型名的那一列
                # 这里做一个简单的启发式查找：找最后一个是数字的列
                score = 0.0
                for col in reversed(df.columns):
                    val = row_dict[col]
                    if isinstance(val, (int, float)) and col not in ['version']:
                        score = val
                        break
                
                clean_result["score"] = score
                results.append(clean_result)
                
            return results

        except Exception as e:
            logger.error(f"❌ Failed to parse CSV: {e}")
            raise e