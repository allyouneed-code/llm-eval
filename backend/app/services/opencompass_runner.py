import os
import subprocess
import glob
import logging
import torch
import json
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
        
        # 定义官方配置文件的根目录 (假设运行在 backend 目录下，数据存放在 data/official)
        # 如果是 Docker 环境，通常是 /app/data/official
        self.official_data_root = os.path.abspath(os.path.join("data", "official"))

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
        【配置生成】
        生成用于 OpenCompass 运行的 Python 配置文件
        支持混合加载：
        1. 私有数据集 (JSONL + 动态生成 Config)
        2. 官方数据集 (加载本地 .py 配置文件)
        """
        
        # 1. 准备路径
        workspace_str = str(os.path.abspath(self.workspace)).replace("\\", "/")
        
        # =========================================================
        # 第一部分：生成 dataset_loader.py (用于私有数据集)
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
        
        # --- 2.1 构建数据集列表 (混合模式) ---
        private_ds_lines = []
        official_read_lines = []
        official_ds_vars = []

        for idx, ds in enumerate(datasets):
            # 🟢 分支 A：官方数据集 (约定 file_path 以 official:// 开头)
            if ds.file_path and ds.file_path.startswith("official://"):
                # 解析真实路径
                # 数据库存: official://configs/gsm8k/gsm8k_gen.py
                # 真实路径: /app/data/official/configs/gsm8k/gsm8k_gen.py
                relative_path = ds.file_path.replace("official://", "")
                real_config_path = os.path.join(self.official_data_root, relative_path)
                
                # 路径转义 (Windows兼容)
                real_config_path = str(real_config_path).replace("\\", "/")
                
                if not os.path.exists(real_config_path):
                    logger.error(f"❌ Official config file missing: {real_config_path}")
                    # 如果找不到文件，暂时跳过，防止整个任务挂掉
                    continue

                var_name = f"official_ds_{idx}"
                
                # 生成读取官方配置的代码
                code_block = [
                    f"",
                    f"# --- Official Dataset: {ds.config_name} ---",
                    f"# Loading from: {real_config_path}",
                    f"_tmp_cfg_{idx} = Config.fromfile('{real_config_path}')",
                    f"# 尝试提取 datasets 变量，通常是一个 list",
                    f"{var_name} = _tmp_cfg_{idx}.get('datasets', [])",
                    f"# Force override 'abbr' to match DB config_name for result mapping",
                    f"for item in {var_name}:",
                    f"    item['abbr'] = '{ds.config_name}'"
                ]
                official_read_lines.extend(code_block)
                official_ds_vars.append(var_name)
                continue

            # 🔵 分支 B：私有数据集 (JSONL)
            # 1. 路径处理
            fpath = str(ds.file_path).replace("\\", "/") if ds.file_path else ""
            if fpath and not os.path.isabs(fpath):
                 fpath = os.path.abspath(fpath).replace("\\", "/")

            # 2. 解析 JSON 配置
            try: reader_cfg = json.loads(ds.reader_cfg) if ds.reader_cfg else {}
            except: reader_cfg = {}
            try: infer_cfg = json.loads(ds.infer_cfg) if ds.infer_cfg else {}
            except: infer_cfg = {}
            try: metric_cfg = json.loads(ds.metric_config) if getattr(ds, 'metric_config', None) else {}
            except: metric_cfg = {}
            try: post_process_cfg = json.loads(ds.post_process_cfg) if getattr(ds, 'post_process_cfg', None) else {}
            except: post_process_cfg = {}

            # 3. 逻辑整合
            
            # (A) 组装 eval_cfg
            eval_cfg = metric_cfg.copy()
            if not eval_cfg.get('evaluator'):
                eval_cfg['evaluator'] = {'type': 'AccEvaluator'}
            
            # 注入后处理配置
            if post_process_cfg and post_process_cfg.get("type"):
                eval_cfg["pred_postprocessor"] = dict(
                    type=post_process_cfg["type"],
                    **{k: v for k, v in post_process_cfg.items() if k != "type"}
                )

            # (B) 清理 reader_cfg (移除前端 mapping)
            clean_reader_cfg = {k: v for k, v in reader_cfg.items() if k != 'mapping'}
            if not clean_reader_cfg:
                clean_reader_cfg = dict(input_columns=['question', 'textA', 'textB', 'textC', 'textD'],output_column='answerKey')

            # (C) 兜底 infer_cfg
            if not infer_cfg:
                 infer_cfg = {
                    'prompt_template': {
                        'type': 'PromptTemplate',
                        'template': dict(round=[dict(role='HUMAN', prompt='Question: {question}\nAnswer:')])
                    },
                    'retriever': {'type': 'ZeroRetriever'},
                    'inferencer': {'type': 'GenInferencer'}
                 }

            item = {
                'abbr': ds.config_name,
                'type': 'SimpleJsonlDataset',
                'path': fpath,
                'reader_cfg': clean_reader_cfg,
                'infer_cfg': infer_cfg,
                'eval_cfg': eval_cfg
            }
            private_ds_lines.append(f"    dict({json.dumps(item, ensure_ascii=False)}),")
            
        # --- 2.2 合并所有数据集 ---
        # 生成私有 datasets 列表代码
        if private_ds_lines:
            private_block = "private_datasets = [\n" + "\n".join(private_ds_lines) + "\n]"
        else:
            private_block = "private_datasets = []"
            
        # 生成合并代码: datasets = private_datasets + official_ds_0 + ...
        all_lists = ["private_datasets"] + official_ds_vars
        combine_block = f"datasets = {' + '.join(all_lists)}"

        # --- 2.3 构建模型列表 ---
        m_abbr = str(model.name)       # 仅用于日志显示的简称
        m_model_id = str(model.path)   # API 真正调用的模型 ID (如 gpt-4)
        m_key = str(model.api_key) if model.api_key else "" # 默认防空
        m_base_url = str(model.base_url) if model.base_url else ""
        
        # 准备 Import 语句
        if model.type == "api":
            model_import_stmt = "from opencompass.models import OpenAI"
            models_block = f"""
models = [
    dict(
        type=OpenAI,
        abbr='{m_abbr}',              # 评测结果中显示的列名
        path='{m_model_id}',          # 传给 API 的模型参数 (model="gpt-4")
        key='{m_key}',                # API Key
        openai_api_base='{m_base_url}', # API Base URL
        meta_template=dict(
            round=[
                dict(role='HUMAN', api_role='HUMAN'),
                dict(role='BOT', api_role='BOT', generate=True),
            ],
        ),
        query_per_second=1,
        max_out_len=2048,
        max_seq_len=4096,
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
            # 🌟 必须导入 Config 以支持 fromfile 加载
            "from mmengine.config import Config",
            
            # 导入 OpenCompass 通用组件
            "from opencompass.openicl.icl_prompt_template import PromptTemplate",
            "from opencompass.openicl.icl_retriever import ZeroRetriever",
            "from opencompass.openicl.icl_inferencer import GenInferencer",
            "from opencompass.openicl.icl_evaluator import AccEvaluator",
            "from opencompass.openicl.icl_evaluator import BleuEvaluator",
            "from opencompass.openicl.icl_evaluator import RougeEvaluator",
            "from opencompass.utils.text_postprocessors import first_option_postprocess",
            "from opencompass.utils.text_postprocessors import first_capital_postprocess",
            
            # 导入私有数据集加载器
            "from dataset_loader import SimpleJsonlDataset",
            
            # 导入模型类
            model_import_stmt, 
            "",
            # 🟢 1. 插入官方数据集加载代码
            "\n".join(official_read_lines),
            "",
            # 🔵 2. 插入私有数据集定义
            private_block,
            "",
            # 🟡 3. 合并列表
            combine_block,
            "",
            # 4. 类型修正 (Type Fixes for Private Datasets)
            # 因为私有数据集是通过 JSON 拼装的，类名是字符串，需要替换为真实类引用
            "for ds in datasets:",
            "    # 只处理私有数据集 (SimpleJsonlDataset)",
            "    if ds.get('type') == 'SimpleJsonlDataset':",
            "        ds['type'] = SimpleJsonlDataset",
            "",
            "        # Infer Config Types",
            "        if 'infer_cfg' in ds:",
            "            if ds['infer_cfg'].get('prompt_template', {}).get('type') == 'PromptTemplate':",
            "                ds['infer_cfg']['prompt_template']['type'] = PromptTemplate",
            "            if ds['infer_cfg'].get('retriever', {}).get('type') == 'ZeroRetriever':",
            "                ds['infer_cfg']['retriever']['type'] = ZeroRetriever",
            "            if ds['infer_cfg'].get('inferencer', {}).get('type') == 'GenInferencer':",
            "                ds['infer_cfg']['inferencer']['type'] = GenInferencer",
            "",
            "        # Eval Config Types",
            "        if 'eval_cfg' in ds:",
            "            ev_type = ds['eval_cfg'].get('evaluator', {}).get('type')",
            "            if ev_type == 'AccEvaluator':",
            "                ds['eval_cfg']['evaluator']['type'] = AccEvaluator",
            "            elif ev_type == 'BleuEvaluator':",
            "                ds['eval_cfg']['evaluator']['type'] = BleuEvaluator",
            "            elif ev_type == 'RougeEvaluator':",
            "                ds['eval_cfg']['evaluator']['type'] = RougeEvaluator",
            "",
            "            pp_type = ds['eval_cfg'].get('pred_postprocessor', {}).get('type')",
            "            if pp_type == 'first_option_postprocess':",
            "                ds['eval_cfg']['pred_postprocessor']['type'] = first_option_postprocess",
            "            elif pp_type == 'first_capital_postprocess':",
            "                ds['eval_cfg']['pred_postprocessor']['type'] = first_capital_postprocess",
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
            # 清理命名空间，防止生成的 Config 包含不必要的变量
            "try:",
            "    del os, sys, SimpleJsonlDataset, OpenAI",
            "    del PromptTemplate, ZeroRetriever, GenInferencer, AccEvaluator",
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