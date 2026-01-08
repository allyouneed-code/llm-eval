import os
import sys
import glob
import json
import ast
import re
import logging
from sqlmodel import Session, select

# 1. 静音设置
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)

# 2. 环境设置
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from app.core.database import engine
from app.models.dataset import DatasetMeta, DatasetConfig
# 引入 Task 和 Result 防止关系报错
from app.models.task import EvaluationTask
from app.models.result import EvaluationResult

# 3. 加载官方映射表
CAPABILITY_MAP_FILE = os.path.join(current_dir, "dataset_capabilities.json")
CAPABILITY_MAP = {}
if os.path.exists(CAPABILITY_MAP_FILE):
    try:
        with open(CAPABILITY_MAP_FILE, "r", encoding="utf-8") as f:
            raw_map = json.load(f)
            # 转小写键，方便匹配
            CAPABILITY_MAP = {k.lower(): v for k, v in raw_map.items()}
    except: pass

# ==========================================
# 🆕 4. 加载数据量统计报告 (strict_match_report.json)
# ==========================================
DATA_COUNTS = {}
# 尝试在当前目录或脚本目录下寻找报告文件
POSSIBLE_REPORT_PATHS = [
    "strict_match_report.json",
    os.path.join(current_dir, "strict_match_report.json"),
    os.path.join(backend_dir, "strict_match_report.json")
]
for p in POSSIBLE_REPORT_PATHS:
    if os.path.exists(p):
        print(f"📉 发现数据量报告: {p}")
        try:
            with open(p, "r", encoding="utf-8") as f:
                report_data = json.load(f)
                # 构建映射表: Meta Name -> Count
                for item in report_data.get("details", []):
                    if "name" in item and "count" in item:
                        DATA_COUNTS[item["name"]] = item["count"]
            print(f"   ✅ 已加载 {len(DATA_COUNTS)} 条数据量记录")
            break
        except Exception as e:
            print(f"   ⚠️ 报告加载失败: {e}")

# 5. Evaluator 映射表 (保持不变)
EVALUATOR_MAPPING = {
    # ... (保持原有的映射内容不变，节省篇幅) ...
    "AccEvaluator": "Accuracy",
    "AccwithDetailsEvaluator": "Accuracy",
    "Accuracy": "Accuracy",
    "EMEvaluator": "Exact Match",
    "ExactMatchEvaluator": "Exact Match",
    "HumanEvalEvaluator": "Pass@k",
    "MBPPEvaluator": "Pass@k",
    "BigCodeBenchEvaluator": "Pass@k",
    "HumanevalPlusEvaluator": "Pass@k",
    "HumanevalXEvaluator": "Pass@k",
    "MBPPPassKEvaluator": "Pass@k",
    "DS1000Evaluator": "Pass@k",
    "LCBCodeGenerationEvaluator": "Pass@k",
    "CodeCompassEvaluator": "Pass@k",
    "SciCodeEvaluator": "Pass@k",
    "MATHEvaluator": "Accuracy",
    "Gsm8kEvaluator": "Accuracy",
    "MathVerifyEvaluator": "Accuracy",
    "LiveMathBenchEvaluator": "Accuracy",
    "GaoKaoMATHEvaluator": "Accuracy",
    "OmniMathEvaluator": "Accuracy",
    "SuperGPQAEvaluator": "Accuracy",
    "MMLUEvaluator": "Accuracy",
    "MMLUProBaseEvaluator": "Accuracy",
    "AGIEvalEvaluator": "Accuracy",
    "CEvalEvaluator": "Accuracy",
    "CMPhysBenchEvaluator": "Accuracy",
    "GPQAEvaluator": "Accuracy",
    "BBHEvaluator": "Exact Match",
    "TriviaQAEvaluator": "Exact Match",
    "DropEvaluator": "F1 Score",
    "TruthfulQAEvaluator": "Truthfulness",
    "BleuEvaluator": "BLEU",
    "RougeEvaluator": "ROUGE",
    "JiebaRougeEvaluator": "ROUGE",
    "MeteorEvaluator": "METEOR",
    "LVEvalOPTRougeEvaluator": "ROUGE",
    "NeedleBenchOriginEvaluator": "Recall",
    "NeedleBenchMultiEvaluator": "Recall",
    "NeedleBenchParallelEvaluator": "Recall",
    "RulerNiahEvaluator": "Recall",
    "LongBenchF1Evaluator": "F1 Score",
    "LongBenchRougeEvaluator": "ROUGE",
    "LVEvalF1Evaluator": "F1 Score",
    "BabiLongEvaluator": "Accuracy",
    "GenericLLMEvaluator": "LLM Score",
    "LMEvaluator": "Perplexity", 
    "JudgeEvaluator": "LLM Score",
    "ArenaHardEvaluator": "Win Rate",
    "ToxicEvaluator": "Toxicity",
    "CrowspairsEvaluator": "Accuracy",
    "CircularEvaluator": "Consistency",
    "AttackSuccessRate": "ASR"
}

VERSION_PATTERN = re.compile(r'_[0-9a-f]{6}\.py$')
REGEX_EVALUATOR = re.compile(r"\b([a-zA-Z0-9_]+Evaluator)\b")

# ... (辅助函数 extract_metric_from_file, infer_metric_by_filename, infer_mode_strict 保持不变) ...

def extract_metric_from_file(file_path):
    content = ""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except: return None
    matches = REGEX_EVALUATOR.findall(content)
    for eval_cls in reversed(matches):
        if eval_cls in EVALUATOR_MAPPING: return EVALUATOR_MAPPING[eval_cls]
        if "Acc" in eval_cls: return "Accuracy"
        if "Bleu" in eval_cls: return "BLEU"
        if "Rouge" in eval_cls: return "ROUGE"
        if "PassK" in eval_cls: return "Pass@k"
        if "ExactMatch" in eval_cls: return "Exact Match"
    return None

def infer_metric_by_filename(filename):
    name = filename.lower()
    if 'code' in name or 'mbpp' in name or 'humaneval' in name: return "Pass@k"
    if 'math' in name or 'gsm8k' in name: return "Accuracy"
    if 'translation' in name or 'wmt' in name: return "BLEU"
    if 'summarization' in name: return "ROUGE"
    return "Accuracy"

def infer_mode_strict(filename):
    name = filename.replace(".py", "").lower()
    if "_gen" in name: return "gen"
    if "_ppl" in name: return "ppl"
    if "_mixed" in name: return "mixed"
    return None

# ... (辅助函数 infer_category_heuristics, resolve_meta_and_category, infer_modality 保持不变) ...

def infer_category_heuristics(name):
    """关键词兜底逻辑 (增强版)"""
    n = name.lower()
    if any(x in n for x in ['math', 'gsm8k', 'arithmetic', 'theorem', 'algebra', 'calculus']): return "Math"
    if any(x in n for x in ['code', 'mbpp', 'humaneval', 'python', 'java', 'sql']): return "Code"
    if any(x in n for x in ['mmlu', 'ceval', 'agieval', 'exam', 'bench', 'choice']): return "Knowledge"
    if any(x in n for x in ['translation', 'wmt', 'bleu', 'flores']): return "Translation"
    if any(x in n for x in ['chat', 'dialog', 'conversation']): return "Dialogue"
    if any(x in n for x in ['safety', 'toxic', 'bias', 'jailbreak']): return "Safety"
    if any(x in n for x in ['reason', 'logic', 'nli', 'qa', 'reading', 'arc', 'hellaswag']): return "Reasoning"
    if any(x in n for x in ['long', 'context', 'needle', 'lveval', 'lv-eval', 'book']): return "Long Context"
    if any(x in n for x in ['vision', 'image', 'video', 'mmbench']): return "Multimodal"
    return None

def resolve_meta_and_category(file_path, oc_root):
    abs_datasets_dir = os.path.join(oc_root, "configs", "datasets")
    if not file_path.startswith(abs_datasets_dir):
        return os.path.basename(os.path.dirname(file_path)), "Other"
        
    rel_path = os.path.relpath(file_path, abs_datasets_dir)
    parts = rel_path.replace("\\", "/").split("/")
    
    meta_name = parts[-2] if len(parts) >= 2 else parts[0]
    category = "Other"
    
    if meta_name.lower() in CAPABILITY_MAP:
        category = CAPABILITY_MAP[meta_name.lower()]
    
    if category == "Other":
        for k, v in CAPABILITY_MAP.items():
            if k in meta_name.lower():
                category = v
                break
    
    if category == "Other":
        h_cat = infer_category_heuristics(meta_name)
        if h_cat:
            category = h_cat
            
    return meta_name, category

def infer_modality(meta_name):
    n = meta_name.lower()
    if any(x in n for x in ['video', 'activitynet', 'msrvtt']): return "Video"
    if any(x in n for x in ['audio', 'speech', 'aishell']): return "Audio"
    if any(x in n for x in ['image', 'vision', 'visual', 'mmbench', 'coco', 'flickr', 'vqav2', 'ocr', 'caption']): return "Image"
    return "Text"

# ... (AST 辅助函数保持不变) ...

def ast_to_dict(node):
    if isinstance(node, ast.Dict):
        return {ast_to_dict(k): ast_to_dict(v) for k, v in zip(node.keys, node.values)}
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'dict':
        return {k.arg: ast_to_dict(k.value) for k in node.keywords}
    elif isinstance(node, ast.Constant): 
        return node.value
    elif isinstance(node, ast.Str):
        return node.s
    elif isinstance(node, ast.Num):
        return node.n
    elif isinstance(node, ast.Name):
        return node.id 
    return None

def parse_ast_for_extra_fields(file_path):
    evaluator_type = ""
    post_process_cfg = {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == 'eval_cfg':
                        value_node = node.value
                        if isinstance(value_node, ast.Call) and value_node.keywords:
                            for kw in value_node.keywords:
                                if kw.arg == 'evaluator':
                                    ev_dict = ast_to_dict(kw.value)
                                    if ev_dict and 'type' in ev_dict:
                                        evaluator_type = str(ev_dict['type'])
                                if kw.arg == 'pred_postprocessor':
                                    pp_dict = ast_to_dict(kw.value)
                                    if pp_dict:
                                        post_process_cfg = pp_dict
                        break
    except Exception as e:
        pass
    return evaluator_type, post_process_cfg

def infer_task_type(evaluator_type, post_process_cfg):
    pp_type = str(post_process_cfg.get('type', '')).lower()
    ev_type = evaluator_type.lower()
    if 'option' in pp_type or 'capital' in pp_type: return 'multiple_choice'
    if 'acc' in ev_type: return 'multiple_choice' 
    if 'em' in ev_type or 'exact' in ev_type: return 'cloze'
    return 'qa'

# ==========================================
# 🚀 主流程
# ==========================================
def process_and_save(session: Session, oc_root: str):
    target_dir = os.path.join(oc_root, "configs", "datasets")
    if not os.path.exists(target_dir):
        if os.path.exists(oc_root) and "datasets" in oc_root:
            target_dir = oc_root
            oc_root = os.path.dirname(os.path.dirname(target_dir))
        else:
            print(f"❌ 错误：找不到 configs/datasets 路径 -> {target_dir}")
            return

    print(f"🚀 [V10-验收终极版] 开始扫描: {target_dir}")
    print(f"   ℹ️  特性: 映射表 > Modality > 注入 Data Count")
    
    py_files = glob.glob(os.path.join(target_dir, "**/*.py"), recursive=True)
    print(f"📄 物理文件总数: {len(py_files)}")
    
    success_count = 0
    skipped_count = 0
    
    for i, file_path in enumerate(py_files):
        if i > 0 and i % 500 == 0: print(f"   ...进度 {i}/{len(py_files)}")
        
        filename = os.path.basename(file_path)
        if filename == "__init__.py": continue
        if VERSION_PATTERN.search(filename): continue
        if filename.endswith("_settings.py") or filename.endswith("_base.py") or filename.endswith("_common.py"):
            skipped_count += 1
            continue

        try:
            # 1. Strict Mode
            mode = infer_mode_strict(filename)
            if not mode:
                skipped_count += 1
                continue

            # 2. Resolve Meta & Category
            meta_name, category = resolve_meta_and_category(file_path, oc_root)
            
            # 3. Infer Modality
            modality = infer_modality(meta_name)
            
            # 🆕 4. 获取数据量 (从报告中查找)
            data_count = DATA_COUNTS.get(meta_name, 0)
            
            # 5. Metric
            metric = extract_metric_from_file(file_path)
            if not metric:
                metric = infer_metric_by_filename(filename)
            
            # 6. Extract Extra Fields
            ast_eval_type, ast_pp_cfg = parse_ast_for_extra_fields(file_path)
            task_type = infer_task_type(ast_eval_type, ast_pp_cfg)
            
            # 7. DB Operations
            # Meta
            meta = session.exec(select(DatasetMeta).where(DatasetMeta.name == meta_name)).first()
            if not meta:
                meta = DatasetMeta(
                    name=meta_name, 
                    category=category, 
                    modality=modality,
                    description="Official Dataset",
                    data_count=data_count # 🆕 创建时注入数量
                )
                session.add(meta)
                session.flush()
            else:
                needs_meta_update = False
                if meta.category != category: 
                    meta.category = category
                    needs_meta_update = True
                
                if meta.modality != modality:
                    meta.modality = modality
                    needs_meta_update = True
                
                # 🆕 更新时同步数量 (如果数据库里是0或者与报告不一致，以报告为准)
                # 只有当报告里有非0值时才去覆盖，防止把已有的覆盖成0
                if data_count > 0 and meta.data_count != data_count:
                    meta.data_count = data_count
                    needs_meta_update = True
                    
                if needs_meta_update:
                     session.add(meta)
                     session.flush()

            # Config
            config_name = filename.replace('.py', '')
            try:
                rel_path = os.path.relpath(file_path, oc_root).replace("\\", "/")
            except:
                rel_path = f"configs/datasets/{meta_name}/{filename}"
            official_path = f"official://{rel_path}"

            existing = session.exec(select(DatasetConfig).where(DatasetConfig.config_name == config_name, DatasetConfig.meta_id == meta.id)).first()
            
            if existing:
                needs_update = False
                if existing.display_metric != metric: existing.display_metric = metric; needs_update = True
                if existing.mode != mode: existing.mode = mode; needs_update = True
                if existing.file_path != official_path: existing.file_path = official_path; needs_update = True
                if existing.task_type != task_type: existing.task_type = task_type; needs_update = True
                new_pp_json = json.dumps(ast_pp_cfg, ensure_ascii=False)
                if existing.post_process_cfg != new_pp_json: existing.post_process_cfg = new_pp_json; needs_update = True
                
                if needs_update:
                    session.add(existing)
                    session.commit()
                continue
            
            db_config = DatasetConfig(
                meta_id=meta.id,
                config_name=config_name,
                mode=mode,
                file_path=official_path,
                display_metric=metric,
                task_type=task_type,
                post_process_cfg=json.dumps(ast_pp_cfg, ensure_ascii=False),
                reader_cfg="{}", infer_cfg="{}", metric_config="{}"
            )
            session.add(db_config)
            session.commit()
            success_count += 1
            
        except Exception:
            session.rollback()
            continue

    print(f"\n🎉 V10 录入完成！")
    print(f"   ✅ 成功录入: {success_count}")
    print(f"   🧹 过滤噪音: {skipped_count}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python scripts/seed_via_ast_v10.py <path>")
        sys.exit(1)
    
    from sqlmodel import SQLModel
    # 确保数据库表已创建 (如果之前没创建过)
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        process_and_save(session, sys.argv[1])