import os
import json
from typing import Dict, Any

# 引入 OpenCompass 的组件 (模拟导入，实际运行时环境中要有这些包)
# 如果是动态生成字符串供 eval() 使用，则不需要 import，但为了生成 Python Config 文件，通常是生成字典或代码字符串
# 这里假设我们生成一个 Python 字典结构，OpenCompass Runner 会将其转为 Config 对象

class ConfigFactory:
    """
    负责将数据库中的 DatasetConfig 转换为 OpenCompass 可执行的 Python 配置字典
    """
    
    @staticmethod
    def convert_to_opencompass_config(db_config: Any) -> Dict[str, Any]:
        """
        :param db_config: SQLModel 对象 (DatasetConfig)
        :return: 符合 OpenCompass 要求的 dataset 配置字典
        """
        
        # 1. 基础路径检查
        if not os.path.exists(db_config.file_path):
            raise FileNotFoundError(f"Dataset file not found: {db_config.file_path}")

        # 2. 解析 JSON 字段
        reader_cfg = json.loads(db_config.reader_cfg)
        infer_cfg = json.loads(db_config.infer_cfg)
        metric_cfg = json.loads(db_config.metric_config) # 注意：这里存的是 eval_cfg 的主体
        post_process_cfg = json.loads(db_config.post_process_cfg)
        few_shot_cfg = json.loads(db_config.few_shot_cfg)

        # -------------------------------------------------
        # 3. 组装 eval_cfg (核心修正点)
        # OpenCompass 要求 pred_postprocessor 在 eval_cfg 中
        # -------------------------------------------------
        eval_cfg = metric_cfg.copy()
        
        # 如果配置了后处理，注入到 eval_cfg 中
        if post_process_cfg and post_process_cfg.get("type"):
            eval_cfg["pred_postprocessor"] = dict(
                type=post_process_cfg["type"],
                # 有些后处理需要参数，比如提取首选项需要 'options': 'ABCD'
                **{k: v for k, v in post_process_cfg.items() if k != "type"}
            )

        # -------------------------------------------------
        # 4. 组装 reader_cfg (注入文件路径)
        # -------------------------------------------------
        # 对于 JSONL 文件，OpenCompass 通常使用 JsonlDataset 这里的配置要根据实际使用的 Dataset 类来定
        # 如果使用通用的 CustomDataset (假设)
        
        dataset_config = dict(
            # 必须指定 type，这里假设 OpenCompass 环境里有一个通用的 JsonlDataset 
            # 或者使用 'opencompass.datasets.JsonlDataset'
            # 如果是 csv，可能需要 CSVDataset
            type='opencompass.datasets.JsonlDataset', 
            path=db_config.file_path,
            
            # Reader Config 直接透传 (包含 input_columns, output_column)
            # 注意：OpenCompass 的 reader_cfg 只要 input_columns/output_column
            # 前端的 'mapping' 字段 OpenCompass 无法识别，需要剔除，或者保留也无害(通常会忽略)
            reader_cfg={k: v for k, v in reader_cfg.items() if k != 'mapping'},
            
            # Infer Config
            infer_cfg=infer_cfg,
            
            # Eval Config (包含 evaluator 和 postprocessor)
            eval_cfg=eval_cfg
        )
        
        # -------------------------------------------------
        # 5. 处理 Few-shot (如果有)
        # -------------------------------------------------
        if few_shot_cfg:
            # OpenCompass 的 few-shot 通常配置在 infer_cfg.retriever 中
            # 或者作为独立的配置项，具体取决于版本。
            # 这里假设是标准的 retriever 增强
            dataset_config['infer_cfg']['retriever'] = dict(
                type='opencompass.openicl.icl_retriever.FixKRetriever',
                fix_id_list=few_shot_cfg.get('fix_id_list', []),
                # 或者使用其他 Retriever
            )

        # 返回包装好的列表 (因为 OpenCompass datasets 字段通常是 list)
        return dataset_config