from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, Session, select  # <--- [修改] 引入 Session 和 select
from fastapi.staticfiles import StaticFiles
import os

from app.core.database import engine

# === 模型导入 Start ===
from app.models.llm_model import LLMModel
from app.models.dataset import DatasetMeta, DatasetConfig, EvaluationMetric 
from app.models.task import EvaluationTask
from app.models.user import User 
from app.models.dict import DictItem
# === 模型导入 End ===

# [新增] 引入哈希工具
from app.utils.security_lite import hash_password 

# [修改] 引入 auth 模块
from app.api.v1 import models, datasets, tasks, schemes, auth, dicts

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [Startup] 正在初始化数据库...")
    # 1. 创建表结构
    SQLModel.metadata.create_all(engine)
    
    # 2. [新增] 预注册管理员账号
    try:
        with Session(engine) as session:
            # 查询是否存在用户名为 admin 的用户
            statement = select(User).where(User.username == "admin")
            admin_user = session.exec(statement).first()
            
            if not admin_user:
                print("👤 [Startup] 未检测到管理员，正在创建默认账户 (admin)...")
                new_admin = User(
                    username="admin",
                    # 这里设置你的默认密码，例如 'admin123'
                    hashed_password=hash_password("admin123"), 
                    role="admin",
                    is_active=True
                )
                session.add(new_admin)
                session.commit()
                print("✅ [Startup] 管理员创建成功！账号: admin / 密码: admin123")
            else:
                print("ℹ️ [Startup] 管理员账号已存在，跳过创建。")
    except Exception as e:
        print(f"❌ [Startup] 初始化管理员失败: {e}")

    print("✅ [Startup] 系统启动准备就绪！")
    yield
    print("👋 [Shutdown] 应用服务已关闭")

app = FastAPI(
    title="LLM Eval Platform",
    description="基于 OpenCompass 的模型评测平台",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to LLM Eval Platform API"}

@app.get("/health")
def health_check():
    return {"status": "ok", "database": "connected"}

os.makedirs("data/datasets", exist_ok=True)
app.mount("/static", StaticFiles(directory="data/datasets"), name="static")

# === 注册路由 ===
app.include_router(models.router, prefix="/api/v1/models", tags=["Models"])
app.include_router(datasets.router, prefix="/api/v1/datasets", tags=["Datasets"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["Tasks"])
app.include_router(schemes.router, prefix="/api/v1/schemes", tags=["Schemes"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(dicts.router, prefix="/api/v1/dicts", tags=["Dicts"])