import os
import sys
import glob
import json
import re

# ==========================================
# 1. 严格过滤逻辑 (1:1 复刻 seed_official_datasets.py)
# ==========================================

VERSION_PATTERN = re.compile(r'_[0-9a-f]{6}\.py$')

def infer_mode_strict(filename):
    """
    Seed 脚本同款逻辑：必须包含特定后缀才算有效配置
    """
    name = filename.replace(".py", "").lower()
    if "_gen" in name: return "gen"
    if "_ppl" in name: return "ppl"
    if "_mixed" in name: return "mixed"
    return None

def is_valid_config(file_path):
    """
    判断文件是否应该被统计
    """
    filename = os.path.basename(file_path)
    
    # 1. 基础黑名单
    if filename == "__init__.py": return False
    if filename.endswith("_settings.py") or filename.endswith("_base.py") or filename.endswith("_common.py"):
        return False
        
    # 2. 版本号过滤 (忽略带hash的文件)
    if VERSION_PATTERN.search(filename):
        return False
        
    # 3. 严格模式检查 (必须有 _gen / _ppl)
    if not infer_mode_strict(filename):
        return False
        
    return True

# ==========================================
# 2. 命名解析 & 匹配逻辑 (保持优化版)
# ==========================================

MANUAL_MAPPING = {
    "mmlu_pro": "mmlu-pro",       
    "mmlu_cf": "mmlu",            
    "lveval": "lv-eval",          
    "supergpqa": "gpqa",          
    # "needlebench_4k": "needlebench", 
}

def resolve_meta_name(file_path, oc_root):
    abs_datasets_dir = os.path.join(oc_root, "configs", "datasets")
    if not file_path.startswith(abs_datasets_dir):
        parts = file_path.replace("\\", "/").split("/")
        if "datasets" in parts:
            idx = parts.index("datasets")
            if idx + 2 < len(parts): return parts[idx+1]
        return os.path.basename(os.path.dirname(file_path))
    rel_path = os.path.relpath(file_path, abs_datasets_dir)
    parts = rel_path.replace("\\", "/").split("/")
    return parts[-2] if len(parts) >= 2 else parts[0]

def normalize_key(text):
    if not text: return ""
    return re.sub(r'[-_.\s]', '', str(text).lower())

def find_best_match(target_name, inv):
    t_name = target_name.lower().strip()
    norm_name = normalize_key(t_name)
    
    # 策略 0: 人工映射
    if t_name in MANUAL_MAPPING:
        key = MANUAL_MAPPING[t_name]
        if key in inv["by_folder"]: return inv["by_folder"][key], "Manual (Folder)"
        if key in inv["by_filename"]: return inv["by_filename"][key], "Manual (File)"

    # 策略 1: 精确匹配
    if t_name in inv["by_folder"]: return inv["by_folder"][t_name], "Exact Folder"
    if t_name in inv["by_filename"]: return inv["by_filename"][t_name], "Exact File"
    
    # 策略 2: 前缀/包含匹配
    best_cand = None
    best_len = 0
    for folder_key in inv["by_folder"]:
        if len(folder_key) < 3: continue 
        if t_name.startswith(folder_key) or norm_name.startswith(normalize_key(folder_key)):
            if len(folder_key) > best_len:
                best_len = len(folder_key)
                best_cand = folder_key
    if best_cand:
        return inv["by_folder"][best_cand], f"Prefix Match ({best_cand})"

    # 策略 3: 标准化匹配
    for folder_key in inv["by_folder"]:
        if normalize_key(folder_key) == norm_name:
            return inv["by_folder"][folder_key], "Normalized Folder"

    # 策略 4: 单词拆分
    parts = re.split(r'[-_]', t_name)
    if len(parts) > 1:
        first = parts[0]
        if len(first) > 3 and first in inv["by_folder"]:
            return inv["by_folder"][first], f"Split Match ({first})"

    return None, None

# ==========================================
# 3. 主程序
# ==========================================
def run_strict_preview(oc_root, inventory_path="local_inventory_v2.json"):
    if not os.path.exists(inventory_path):
        print(f"❌ 未找到 {inventory_path}")
        return
    with open(inventory_path, 'r', encoding='utf-8') as f:
        inv = json.load(f)

    target_dir = os.path.join(oc_root, "configs", "datasets")
    print(f"🚀 严格扫描 Configs: {target_dir} ...")
    
    py_files = glob.glob(os.path.join(target_dir, "**/*.py"), recursive=True)
    
    # 🌟 应用严格过滤
    valid_metas = set()
    ignored_count = 0
    
    for f in py_files:
        if is_valid_config(f):
            name = resolve_meta_name(f, oc_root)
            if name: valid_metas.add(name)
        else:
            ignored_count += 1
            
    print(f"📋 统计结果:")
    print(f"   - 扫描文件数: {len(py_files)}")
    print(f"   - 有效数据集: {len(valid_metas)} (应接近 250)")
    print(f"   - 过滤无效项: {ignored_count}")

    print("\n🔍 开始匹配...")
    
    report = {
        "summary": {"total_valid_metas": len(valid_metas), "matched": 0, "total_rows": 0},
        "details": [],
        "unmatched": []
    }
    
    for meta_name in sorted(list(valid_metas)):
        files, strategy = find_best_match(meta_name, inv)
        
        if files:
            unique_paths = set()
            count = 0
            for f in files:
                if f['path'] not in unique_paths:
                    unique_paths.add(f['path'])
                    count += f['count']
            
            report["summary"]["matched"] += 1
            report["summary"]["total_rows"] += count
            report["details"].append({
                "name": meta_name,
                "strategy": strategy,
                "count": count
            })
            
            # 仅打印大额匹配
            if count > 1000:
                print(f"   ✅ {meta_name:<20} -> {count:>7} 行 | {strategy}")
        else:
            report["unmatched"].append(meta_name)

    out_file = "strict_match_report.json"
    with open(out_file, "w", encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n" + "="*50)
    print(f"📊 严格报告已生成: {out_file}")
    print(f"   - 匹配进度: {report['summary']['matched']} / {len(valid_metas)}")
    print(f"   - 预计总题量: {report['summary']['total_rows']:,}")
    print("="*50)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python backend/scripts/5_strict_preview.py <OpenCompass根目录>")
    else:
        run_strict_preview(sys.argv[1])