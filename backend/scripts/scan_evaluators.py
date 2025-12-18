import os
import sys
import glob
import ast
import collections

# ==========================================
# 🕵️ 评估器扫描脚本 (暴力增强版)
# ==========================================

def get_potential_evaluators(file_path):
    """
    不关心嵌套结构，只要发现 type=xxx，且 xxx 看起来像评估器，就抓出来
    """
    types = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # 1. 尝试 AST 解析 (处理结构化数据)
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    # 检查所有关键字参数: type=...
                    if isinstance(node, ast.keyword) and node.arg == 'type':
                        val = _extract_value(node.value)
                        if _is_likely_evaluator(val):
                            types.append(val)
                    
                    # 检查所有字典定义: {'type': ...}
                    elif isinstance(node, ast.Dict):
                        for key, value in zip(node.keys, node.values):
                            k_str = _extract_value(key)
                            if k_str == 'type':
                                val = _extract_value(value)
                                if _is_likely_evaluator(val):
                                    types.append(val)
            except:
                # 如果 AST 解析挂了 (比如有语法错误)，回退到简单的文本匹配
                pass

    except Exception:
        pass
    return types

def _extract_value(node):
    """提取 AST 节点的值，支持字符串和变量名"""
    # 1. 字符串 'AccEvaluator'
    if isinstance(node, ast.Constant): return node.value 
    if isinstance(node, ast.Str): return node.s
    
    # 2. 变量名 AccEvaluator (这是之前漏掉的关键！)
    if isinstance(node, ast.Name): return node.id
    
    # 3. 属性调用 mmengine.evaluator.AccEvaluator
    if isinstance(node, ast.Attribute): return node.attr
    
    return None

def _is_likely_evaluator(name):
    """
    简单的过滤器，防止把 Dataset 或 Model 的类名抓进来
    """
    if not name or not isinstance(name, str):
        return False
    
    # 规则 1: 名字里包含 Evaluator (最准)
    if "Evaluator" in name:
        return True
    
    # 规则 2: 常见的简写指标
    whitelist = [
        "Accuracy", "Acc", "BLEU", "Bleu", "Rouge", "ROUGE", 
        "ExactMatch", "EM", "PassAtK", "F1", "F1Score"
    ]
    if name in whitelist:
        return True
        
    return False

def main(oc_root):
    target_dir = os.path.join(oc_root, "configs", "datasets")
    if not os.path.exists(target_dir):
        if "datasets" in oc_root:
            target_dir = oc_root
        else:
            print(f"❌ 错误：找不到 configs/datasets 路径 -> {target_dir}")
            return

    print(f"🚀 [V2] 开始暴力扫描评估器: {target_dir}")
    py_files = glob.glob(os.path.join(target_dir, "**/*.py"), recursive=True)
    
    counter = collections.Counter()
    
    for i, file_path in enumerate(py_files):
        if i > 0 and i % 200 == 0: print(f"   ...扫描进度 {i}/{len(py_files)}")
        if "__init__.py" in file_path: continue
        
        found_types = get_potential_evaluators(file_path)
        counter.update(found_types)

    print("\n" + "="*50)
    print("📊 扫描结果 (Count | Evaluator Class)")
    print("="*50)
    
    # 打印结果
    if not counter:
        print("❌ 还是没找到？这不科学。请检查路径是否正确。")
    else:
        for eval_type, count in counter.most_common():
            print(f"{count:<5} : {eval_type}")
        
    print("="*50)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python backend/scripts/scan_evaluators_v2.py <opencompass_path>")
        sys.exit(1)
    
    main(sys.argv[1])