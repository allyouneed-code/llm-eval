import json
import csv
import os
# 引入上面的 smart_count_rows 函数 (实际使用时请合并到同一个文件)
# from utils import smart_count_rows 

DATA_ROOT = "D:\mydesk\study\opencompass\opencompass\data"

def scan_files_v2():
    inventory = {
        "by_filename": {},      # key: filename_stem -> list of files
        "by_folder": {},        # key: folder_name -> list of files
        "all_files": []         # flat list
    }
    
    print(f"🚀 开始深度扫描: {DATA_ROOT} ...")
    
    for root, dirs, files in os.walk(DATA_ROOT):
        folder_name = os.path.basename(root).lower()
        
        # 初始化文件夹索引
        if folder_name not in inventory["by_folder"]:
            inventory["by_folder"][folder_name] = []
            
        for file in files:
            if file.lower().endswith(('.json', '.jsonl', '.csv', '.txt')):
                full_path = os.path.join(root, file)
                row_count = smart_count_rows(full_path) # 使用上面的智能计数
                
                # 提取关键元数据
                filename_stem = os.path.splitext(file)[0].lower() # 去后缀
                
                file_entry = {
                    "path": full_path,
                    "name": file,
                    "stem": filename_stem,
                    "folder": folder_name,
                    "count": row_count
                }
                
                # 1. 存入总表
                inventory["all_files"].append(file_entry)
                
                # 2. 按文件夹归档 (解决 MyDataset/train.json 问题)
                inventory["by_folder"][folder_name].append(file_entry)
                
                # 3. 按文件名前缀归档 (解决 gaokao-bio.json 问题)
                # 我们把 "gaokao-biology" 拆解，把 "gaokao" 也作为索引键
                if '-' in filename_stem:
                    prefix = filename_stem.split('-')[0]
                    if prefix not in inventory["by_filename"]:
                        inventory["by_filename"][prefix] = []
                    inventory["by_filename"][prefix].append(file_entry)
                
                # 同时也存完整文件名
                if filename_stem not in inventory["by_filename"]:
                    inventory["by_filename"][filename_stem] = []
                inventory["by_filename"][filename_stem].append(file_entry)

    # 保存
    with open("local_inventory_v2.json", "w", encoding='utf-8') as f:
        json.dump(inventory, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 扫描完成！索引已构建。")

def smart_count_rows(filepath):
    """
    智能计算行数：兼容伪装成 .json 的 JSONL 文件
    """
    ext = os.path.splitext(filepath)[1].lower()
    count = 0
    
    try:
        # 🟢 Case 1: 明确的 JSONL
        if ext == '.jsonl':
            with open(filepath, 'rb') as f:
                for _ in f: count += 1
                
        # 🟡 Case 2: .json (可能是标准 JSON，也可能是 JSONL)
        elif ext == '.json':
            try:
                # 1. 先尝试按标准 JSON 读取
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    data = json.load(f)
                    
                # 如果成功，计算长度
                if isinstance(data, list):
                    count = len(data)
                elif isinstance(data, dict):
                    # 如果是字典，检查是否有常见的列表字段 (如 'data', 'rows')
                    # 否则算作 1 条数据
                    count = 1
                    for k in ['data', 'items', 'rows', 'examples']:
                        if k in data and isinstance(data[k], list):
                            count = len(data[k])
                            break
                            
            except json.JSONDecodeError:
                # 🌟 关键修复：如果解析失败（通常是 Extra data），说明它是 JSONL
                # 重新以二进制按行读取
                with open(filepath, 'rb') as f:
                    count = 0
                    for _ in f: count += 1

        # 🔵 Case 3: CSV/TSV
        elif ext in ['.csv', '.tsv']:
            with open(filepath, 'rb') as f:
                # 二进制读行数通常比 csv 模块快且容错率高
                lines = sum(1 for _ in f)
                count = max(0, lines - 1) # 减去表头
        
        # ⚪ Case 4: TXT
        elif ext == '.txt':
            with open(filepath, 'rb') as f:
                for _ in f: count += 1
                
    except Exception as e:
        print(f"⚠️ 无法读取 {filepath}: {e}")
        # 出错时返回 0，不中断程序
        return 0
        
    return count

if __name__ == "__main__":
    scan_files_v2()