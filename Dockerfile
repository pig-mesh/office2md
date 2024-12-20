# 使用 Python 官方镜像作为基础镜像
FROM python:3.13

USER root

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

# 设置工作目录
WORKDIR /app

# 复制项目文件到容器中
COPY . .

# Runtime dependency
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    pip3 install -r requirements.txt

# 暴露端口（修改为 8000)
EXPOSE 8000

# 使用 uvicorn 运行 FastAPI 应用，端口改为 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"] 