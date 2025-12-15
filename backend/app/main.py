# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="OpenCompass Platform API", version="0.1.0")

# 配置 CORS (允许前端跨域访问)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 生产环境请改为前端具体地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to OpenCompass Evaluation System"}

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "backend"}