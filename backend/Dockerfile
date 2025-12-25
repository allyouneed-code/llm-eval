# backend/Dockerfile

# 1. 使用包含 CUDA 12.1 和 PyTorch 2.1.2 的官方镜像作为基础
# "devel" 版本包含了 nvcc 编译器，这对安装 flash-attn 等库是必须的
FROM pytorch/pytorch:2.1.2-cuda12.1-cudnn8-devel

# 设置工作目录
WORKDIR /app

# 2. 环境变量设置
# 防止 apt 安装时出现交互式弹窗
ENV DEBIAN_FRONTEND=noninteractive
# 确保使用国内源或解决一些网络超时问题（可选，视网络情况而定）
ENV PIP_DEFAULT_TIMEOUT=100

# 3. 安装系统级依赖
# netcat-openbsd: 用于启动脚本中的数据库连接检测
# git: 用于安装某些 GitHub 源码包
RUN apt-get update && apt-get install -y \
    git \
    netcat-openbsd \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 4. 复制依赖文件
COPY requirements.txt .

# 5. 安装 Python 依赖
# 注意：底座镜像已经自带了 pytorch，requirements.txt 里不应再包含 torch
RUN pip install --no-cache-dir -r requirements.txt

# 6. 复制项目代码
COPY . .

# 7. 暴露端口
EXPOSE 8000

# 8. 启动命令
# 生产环境建议结合 gunicorn 或 shell 脚本使用，这里保持开发模式
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]