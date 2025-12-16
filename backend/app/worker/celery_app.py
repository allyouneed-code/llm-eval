# backend/app/worker/celery_app.py
from celery import Celery
import time

# 这里默认连接本地的 Redis，稍后我们用 Docker 启动 Redis
celery_app = Celery(
    "worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

celery_app.conf.broker_connection_retry_on_startup = True

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
)

@celery_app.task
def test_task(word: str):
    import time
    time.sleep(5) # 模拟耗时评测
    return f"Task completed: {word}"

@celery_app.task
def run_evaluation_task(task_id: int):
    """
    这是 Async Worker 真正干活的地方。
    它接收一个 task_id，然后去数据库查详情，最后启动显卡跑分。
    """
    print(f"👷 [Worker] 收到任务 ID: {task_id}，准备开始评测...")
    
    # --- 模拟耗时操作 (假装在跑 OpenCompass) ---
    time.sleep(2)
    print(f"🚀 [Worker] 正在加载模型 (模拟)...")
    time.sleep(2)
    print(f"📊 [Worker] 正在计算分数 (模拟)...")
    
    # 后面我们会在这里写读取数据库、更新进度、写回结果的代码
    return f"任务 {task_id} 完成！"