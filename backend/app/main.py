from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel
from fastapi.staticfiles import StaticFiles #
import os

from app.core.database import engine

# === 修正部分 Start ===
from app.models.llm_model import LLMModel
# 导入新的模型类，不再是 Dataset
from app.models.dataset import DatasetMeta, DatasetConfig, EvaluationMetric 
from app.models.task import EvaluationTask
# === 修正部分 End ===

from app.api.v1 import models, datasets, tasks, schemes

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [Startup] 正在初始化数据库...")
    SQLModel.metadata.create_all(engine)
    print("✅ [Startup] 数据库表结构同步完成！")
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

app.include_router(models.router, prefix="/api/v1/models", tags=["Models"])
app.include_router(datasets.router, prefix="/api/v1/datasets", tags=["Datasets"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["Tasks"])
app.include_router(schemes.router, prefix="/api/v1/schemes", tags=["Schemes"])