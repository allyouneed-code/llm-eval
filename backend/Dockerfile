# backend/Dockerfile
FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖（如果是 MySQL 可能需要一些 build-essential，但 pymysql 通常不需要）
RUN apt-get update && apt-get install -y netcat-openbsd && rm -rf /var/lib/apt/lists/*

# 复制依赖并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制所有代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动脚本 (等待数据库启动后再运行应用)
# 这里仅作示例，生产环境建议用 shell 脚本做 wait-for-it
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]