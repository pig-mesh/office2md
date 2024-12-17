import os
import time
import asyncio
import fitz  # PyMuPDF
from fastapi import APIRouter, File, UploadFile, status
from typing import Dict, Optional, Tuple
from openai import OpenAI
from markitdown import MarkItDown
import tempfile

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

async def process_pdf_page(
    page: fitz.Page, 
    markitdown: MarkItDown,
    mlm_prompt: str
) -> Optional[str]:
    """处理单个PDF页面，尝试提取文本或进行OCR识别
    
    Args:
        page: PDF页面对象
        markitdown: MarkItDown实例
        mlm_prompt: 文本提取提示
        
    Returns:
        提取的文本内容，如果提取失败返回None
    """
    # 首先尝试直接提取文本
    text = page.get_text().strip()
    if text:
        return text
        
    # 如果直接提取失败，转换为图片进行OCR
    try:
        pix = page.get_pixmap()
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_img:
            pix.save(temp_img.name)
            result = markitdown.convert(temp_img.name, mlm_prompt=mlm_prompt)
            # 清理临时文件
            os.unlink(temp_img.name)
            return result.text_content
    except Exception as e:
        print(f"页面处理错误: {str(e)}")
        return None

async def extract_pdf_text(
    pdf_path: str,
    markitdown: MarkItDown,
    mlm_prompt: str
) -> Tuple[bool, str]:
    """从PDF文件中提取文本
    
    Args:
        pdf_path: PDF文件路径
        markitdown: MarkItDown实例
        mlm_prompt: 文本提取提示
        
    Returns:
        (是否成功, 提取的文本内容)
    """
    try:
        pdf_document = fitz.open(pdf_path)
        all_text = []
        
        for page_num in range(len(pdf_document)):
            text = await process_pdf_page(
                pdf_document[page_num],
                markitdown,
                mlm_prompt
            )
            if text:
                all_text.append(text)
                
        pdf_document.close()
        
        if all_text:
            return True, '\n'.join(all_text)
        return False, ""
        
    except Exception as e:
        print(f"PDF处理错误: {str(e)}")
        return False, ""

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
    
    markitdown = MarkItDown(mlm_client=client, mlm_model=MODEL)
    result = markitdown.convert(file_path, mlm_prompt=MLM_PROMPT)
    
    # 如果是PDF文件且未提取到文本，则尝试其他方法
    if file_extension == '.pdf' and not result.text_content:
        success, text = await extract_pdf_text(file_path, markitdown, MLM_PROMPT)
        if success:
            result.text_content = text
    
    # 创建异步任务删除临时文件
    asyncio.create_task(delete_files(file_path, "", FILE_DELETE_DELAY))
    
    return {
        "text": result.text_content or ""
    }