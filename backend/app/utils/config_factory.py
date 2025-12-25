import os

def create_dataset_config_file(
    dataset_name: str,
    file_path: str,  # 上传的 jsonl 文件绝对路径
    output_dir: str = "workspace/custom_configs"
) -> str:
    """
    为私有数据集生成 OpenCompass 适配的 python 配置文件
    返回生成的配置文件路径 (相对路径或绝对路径)
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 清理文件名，防止特殊字符
    safe_name = dataset_name.replace(" ", "_").lower()
    config_filename = f"{safe_name}_gen.py"
    config_path = os.path.join(output_dir, config_filename)

    # 这是一个通用的私有数据集配置模板 (针对 JSONL 格式)
    # 假设数据格式是 {"input": "...", "target": "..."}
    template = f"""
from opencompass.openicl.icl_prompt_template import PromptTemplate
from opencompass.openicl.icl_retriever import ZeroRetriever
from opencompass.openicl.icl_inferencer import GenInferencer
from opencompass.openicl.icl_evaluator import AccEvaluator
from opencompass.datasets import JsonlDataset

# 1. 定义数据集读取器
{safe_name}_reader_cfg = dict(
    input_columns=['input'],
    output_column='target',
)

# 2. 定义推理配置 (Prompt 模板)
{safe_name}_infer_cfg = dict(
    prompt_template=dict(
        type=PromptTemplate,
        template=dict(
            round=[
                dict(role='HUMAN', prompt='{{input}}'),
                dict(role='BOT', prompt='')
            ],
        ),
    ),
    retriever=dict(type=ZeroRetriever),
    inferencer=dict(type=GenInferencer),
)

# 3. 定义评测配置 (这里默认用精确匹配，如果是生成式通常需要更复杂的 evaluator)
{safe_name}_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator), 
)

# 4. 组合配置
{safe_name}_datasets = [
    dict(
        abbr='{safe_name}',
        type=JsonlDataset,
        path='{file_path}',  # 指向上传的原始数据文件
        reader_cfg={safe_name}_reader_cfg,
        infer_cfg={safe_name}_infer_cfg,
        eval_cfg={safe_name}_eval_cfg,
    )
]
"""
    
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(template)
        
    return config_path