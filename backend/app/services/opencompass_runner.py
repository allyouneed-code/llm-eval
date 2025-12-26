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
        :param workspace: 任务的独立工作目录，用于存放 config.py, 日志和输出结果
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
                "num_gpus": 1,          # 默认单任务单卡，可根据调度优化
                "max_out_len": 100,
                "batch_size": 8,        
            }
        else:
            logger.warning("⚠️ No GPU detected. Falling back to CPU mode (Very Slow).")
            return {
                "device_map": "'cpu'",
                "num_gpus": 0,
                "max_out_len": 20,      
                "batch_size": 1,
            }

    def generate_config(self, task_id: int, model: LLMModel, datasets: List[DatasetConfig]) -> str:
        """
        【配置生成 - Import修复版】
        修复 NameError: name 'OpenAI' is not defined 问题。
        确保在定义 models 列表之前，先完成类的 Import。
        """
        import json
        
        # 1. 准备路径
        workspace_str = str(os.path.abspath(self.workspace)).replace("\\", "/")
        
        # =========================================================
        # 第一部分：生成 dataset_loader.py
        # =========================================================
        loader_code = [
            "import json",
            "import os",
            "from opencompass.datasets import BaseDataset",
            "from datasets import Dataset",
            "",
            "class SimpleJsonlDataset(BaseDataset):",
            "    def load(self, path):",
            "        data_list = []",
            "        if not os.path.exists(path):",
            "            print(f'Warning: Dataset file not found: {path}')",
            "            return {'test': Dataset.from_list([]), 'train': Dataset.from_list([])}",
            "        with open(path, 'r', encoding='utf-8') as f:",
            "            for line in f:",
            "                line = line.strip()",
            "                if line:",
            "                    try:",
            "                        data_list.append(json.loads(line))",
            "                    except:",
            "                        pass",
            "        dataset = Dataset.from_list(data_list)",
            "        return {",
            "            'test': dataset,",
            "            'train': dataset,",
            "            'validation': dataset",
            "        }"
        ]
        
        loader_path = os.path.join(self.workspace, "dataset_loader.py")
        with open(loader_path, "w", encoding="utf-8") as f:
            f.write("\n".join(loader_code))
            
        # =========================================================
        # 第二部分：准备配置变量
        # =========================================================
        run_cfg = self._detect_device_config()
        
        # --- 2.1 构建数据集列表 ---
        ds_lines = []
        for ds in datasets:
            fpath = str(ds.file_path).replace("\\", "/") if ds.file_path else ""
            if fpath and not os.path.isabs(fpath):
                 fpath = os.path.abspath(fpath).replace("\\", "/")

            try: reader_cfg = json.loads(ds.reader_cfg) if ds.reader_cfg else {}
            except: reader_cfg = {}
            try: infer_cfg = json.loads(ds.infer_cfg) if ds.infer_cfg else {}
            except: infer_cfg = {}
            try: eval_cfg = json.loads(ds.metric_config) if getattr(ds, 'metric_config', None) else {}
            except: eval_cfg = {}

            # 兜底逻辑
            if not reader_cfg:
                reader_cfg = {'input_columns': ['question', 'textA', 'textB', 'textC', 'textD'], 'output_column': 'answerKey'}
            if not infer_cfg:
                 infer_cfg = {
                    'prompt_template': {
                        'type': 'PromptTemplate',
                        'template': {
                            'round': [{'role': 'HUMAN', 'prompt': 'Question: {question}\nA. {textA}\nB. {textB}\nC. {textC}\nD. {textD}\nAnswer:'}]
                        }
                    },
                    'retriever': {'type': 'ZeroRetriever'},
                    'inferencer': {'type': 'GenInferencer'}
                 }
            if not eval_cfg:
                eval_cfg = {
                    'evaluator': {'type': 'AccEvaluator'},
                    'pred_role': 'BOT',
                    'pred_postprocessor': {'type': 'first_option_postprocess', 'options': 'ABCD'}
                }

            item = {
                'abbr': ds.config_name,
                'type': 'SimpleJsonlDataset', 
                'path': fpath,
                'reader_cfg': reader_cfg,
                'infer_cfg': infer_cfg,
                'eval_cfg': eval_cfg
            }
            ds_lines.append(f"    dict({json.dumps(item, ensure_ascii=False)}),")
            
        datasets_block = "datasets = [\n" + "\n".join(ds_lines) + "\n]"

        # --- 2.2 构建模型列表 ---
        m_abbr = str(model.name)
        m_path_url = str(model.path) if model.path else "" 
        if "http" in m_path_url and "v1" in m_path_url and not m_path_url.endswith("/chat/completions"):
             if m_path_url.endswith("/"): m_path_url += "chat/completions"
             else: m_path_url += "/chat/completions"
        m_key = str(model.api_key) if model.api_key else ""
        
        # 关键修改：在这里只准备 Import 语句，不放在 models_block 后面
        if model.type == "api":
            model_import_stmt = "from opencompass.models import OpenAI"
            models_block = f"""
models = [
    dict(
        type=OpenAI,
        abbr='{m_abbr}',
        path='{m_abbr}',
        key='{m_key}',
        openai_api_base='{m_path_url}',
        meta_template=dict(
            round=[
                dict(role='HUMAN', api_role='HUMAN'),
                dict(role='BOT', api_role='BOT', generate=True),
            ],
        ),
        query_per_second=1,
        max_out_len=100,
        max_seq_len=2048,
        batch_size=1,
    )
]
"""
        else:
            model_import_stmt = "from opencompass.models import HuggingFaceCausalLM"
            m_local_path = str(model.path)
            models_block = f"""
models = [
    dict(
        type=HuggingFaceCausalLM,
        abbr='{m_abbr}',
        path='{m_local_path}',
        tokenizer_path='{m_local_path}',
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
"""

        # =========================================================
        # 第三部分：拼接主配置文件
        # =========================================================
        main_config_lines = [
            "import sys",
            "import os",
            f"sys.path.append(r'{workspace_str}')", 
            "from mmengine.config import Config",
            # 导入通用类
            "from opencompass.openicl.icl_prompt_template import PromptTemplate",
            "from opencompass.openicl.icl_retriever import ZeroRetriever",
            "from opencompass.openicl.icl_inferencer import GenInferencer",
            "from opencompass.openicl.icl_evaluator import AccEvaluator",
            "from opencompass.utils.text_postprocessors import first_option_postprocess",
            # 导入数据集加载器
            "from dataset_loader import SimpleJsonlDataset",
            # 👇👇👇 关键修复：模型类必须在 datasets 和 models 定义之前导入 👇👇👇
            model_import_stmt, 
            "",
            datasets_block,
            "",
            "# 类型修正",
            "for ds in datasets:",
            "    if ds.get('type') == 'SimpleJsonlDataset':",
            "        ds['type'] = SimpleJsonlDataset",
            "    if 'infer_cfg' in ds:",
            "        if ds['infer_cfg'].get('prompt_template', {}).get('type') == 'PromptTemplate':",
            "            ds['infer_cfg']['prompt_template']['type'] = PromptTemplate",
            "        if ds['infer_cfg'].get('retriever', {}).get('type') == 'ZeroRetriever':",
            "            ds['infer_cfg']['retriever']['type'] = ZeroRetriever",
            "        if ds['infer_cfg'].get('inferencer', {}).get('type') == 'GenInferencer':",
            "            ds['infer_cfg']['inferencer']['type'] = GenInferencer",
            "    if 'eval_cfg' in ds:",
            "        if ds['eval_cfg'].get('evaluator', {}).get('type') == 'AccEvaluator':",
            "            ds['eval_cfg']['evaluator']['type'] = AccEvaluator",
            "        if ds['eval_cfg'].get('pred_postprocessor', {}).get('type') == 'first_option_postprocess':",
            "            ds['eval_cfg']['pred_postprocessor']['type'] = first_option_postprocess",
            "",
            models_block,
            "",
            "summarizer = dict(",
            "    dataset_abbrs=[ds['abbr'] for ds in datasets],",
            "    summary_groups=[],",
            ")",
            "",
            f"work_dir = r'{workspace_str}'",
            "",
            "try:",
            "    del os, sys, SimpleJsonlDataset, OpenAI",
            "    del PromptTemplate, ZeroRetriever, GenInferencer, AccEvaluator, first_option_postprocess",
            "except:",
            "    pass"
        ]
        
        config_path = os.path.join(self.workspace, f"task_{task_id}_config.py")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write("\n".join(main_config_lines))
        
        logger.info(f"✅ Generated config file: {config_path}")
        return config_path

    def run(self, config_path: str, log_file_name: str = "output.log"):
        """
        【进程执行】
        """
        log_path = os.path.join(self.workspace, log_file_name)
        
        # 构造命令
        cmd = ["opencompass", config_path, "-w", self.workspace, "--debug"]
        logger.info(f"▶️ Starting OpenCompass execution: {' '.join(cmd)}")

        with open(log_path, "w", encoding="utf-8") as f_log:
            # 简单调用，阻塞等待完成
            # TODO: 后续可优化为实时读取 stdout 来更新进度
            process = subprocess.Popen(
                cmd,
                stdout=f_log,
                stderr=subprocess.STDOUT,
                text=True
            )
            return_code = process.wait()
            
            if return_code != 0:
                logger.error(f"❌ OpenCompass execution failed. Log: {log_path}")
                raise RuntimeError(f"OpenCompass exited with code {return_code}")
            
            logger.info("✅ OpenCompass execution finished successfully.")

    def parse_results(self) -> List[Dict[str, Any]]:
        """
        【结果解析】
        解析生成的 summary.csv
        """
        search_pattern = os.path.join(self.workspace, "*", "summary", "summary.csv")
        csv_files = glob.glob(search_pattern)
        
        if not csv_files:
            logger.warning("⚠️ No summary.csv found.")
            return []
        
        # 取最新生成的 CSV
        latest_csv = max(csv_files, key=os.path.getmtime)
        try:
            df = pd.read_csv(latest_csv)
            results = []
            
            for _, row in df.iterrows():
                row_dict = row.to_dict()
                
                # 简单清洗
                dataset_abbr = row_dict.get("dataset", "Unknown")
                metric = row_dict.get("metric", "score")
                
                # 提取分数：取最后一列数值列作为分数
                score = 0.0
                for col in reversed(df.columns):
                    val = row_dict[col]
                    if isinstance(val, (int, float)) and col not in ['version', 'metric', 'mode']:
                        score = float(val)
                        break
                
                results.append({
                    "dataset": dataset_abbr,
                    "metric": metric,
                    "score": score,
                    "raw_data": row_dict
                })
                
            return results
        except Exception as e:
            logger.error(f"❌ Failed to parse CSV: {e}")
            raise e