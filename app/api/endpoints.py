import os
import time
import asyncio
import logging
from fastapi import APIRouter, File, UploadFile, status
from typing import Dict
from openai import OpenAI
from markitdown import MarkItDown
from app.utils.pdf_utils import PDFProcessor

# 配置日志
logger = logging.getLogger(__name__)


from app.config import (
    API_KEY,
    BASE_URL,
    MODEL,
    FILE_DELETE_DELAY,
    MLM_PROMPT
)
from app.utils.file_utils import save_upload_file, delete_files

router = APIRouter()

client = OpenAI(
    base_url=BASE_URL,
    api_key=API_KEY
)

@router.post("/upload/", 
    response_model=Dict[str, str],
    status_code=status.HTTP_200_OK,
    summary="上传文件",
    description="上传图片或PDF文件并提取其中的文本内容",
    responses={
        200: {
            "description": "成功提取文本",
            "content": {
                "application/json": {
                    "example": {
                        "text": "提取的文本内容"
                    }
                }
            }
        }
    }
)
async def upload_file(
    file: UploadFile = File(..., description="要上传的文件，支持常见图片格式和PDF文件")
):
    timestamp = int(time.time())
    file_extension = os.path.splitext(file.filename)[1].lower()
    new_filename = f"{timestamp}{file_extension}"
    
    content = await file.read()
    file_path = await save_upload_file(content, new_filename)
    
    markitdown = MarkItDown(llm_client=client, llm_model=MODEL)
    result = markitdown.convert(file_path, llm_prompt=MLM_PROMPT)
    
    # 如果是PDF文件且未提取到文本，则尝试其他方法
    if file_extension == '.pdf' and not result.text_content:
        async with PDFProcessor(concurrent_limit=5) as processor:
            success, text = await processor.extract_text(
                file_path,
                client.api_key,
                MLM_PROMPT,
                batch_size=10
            )
            if success:
                result.text_content = text
    
    # 创建异步任务删除临时文件
    asyncio.create_task(delete_files(file_path, "", FILE_DELETE_DELAY))
    
    return {
        "text": result.text_content or ""
    }