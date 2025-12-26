import sys
import os
import time
import requests

# 配置：请根据你的实际情况修改
API_BASE = "http://localhost:8000/api/v1"
# 使用一个真实的 API Key (例如 OpenAI 或 DeepSeek)，或者如果是 Mock 测试，随便填
TEST_API_KEY = os.getenv("OPENAI_API_KEY", "sk-OjjN3nmNeSZxEE8c2QJz985fdY3b9XegsKi7lTcl8z6Sr2de") 
TEST_MODEL_NAME = "gpt-3.5-turbo" 
 
def step(name):
    print(f"\n🔹 [STEP] {name}...")

def run_test():
    # 1. 创建/获取一个用于测试的模型 (API模式)
    # step("Create Model (API Type)")
    # model_payload = {
    #     "name": f"Test-Model-{int(time.time())}",
    #     "type": "api",
    #     "path": "https://api.chatanywhere.tech/v1", # 或者其他兼容接口
    #     "api_key": TEST_API_KEY,
    #     "param_size": "Unknown"
    # }
    # resp = requests.post(f"{API_BASE}/models/", json=model_payload)
    # if resp.status_code != 200:
    #     print(f"❌ Create model failed: {resp.text}")
    #     return
    # model_id = resp.json()["id"]
    # print(f"✅ Model Created: ID={model_id}")

    # 2. 上传/创建一个测试数据集
    step("Create Dataset")
    # 为了测试方便，我们假设数据库里已经有了初始化的数据集
    # 如果没有，我们需要先上传一个。这里尝试获取现有的。
    resp = requests.get(f"{API_BASE}/datasets/configs")
    configs = resp.json()
    print(configs)
    
    if not configs:
        print("⚠️ No dataset configs found. Please upload a dataset first.")
        # 这里可以扩展为自动上传一个 dummy jsonl
        return
    
    # 选第一个配置
    config_id = configs[0]["id"]
    print(f"✅ Using Dataset Config ID: {config_id} ({configs[0]['config_name']})")

    # 3. 创建评测任务
    step("Create Evaluation Task")
    task_payload = {
        "model_id": 1,
        "config_ids": [config_id],  # 使用列表
        "scheme_id": None
    }
    resp = requests.post(f"{API_BASE}/tasks/", json=task_payload)
    if resp.status_code != 200:
        print(f"❌ Create task failed: {resp.text}")
        return
    task_data = resp.json()
    task_id = task_data["id"]
    print(f"✅ Task Created: ID={task_id}")

    # 4. 轮询任务状态
    step("Wait for Task Completion")
    for _ in range(60): # 最多等 60秒
        resp = requests.get(f"{API_BASE}/tasks/{task_id}")
        task = resp.json()
        status = task["status"]
        progress = task["progress"]
        print(f"   >> Status: {status} | Progress: {progress}%")
        
        if status == "success":
            print("✅ Task Finished Successfully!")
            print("   Result Summary:", task.get("result_summary"))
            break
        elif status == "failed":
            print(f"❌ Task Failed. Error: {task.get('error_msg')}")
            break
        
        time.sleep(2)

if __name__ == "__main__":
    run_test()