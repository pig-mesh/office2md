import os
import asyncio
import aiofiles
from typing import Optional

async def save_upload_file(file_content: bytes, filename: str, directory: str = "files") -> str:
    """保存上传的文件"""
    if not os.path.exists(directory):
        os.makedirs(directory)
    
    file_path = os.path.join(directory, filename)
    async with aiofiles.open(file_path, 'wb') as out_file:
        await out_file.write(file_content)
    return file_path

async def delete_files(file_path: str, output_path: Optional[str], delay: int):
    """延迟删除文件"""
    await asyncio.sleep(delay)
    if os.path.exists(file_path):
        os.remove(file_path)
    if output_path and os.path.exists(output_path):
        os.remove(output_path) 