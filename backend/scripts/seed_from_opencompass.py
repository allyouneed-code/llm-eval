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

# 4. Evaluator 映射表 (保持不变)
EVALUATOR_MAPPING = {
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

# ==========================================
# 🧠 提取 Metric
# ==========================================
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

# ==========================================
# 🏷️ Mode 推断
# ==========================================
def infer_mode_strict(filename):
    name = filename.replace(".py", "").lower()
    if "_gen" in name: return "gen"
    if "_ppl" in name: return "ppl"
    if "_mixed" in name: return "mixed"
    return None

# ==========================================
# 📂 智能分类推断 (V8 严格版)
# ==========================================

def infer_category_heuristics(name):
    """关键词兜底逻辑 (增强版)"""
    n = name.lower()
    # Math
    if any(x in n for x in ['math', 'gsm8k', 'arithmetic', 'theorem', 'algebra', 'calculus']): return "Math"
    # Code
    if any(x in n for x in ['code', 'mbpp', 'humaneval', 'python', 'java', 'sql']): return "Code"
    # Examination / Knowledge
    if any(x in n for x in ['mmlu', 'ceval', 'agieval', 'exam', 'bench', 'choice']): return "Knowledge"
    # NLP / Translation
    if any(x in n for x in ['translation', 'wmt', 'bleu', 'flores']): return "Translation"
    # Dialogue / Chat
    if any(x in n for x in ['chat', 'dialog', 'conversation']): return "Dialogue"
    # Safety
    if any(x in n for x in ['safety', 'toxic', 'bias', 'jailbreak']): return "Safety"
    # Reasoning
    if any(x in n for x in ['reason', 'logic', 'nli', 'qa', 'reading', 'arc', 'hellaswag']): return "Reasoning"
    # Long Context (🌟 新增，解决 lveval 问题)
    if any(x in n for x in ['long', 'context', 'needle', 'lveval', 'lv-eval', 'book']): return "Long Context"
    # Vision / Multimodal (以防万一)
    if any(x in n for x in ['vision', 'image', 'video', 'mmbench']): return "Multimodal"
    
    return None

def resolve_meta_and_category(file_path, oc_root):
    """
    V8 策略：非白名单即 Other
    """
    abs_datasets_dir = os.path.join(oc_root, "configs", "datasets")
    if not file_path.startswith(abs_datasets_dir):
        return os.path.basename(os.path.dirname(file_path)), "Other"
        
    rel_path = os.path.relpath(file_path, abs_datasets_dir)
    parts = rel_path.replace("\\", "/").split("/")
    
    # 1. 确定 Meta Name (依然是父文件夹名，这在 adv_glue_mnli 里是对的)
    meta_name = parts[-2] if len(parts) >= 2 else parts[0]
    
    # 2. 确定 Category
    category = "Other" # 默认值
    
    # 策略 A: 查官方映射表 (精确匹配 Meta Name)
    if meta_name.lower() in CAPABILITY_MAP:
        category = CAPABILITY_MAP[meta_name.lower()]
    
    # 策略 B: 查官方映射表 (模糊匹配)
    if category == "Other":
        for k, v in CAPABILITY_MAP.items():
            if k in meta_name.lower():
                category = v
                break
    
    # 策略 C: 关键词兜底 (Heuristics)
    if category == "Other":
        h_cat = infer_category_heuristics(meta_name)
        if h_cat:
            category = h_cat
            
    # ❌ 移除旧策略 D: "category = parts[0]"
    # 如果上面都没匹配到，那就是 "Other"，绝不使用文件夹名作为分类。

    return meta_name, category

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

    print(f"🚀 [V8-纯净分类版] 开始扫描: {target_dir}")
    print(f"   ℹ️  策略: 映射表 > 关键词 > Other (拒绝使用文件夹名作为分类)")
    
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

            # 2. Resolve Meta & Category (V8 Logic)
            meta_name, category = resolve_meta_and_category(file_path, oc_root)
            
            # 3. Metric
            metric = extract_metric_from_file(file_path)
            if not metric:
                metric = infer_metric_by_filename(filename)
            
            # 4. DB Operations
            # Meta
            meta = session.exec(select(DatasetMeta).where(DatasetMeta.name == meta_name)).first()
            if not meta:
                meta = DatasetMeta(name=meta_name, category=category, description="Official Dataset")
                session.add(meta)
                session.flush()
            else:
                # 🌟 强制修正 Category: 如果之前录入的是文件夹名(错的)或者Other，尝试更新为更准确的
                # 现在的逻辑是：除非匹配到明确的 map 或 heuristics，否则就是 Other
                # 所以我们相信这一次的判断
                if meta.category != category:
                     meta.category = category
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
                if existing.display_metric != metric or existing.mode != mode or existing.file_path != official_path:
                    existing.display_metric = metric
                    existing.mode = mode
                    existing.file_path = official_path
                    session.add(existing)
                    session.commit()
                continue
            
            db_config = DatasetConfig(
                meta_id=meta.id,
                config_name=config_name,
                mode=mode,
                file_path=official_path,
                display_metric=metric,
                reader_cfg="{}", infer_cfg="{}", metric_config="{}"
            )
            session.add(db_config)
            session.commit()
            success_count += 1
            
        except Exception:
            session.rollback()
            continue

    print(f"\n🎉 V8 录入完成！")
    print(f"   ✅ 成功录入: {success_count}")
    print(f"   🧹 过滤噪音: {skipped_count}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python scripts/seed_via_ast_v8.py <path>")
        sys.exit(1)
    
    from sqlmodel import SQLModel
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        process_and_save(session, sys.argv[1])