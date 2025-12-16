from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, create_engine

from app.core.database import engine

from app.models.llm_model import LLMModel
from app.models.dataset import Dataset
from app.models.task import EvaluationTask

from app.api.v1 import models, datasets, tasks
# ==========================================
# 生命周期管理 (Lifespan)
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- 启动时执行 ---
    print("🚀 [Startup] 正在初始化数据库...")
    
    # 这一步是魔法所在：它会去数据库里看有没有表，没有就自动 Create Table
    SQLModel.metadata.create_all(engine)
    
    print("✅ [Startup] 数据库表结构同步完成！")
    
    yield # 应用运行中...
    
    # --- 关闭时执行 ---
    print("👋 [Shutdown] 应用服务已关闭")

# ==========================================
# 初始化 App
# ==========================================
app = FastAPI(
    title="LLM Eval Platform",
    description="基于 OpenCompass 的模型评测平台",
    version="0.1.0",
    lifespan=lifespan # 绑定上面的生命周期
)

# 配置 CORS (允许前端跨域访问)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 允许任何来源，生产环境请改为具体前端地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 基础路由
# ==========================================
@app.get("/")
def read_root():
    return {
        "message": "Welcome to LLM Eval Platform API", 
        "docs_url": "http://localhost:8000/docs"
    }

@app.get("/health")
def health_check():
    return {"status": "ok", "database": "connected"}

# ==========================================
# 注册路由 (Router Registration)
# ==========================================
# 这样 /api/v1/models 下的所有接口都生效了
app.include_router(models.router, prefix="/api/v1/models", tags=["Models"])
app.include_router(datasets.router, prefix="/api/v1/datasets", tags=["Datasets"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["Tasks"])