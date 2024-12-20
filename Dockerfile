# 使用更轻量级的 Python 基础镜像
FROM python:3.13-slim AS builder

# 设置工作目录
WORKDIR /app

# 只复制依赖文件
COPY requirements.txt .

# 安装构建依赖和 Python 包
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        python3-dev \
        && \
    pip install --user -r requirements.txt && \
    rm -rf /var/lib/apt/lists/*

# 第二阶段：运行环境
FROM python:3.13-slim

# 定义构建参数
ARG API_KEY
ARG BASE_URL
ARG MODEL
ARG PROMPT
ARG FILE_DELETE_DELAY

# 设置环境变量
ENV API_KEY=${API_KEY} \
    BASE_URL=${BASE_URL} \
    MODEL=${MODEL} \
    PROMPT=${PROMPT} \
    FILE_DELETE_DELAY=${FILE_DELETE_DELAY} \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 只安装运行时必需的系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        && \
    rm -rf /var/lib/apt/lists/*

# 从 builder 阶段复制安装好的 Python 包
COPY --from=builder /root/.local /root/.local

# 确保 Python 包在 PATH 中
ENV PATH=/root/.local/bin:$PATH

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 使用 uvicorn 运行 FastAPI 应用
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]