import os
import time
import tempfile
import asyncio
import logging
from concurrent.futures import ProcessPoolExecutor
import fitz  # PyMuPDF
from typing import Optional, Tuple, List, NamedTuple
from markitdown import MarkItDown
from openai import OpenAI
from app.config import BASE_URL, MODEL

# 配置日志
logger = logging.getLogger(__name__)

class OCRArgs(NamedTuple):
    """OCR参数集合"""
    image_path: str
    api_key: str
    mlm_prompt: str
    base_url: str
    model: str

def ocr_worker(args: OCRArgs) -> Optional[str]:
    """OCR工作进程"""
    client = None
    try:
        client = OpenAI(base_url=args.base_url, api_key=args.api_key)
        markitdown = MarkItDown(
            llm_client=client,
            llm_model=args.model
        )
        result = markitdown.convert(args.image_path, llm_prompt=args.mlm_prompt)
        return result.text_content
    except Exception as e:
        logger.error(f"OCR处理错误: {str(e)}")
        return None
    finally:
        if client:
            client.close()

class PDFProcessor:
    def __init__(self, concurrent_limit: int = 5):
        """初始化PDF处理器"""
        self.concurrent_limit = concurrent_limit
        self.executor = None
        
    async def __aenter__(self):
        self.executor = ProcessPoolExecutor(max_workers=self.concurrent_limit)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.executor:
            self.executor.shutdown(wait=True)
            self.executor = None

    async def process_page(
        self,
        page: fitz.Page,
        api_key: str,
        mlm_prompt: str,
        page_num: int
    ) -> Tuple[int, Optional[str]]:
        """处理单个PDF页面"""
        logger.info(f"开始处理第 {page_num + 1} 页...")
        
        # 尝试直接提取文本
        text = page.get_text().strip()
        if text:
            logger.info(f"第 {page_num + 1} 页: 成功直接提取文本，长度 {len(text)} 字符")
            return page_num, text
        
        # OCR处理
        logger.info(f"第 {page_num + 1} 页: 无法直接提取文本，开始OCR处理...")
        try:
            pix = page.get_pixmap()
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_img:
                pix.save(temp_img.name)
                logger.debug(f"第 {page_num + 1} 页: 临时图片已保存到 {temp_img.name}")
                
                try:
                    args = OCRArgs(
                        image_path=temp_img.name,
                        api_key=api_key,
                        mlm_prompt=mlm_prompt,
                        base_url=BASE_URL,
                        model=MODEL
                    )
                    
                    logger.info(f"第 {page_num + 1} 页: 开始OCR识别...")
                    start_time = time.perf_counter()
                    
                    loop = asyncio.get_running_loop()
                    text_content = await loop.run_in_executor(
                        self.executor,
                        ocr_worker,
                        args
                    )
                    
                    process_time = time.perf_counter() - start_time
                    if text_content:
                        logger.info(
                            f"第 {page_num + 1} 页: OCR识别成功，"
                            f"耗时 {process_time:.1f}秒，"
                            f"提取文本长度 {len(text_content)} 字符"
                        )
                    else:
                        logger.warning(f"第 {page_num + 1} 页: OCR识别失败，耗时 {process_time:.1f}秒")
                    
                    return page_num, text_content
                    
                finally:
                    try:
                        os.unlink(temp_img.name)
                        logger.debug(f"第 {page_num + 1} 页: 临时文件已清理")
                    except Exception as e:
                        logger.warning(f"第 {page_num + 1} 页: 清理临时文件失败: {str(e)}")
                        
        except Exception as e:
            logger.error(f"第 {page_num + 1} 页处理错误: {str(e)}")
            return page_num, None

    async def process_batch(
        self,
        pdf_document: fitz.Document,
        api_key: str,
        mlm_prompt: str,
        start_page: int,
        end_page: int
    ) -> List[Tuple[int, Optional[str]]]:
        """处理一批PDF页面"""
        tasks = []
        for page_num in range(start_page, min(end_page, len(pdf_document))):
            task = self.process_page(
                pdf_document[page_num],
                api_key,
                mlm_prompt,
                page_num
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        return results

    async def extract_text(
        self,
        pdf_path: str,
        api_key: str,
        mlm_prompt: str,
        batch_size: int = 10
    ) -> Tuple[bool, str]:
        """提取PDF文本"""
        pdf_document = None
        start_time = time.perf_counter()
        try:
            pdf_document = fitz.open(pdf_path)
            total_pages = len(pdf_document)
            total_batches = (total_pages + batch_size - 1) // batch_size
            logger.info(f"开始处理PDF文件，总页数: {total_pages}，批次数: {total_batches}")
            
            # 创建所有批次的任务
            tasks = []
            for start_page in range(0, total_pages, batch_size):
                end_page = min(start_page + batch_size, total_pages)
                batch_num = start_page // batch_size + 1
                logger.info(f"创建批次 {batch_num}/{total_batches} (页码 {start_page+1}-{end_page})")
                task = self.process_batch(
                    pdf_document,
                    api_key,
                    mlm_prompt,
                    start_page,
                    end_page
                )
                tasks.append((batch_num, task))
            
            # 并发执行所有批次
            logger.info(f"开始并发处理 {len(tasks)} 个批次...")
            batch_results = await asyncio.gather(*(task for _, task in tasks))
            
            # 合并所有批次的结果并记录每个批次的完成情况
            all_results = []
            for (batch_num, _), results in zip(tasks, batch_results):
                batch_success = sum(1 for _, text in results if text is not None)
                batch_total = len(results)
                logger.info(
                    f"批次 {batch_num}/{total_batches} 完成: "
                    f"成功 {batch_success}/{batch_total} 页 "
                    f"({batch_success/batch_total*100:.1f}%)"
                )
                all_results.extend(results)
            
            # 最终处理结果
            all_results.sort(key=lambda x: x[0])
            valid_texts = [text for _, text in all_results if text]
            
            total_time = time.perf_counter() - start_time
            logger.info(
                f"PDF处理完成: 成功率 {(len(valid_texts)/total_pages*100):.1f}%,"
                f" 总耗时 {total_time:.1f}秒,"
                f" 平均每页 {(total_time/total_pages):.1f}秒"
            )
            
            if valid_texts:
                return True, '\n'.join(valid_texts)
            return False, ""
            
        except Exception as e:
            elapsed_time = time.perf_counter() - start_time
            logger.error(f"PDF处理错误: {str(e)}, 耗时 {elapsed_time:.1f}秒")
            return False, ""
        finally:
            if pdf_document:
                pdf_document.close()
