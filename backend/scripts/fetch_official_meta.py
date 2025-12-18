import requests
import json
import os
from bs4 import BeautifulSoup

# OpenCompass 官方文档的数据集统计页面
# 如果你有特定的本地 HTML 文件，也可以改用 open() 读取
TARGET_URL = "https://doc.opencompass.org.cn/dataset_statistics.html"
# 备用英文版: "https://opencompass.readthedocs.io/en/latest/dataset_statistics.html"

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "dataset_capabilities.json")

def fetch_and_parse():
    print(f"🕵️  正在抓取页面: {TARGET_URL} ...")
    
    try:
        # 1. 获取网页内容
        resp = requests.get(TARGET_URL, timeout=10)
        resp.raise_for_status()
        html_content = resp.text
        
        # 2. 解析 HTML
        soup = BeautifulSoup(html_content, "html.parser")
        
        # 3. 寻找包含数据集列表的表格
        # 通常是页面中含有 "Supported Dataset List" 标题下的第一个表格
        mapping = {}
        
        # 查找所有表格，遍历寻找包含 "Category" 表头的那个
        tables = soup.find_all("table")
        target_table = None
        
        for table in tables:
            headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
            if "name" in headers and "category" in headers:
                target_table = table
                break
        
        if not target_table:
            print("❌ 未找到包含 Name 和 Category 的表格，页面结构可能已变更。")
            return

        # 4. 提取数据
        # 假设第一列是 Name，第二列是 Category (根据文档结构)
        rows = target_table.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 2:
                # 提取数据集名称 (移除多余空格)
                name = cols[0].get_text(strip=True)
                category = cols[1].get_text(strip=True)
                
                # 清洗 Category (有些可能包含斜杠 "Knowledge / Law")
                # 我们只取第一个主要分类，或者保留原样
                main_category = category.split('/')[0].strip()
                
                # 建立映射: 名字 -> 能力
                # 同时存小写键，方便后续不区分大小写匹配
                mapping[name.lower()] = main_category
                
                # 部分数据集可能有别名，这里可以根据需要做特殊处理
        
        print(f"✅ 解析成功！共获取 {len(mapping)} 个数据集的分类信息。")
        
        # 5. 保存结果
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
        print(f"💾 已保存至: {OUTPUT_FILE}")
        
    except Exception as e:
        print(f"❌ 发生错误: {e}")

if __name__ == "__main__":
    # 需要安装依赖: pip install requests beautifulsoup4
    fetch_and_parse()