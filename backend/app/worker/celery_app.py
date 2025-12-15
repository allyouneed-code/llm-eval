# backend/app/worker/celery_app.py
from celery import Celery

# 这里默认连接本地的 Redis，稍后我们用 Docker 启动 Redis
celery_app = Celery(
    "worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

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