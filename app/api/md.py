import os
import time
import asyncio
import logging
import json
from fastapi import APIRouter, File, UploadFile, status, HTTPException, Form, Body, Depends
from typing import Dict, Optional
from openai import OpenAI
from markitdown import MarkItDown
from app.utils.pdf_utils import PDFProcessor
from pydantic import BaseModel

# 配置日志
logger = logging.getLogger(__name__)


from app.config import (
    API_KEY,
    BASE_URL,
    MODEL,
    FILE_DELETE_DELAY,
    MLM_PROMPT,
    PDF_CONCURRENT_LIMIT,
    PDF_BATCH_SIZE
)
from app.utils.file_utils import save_upload_file, delete_files

router = APIRouter()

client = OpenAI(
    base_url=BASE_URL,
    api_key=API_KEY
)

class MarkdownResponse(BaseModel):
    success: bool
    message: str
    text: Optional[str] = None

class AiMarkitdownDTO(BaseModel):
    """AI Markitdown服务的配置参数"""
    base_url: Optional[str] = ""
    """自定义OpenAI API基础URL，为空时使用系统配置"""
    
    api_key: Optional[str] = ""
    """自定义OpenAI API密钥，为空时使用系统配置"""
    
    model: Optional[str] = ""
    """自定义OpenAI模型名称，为空时使用系统配置"""
    
    prompt: Optional[str] = ""
    """自定义提示词，为空时使用系统配置"""
    
    concurrent_limit: Optional[int] = 5
    """自定义PDF处理并发限制，控制PDF处理时的并发数量"""
    
    batch_size: Optional[int] = 10
    """自定义PDF批处理大小，控制PDF处理时的批量大小"""
    
    delete_delay: Optional[int] = 300
    """自定义文件删除延迟时间(秒)，控制临时文件的保留时间"""

async def parse_request_json(request: Optional[str] = Form("", description="JSON格式的配置参数，包含API密钥、模型等设置")) -> Optional[AiMarkitdownDTO]:
    """从表单字段解析JSON对象"""
    if not request:
        return None
    try:
        data = json.loads(request)
        return AiMarkitdownDTO(**data)
    except Exception as e:
        logger.error(f"Error parsing request JSON: {e}")
        return None

@router.post("/upload", 
    response_model=MarkdownResponse,
    status_code=status.HTTP_200_OK,
    summary="上传文件",
    description="上传图片或PDF文件并提取其中的文本内容",
    responses={
        200: {
            "description": "成功提取文本",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Text extracted successfully",
                        "text": "提取的文本内容"
                    }
                }
            }
        }
    }
)
async def upload_file(
    file: UploadFile = File(..., description="要上传的文件，支持常见图片格式和PDF文件"),
    request: Optional[AiMarkitdownDTO] = Depends(parse_request_json)
):
    # 创建一个默认的DTO对象，如果request为None
    if request is None:
        request = AiMarkitdownDTO()
    
    # 记录请求参数（安全处理API密钥）
    masked_api_key = "None" if not request.api_key else f"****{request.api_key[-4:]}" if len(request.api_key) > 4 else "****"
    logger.debug(f"Received request with parameters: base_url={request.base_url}, api_key={masked_api_key}, model={request.model}, prompt_provided={request.prompt != ''}, concurrent_limit={request.concurrent_limit}, batch_size={request.batch_size}, delete_delay={request.delete_delay}")
    
    timestamp = int(time.time())
    file_extension = os.path.splitext(file.filename)[1].lower()
    new_filename = f"{timestamp}{file_extension}"
    
    content = await file.read()
    file_path = await save_upload_file(content, new_filename)
    
    # 使用用户提供的参数或默认值
    used_base_url = request.base_url or BASE_URL
    used_api_key = request.api_key or API_KEY
    used_model = request.model or MODEL
    used_prompt = request.prompt or MLM_PROMPT
    used_concurrent_limit = request.concurrent_limit or PDF_CONCURRENT_LIMIT
    used_batch_size = request.batch_size or PDF_BATCH_SIZE
    used_delete_delay = request.delete_delay or FILE_DELETE_DELAY
    
    # 处理API密钥显示，只显示最后4位
    masked_api_key = "None" if not used_api_key else f"****{used_api_key[-4:]}" if len(used_api_key) > 4 else "****"
    
    logger.info(f"Processing with parameters: base_url={used_base_url}, api_key={masked_api_key}, model={used_model}, prompt_provided={used_prompt is not None}, concurrent_limit={used_concurrent_limit}, batch_size={used_batch_size}, delete_delay={used_delete_delay}")

    # 如果用户提供了自定义参数，创建新的OpenAI客户端
    current_client = client
    if request.base_url or request.api_key:
        current_client = OpenAI(
            base_url=used_base_url,
            api_key=used_api_key
        )
    
    # 使用当前客户端创建MarkItDown实例
    markitdown = MarkItDown(llm_client=current_client, llm_model=used_model)
    
    result = markitdown.convert(file_path, llm_prompt=used_prompt)
    
    # 如果是PDF文件且未提取到文本，则尝试其他方法
    if file_extension == '.pdf' and not result.text_content:
        async with PDFProcessor(concurrent_limit=used_concurrent_limit) as processor:
            success, text = await processor.extract_text(
                file_path,
                used_base_url,
                used_api_key,
                used_model,
                used_prompt,
                batch_size=used_batch_size,
            )
            if success:
                result.text_content = text
    
    # 创建异步任务删除临时文件
    asyncio.create_task(delete_files(file_path, "", used_delete_delay))
    
    return MarkdownResponse(
        success=True,
        message="Text extracted successfully",
        text=result.text_content or ""
    )