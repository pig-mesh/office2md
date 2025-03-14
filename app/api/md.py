import os
import time
import asyncio
import logging
from fastapi import APIRouter, File, UploadFile, status, HTTPException, Form
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
    base_url: Optional[str] = Form(None, description="自定义OpenAI API基础URL"),
    api_key: Optional[str] = Form(None, description="自定义OpenAI API密钥"),
    model: Optional[str] = Form(None, description="自定义OpenAI模型名称"),
    prompt: Optional[str] = Form(None, description="自定义提示词"),
    concurrent_limit: Optional[int] = Form(None, description="自定义PDF处理并发限制"),
    batch_size: Optional[int] = Form(None, description="自定义PDF批处理大小"),
    delete_delay: Optional[int] = Form(None, description="自定义文件删除延迟时间(秒)")
):
    timestamp = int(time.time())
    file_extension = os.path.splitext(file.filename)[1].lower()
    new_filename = f"{timestamp}{file_extension}"
    
    content = await file.read()
    file_path = await save_upload_file(content, new_filename)
    
    # 使用用户提供的参数或默认值
    used_base_url = base_url or BASE_URL
    used_api_key = api_key or API_KEY
    used_model = model or MODEL
    used_prompt = prompt or MLM_PROMPT
    used_concurrent_limit = concurrent_limit or PDF_CONCURRENT_LIMIT
    used_batch_size = batch_size or PDF_BATCH_SIZE
    used_delete_delay = delete_delay or FILE_DELETE_DELAY
    
    # 如果用户提供了自定义参数，创建新的OpenAI客户端
    current_client = client
    if base_url or api_key:
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