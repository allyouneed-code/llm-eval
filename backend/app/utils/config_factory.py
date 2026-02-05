import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

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
        
        # 1. 安全解析 JSON 字段的辅助函数
        def safe_load(field_str):
            try:
                return json.loads(field_str) if field_str else {}
            except Exception as e:
                logger.error(f"解析 JSON 字段失败: {e}")
                return {}

        reader_cfg = safe_load(db_config.reader_cfg)
        infer_cfg = safe_load(db_config.infer_cfg)
        metric_cfg = safe_load(db_config.metric_config) # 对应数据库中的 metric_config
        post_process_cfg = safe_load(db_config.post_process_cfg)
        few_shot_cfg = safe_load(getattr(db_config, 'few_shot_cfg', "{}"))

        # -------------------------------------------------
        # 2. 组装 eval_cfg (核心修正点)
        # OpenCompass 要求 pred_postprocessor 必须嵌套在 eval_cfg 中
        # -------------------------------------------------
        eval_cfg = metric_cfg.copy()
        
        # 注入后处理配置
        if post_process_cfg and post_process_cfg.get("type"):
            eval_cfg["pred_postprocessor"] = dict(
                type=post_process_cfg["type"],
                # 透传除 type 外的所有参数 (如 options: 'ABCD')
                **{k: v for k, v in post_process_cfg.items() if k != "type"}
            )

        # -------------------------------------------------
        # 3. 组装基础 Dataset 配置
        # -------------------------------------------------
        dataset_config = dict(
            # 默认使用系统定义的 SimpleJsonlDataset 加载器
            type='SimpleJsonlDataset', 
            path=db_config.file_path,
            
            # 清理 reader_cfg：剔除前端专用的 'mapping' 字段，防止 OpenCompass 报错
            reader_cfg={k: v for k, v in reader_cfg.items() if k != 'mapping'},
            
            # 推理配置
            infer_cfg=infer_cfg,
            
            # 评估配置 (包含 evaluator 和 postprocessor)
            eval_cfg=eval_cfg
        )
        
        # -------------------------------------------------
        # 4. 处理 Few-shot (少样本) 逻辑
        # -------------------------------------------------
        if few_shot_cfg and few_shot_cfg.get('fix_id_list'):
            dataset_config['infer_cfg']['retriever'] = dict(
                type='opencompass.openicl.icl_retriever.FixKRetriever',
                fix_id_list=few_shot_cfg.get('fix_id_list', []),
            )

        return dataset_config