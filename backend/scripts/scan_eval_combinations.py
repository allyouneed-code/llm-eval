import os
import sys
import glob
import ast
import collections
import json

# ==========================================
# 🕵️ 评估器 & 后处理组合扫描脚本 (V3 结构化版)
# ==========================================

def _extract_value(node):
    """提取 AST 节点的值，支持字符串、数字、变量名、属性调用"""
    if isinstance(node, ast.Constant): return node.value 
    if isinstance(node, ast.Str): return node.s
    if isinstance(node, ast.Num): return node.n
    if isinstance(node, ast.Name): return node.id
    if isinstance(node, ast.Attribute): return node.attr
    return None

def _extract_dict_info(node):
    """
    将 AST 的 Dict 节点或 dict() 调用解析为简单的 python 字典
    仅提取 type 和 options 等关键字段，递归深度 1 层
    """
    result = {}
    keys = []
    values = []

    # 1. 处理 dict(key=value)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'dict':
        keys = [kw.arg for kw in node.keywords]
        values = [kw.value for kw in node.keywords]
    
    # 2. 处理 {'key': value}
    elif isinstance(node, ast.Dict):
        for k in node.keys:
            keys.append(_extract_value(k))
        values = node.values

    # 提取内容
    for k, v in zip(keys, values):
        if not k: continue
        
        # 如果值是另一个 dict 调用 (nested dict)，递归提取 type
        val = _extract_value(v)
        if val is None: # 可能是嵌套结构 dict(type=...)
            sub_dict = _extract_dict_info(v)
            if sub_dict:
                result[k] = sub_dict
        else:
            result[k] = val
            
    return result

def get_eval_combinations(file_path):
    """
    扫描文件，寻找 eval_cfg 结构，返回 (evaluator, postprocessor) 组合列表
    """
    combinations = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                # 我们寻找的是一个字典（eval_cfg），它必须包含 'evaluator' 键
                # 它可以是 dict(evaluator=...) 或 {'evaluator': ...}
                
                node_dict = _extract_dict_info(node)
                
                # 核心判断逻辑：如果这个字典里有 'evaluator'，我们就认为它是 eval_cfg
                if node_dict and 'evaluator' in node_dict:
                    
                    # 1. 提取 Evaluator
                    eval_info = node_dict['evaluator']
                    eval_type = "Unknown"
                    if isinstance(eval_info, dict):
                        eval_type = eval_info.get('type', 'Unknown')
                    elif isinstance(eval_info, str):
                        eval_type = eval_info # 可能是变量名
                    
                    # 2. 提取 Post Processor
                    pp_info = node_dict.get('pred_postprocessor', None)
                    pp_data = None
                    
                    if pp_info:
                        if isinstance(pp_info, dict):
                            pp_data = {
                                'type': pp_info.get('type', 'Unknown'),
                                'options': pp_info.get('options', None)
                            }
                        elif isinstance(pp_info, str):
                            pp_data = {'type': pp_info, 'options': 'Variable'}
                    
                    combinations.append({
                        'evaluator': eval_type,
                        'post_processor': pp_data
                    })

    except Exception as e:
        # print(f"解析错误 {file_path}: {e}")
        pass
        
    return combinations

def main(oc_root):
    target_dir = os.path.join(oc_root, "configs", "datasets")
    if not os.path.exists(target_dir):
        if "datasets" in oc_root:
            target_dir = oc_root
        else:
            print(f"❌ 错误：找不到 configs/datasets 路径 -> {target_dir}")
            return

    print(f"🚀 [V3] 开始扫描 Evaluator + PostProcess 组合: {target_dir}")
    py_files = glob.glob(os.path.join(target_dir, "**/*.py"), recursive=True)
    
    # 使用字符串作为 key 来计数，方便去重
    combo_counter = collections.Counter()
    
    print(f"📂 发现 {len(py_files)} 个配置文件，正在分析...")
    
    for i, file_path in enumerate(py_files):
        if "__init__.py" in file_path: continue
        
        found_combos = get_eval_combinations(file_path)
        
        for combo in found_combos:
            # 序列化成 string 以便 Hash 计数
            key = json.dumps(combo, sort_keys=True)
            combo_counter[key] += 1

    print("\n" + "="*50)
    print("📊 扫描结果 (Top Combinations)")
    print("="*50)
    
    results = []
    
    for json_str, count in combo_counter.most_common():
        data = json.loads(json_str)
        data['count'] = count
        results.append(data)
        
        # 打印到控制台
        eval_t = data['evaluator']
        pp_t = data['post_processor']['type'] if data['post_processor'] else "None"
        pp_opt = f"(opt: {data['post_processor']['options']})" if data['post_processor'] and data['post_processor'].get('options') else ""
        
        print(f"[{count:<3}] Eval: {eval_t:<25} | PP: {pp_t} {pp_opt}")

    # 保存到 JSON 文件
    output_file = "evaluator_combinations.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    print("="*50)
    print(f"✅ 结果已保存至: {output_file}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python scan_eval_combinations.py <opencompass_path>")
    else:
        main(sys.argv[1])