import os
from celery import Celery
from sqlmodel import Session
from app.core.database import engine
# 导入 Service
from app.services.task_service import TaskService

REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)
celery_app.conf.broker_connection_retry_on_startup = True

@celery_app.task
def run_evaluation_task(task_id: int):
    print(f"🚀 [Worker] 接收到任务 {task_id}")
    
    # 为 Worker 独立的线程创建数据库会话
    with Session(engine) as session:
        # 初始化 Service
        service = TaskService(session)
        
        # 执行核心逻辑
        try:
            result = service.run_evaluation_logic(task_id)
            return result
        except Exception as e:
            print(f"❌ [Worker] 任务 {task_id} 失败: {e}")
            # 这里可以扩展：在 Service 中增加 mark_task_failed 方法来更新数据库状态
            raise e