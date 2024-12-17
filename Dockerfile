# 使用 Python 官方镜像作为基础镜像
FROM python:3.13-alpine

USER root

# 定义构建参数
ARG API_KEY
ARG BASE_URL
ARG MODEL
ARG PROMPT
ARG FILE_DELETE_DELAY

# 设置环境变量
ENV API_KEY=${API_KEY}
ENV BASE_URL=${BASE_URL}
ENV MODEL=${MODEL}
ENV PROMPT=${PROMPT}
ENV FILE_DELETE_DELAY=${FILE_DELETE_DELAY}
ENV PYTHONUNBUFFERED=1

# Runtime dependency
RUN apk add --no-cache ffmpeg

# 设置工作目录
WORKDIR /app

# 复制项目文件到容器中
COPY . .

RUN pip3 install -r requirements.txt

# 暴露端口（修改为 8000)
EXPOSE 8000

# 使用 uvicorn 运行 FastAPI 应用，端口改为 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"] 