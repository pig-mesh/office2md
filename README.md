# Image Text Extraction Service

这是一个基于 FastAPI 的图片文本提取服务，支持智谱 AI 的 GLM-4V 模型和阿里云百炼平台的 Qwen-VL-Max 模型进行图片文本识别。

## 环境变量说明

服务支持以下环境变量配置：

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| API_KEY | AI 平台的 API 密钥 | XXXX |
| BASE_URL | AI 平台的 API 基础 URL | https://open.bigmodel.cn/api/paas/v4 |
| MODEL | 使用的模型名称 | glm-4v-flash |
| DELETE_DELAY | 临时文件删除延迟（秒） | 600 |
| PROMPT | 文本提取提示词 | 提取图片中全部的文本，不需要任何推理和总结，只需要原文 |

### 支持的模型配置

#### 智谱 AI
- MODEL=glm-4v-flash
- BASE_URL=https://open.bigmodel.cn/api/paas/v4

#### 阿里云百炼
- MODEL=qwen-vl-max
- BASE_URL=https://dashscope.aliyuncs.com/api/v1

## Docker 使用说明

### 1. 快速使用（默认使用智谱 AI）

```bash
docker run -p 8000:8000 pig4cloud/markitdown
```

### 2. 使用阿里云百炼平台

```bash
docker run -d \
  -p 8000:8000 \
  -e API_KEY=your_aliyun_api_key \
  -e MODEL=qwen-vl-max \
  -e BASE_URL=https://dashscope.aliyuncs.com/api/v1 \
  pig4cloud/markitdown
```

## API 接口

### 上传图片并提取文本

**Endpoint:** POST /upload/

**请求格式:** multipart/form-data

**参数:**
- file: 图片文件

**响应示例:**
```json
{
    "new_filename": "1679012345.jpg",
    "content": "提取的文本内容"
}
```

## 注意事项

1. 使用前请确保已获取相应平台的 API 密钥
2. 智谱 AI 和阿里云百炼平台的接口略有不同，请确保使用正确的配置
3. 上传的图片文件会在处理后自动删除（默认10分钟）
4. 服务默认监听 8000 端口


