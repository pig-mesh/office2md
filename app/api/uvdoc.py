import os
from io import BytesIO
from typing import Optional

import cv2
import numpy as np
import torch
from fastapi import APIRouter, File, UploadFile, HTTPException, Response
from pydantic import BaseModel
from PIL import Image

from app.utils import IMG_SIZE, bilinear_unwarping, load_model

# 路由器添加描述
router = APIRouter(
    prefix="/uvdoc"
)

# 全局变量存储加载的模型
model = None
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class UnwarpResponse(BaseModel):
    success: bool
    message: str
    text: Optional[str] = None


# 创建一个普通函数来加载模型
def load_model_fn():
    """加载模型的函数"""
    global model
    try:
        ckpt_path = os.getenv("MODEL_CHECKPOINT_PATH", "./model/best_model.pkl")
        model = load_model(ckpt_path)
        model.to(device)
        model.eval()
    except Exception as e:
        print(f"Error loading model: {str(e)}")
        model = None

# 在main.py中会调用这个函数
load_model_fn()


@router.post(
    "/unwarp",
    response_class=Response,
    summary="文档图像展平",
    description="接收一张弯曲变形的文档图片，返回展平后的图片",
    responses={
        200: {
            "description": "图片展平处理成功",
            "content": {"image/png": {}}
        },
        500: {
            "description": "模型加载错误或处理错误",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Model not loaded"
                    }
                }
            }
        }
    }
)
async def unwarp_image(
    file: UploadFile = File(..., description="需要进行展平处理的文档图片文件")
):
    """
    使用深度学习模型对文档图片进行展平处理。
    
    参数:
        file (UploadFile): 输入的图片文件，支持常见图片格式（PNG、JPEG等）
        
    返回:
        Response: 包含展平后图片数据的响应对象
            
    异常:
        HTTPException: 当模型未加载或发生其他处理错误时抛出
    """
    if model is None:
        raise HTTPException(status_code=500, detail="Model not loaded")

    try:
        # 读取上传的图片
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return UnwarpResponse(success=False, message="Invalid image file")

        # 转换图片格式
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255
        inp = torch.from_numpy(cv2.resize(img, IMG_SIZE).transpose(2, 0, 1)).unsqueeze(0)

        # 进行预测
        inp = inp.to(device)
        with torch.no_grad():
            point_positions2D, _ = model(inp)

        # 展平处理
        size = img.shape[:2][::-1]
        unwarped = bilinear_unwarping(
            warped_img=torch.from_numpy(img.transpose(2, 0, 1)).unsqueeze(0).to(device),
            point_positions=torch.unsqueeze(point_positions2D[0], dim=0),
            img_size=tuple(size),
        )
        unwarped = (unwarped[0].detach().cpu().numpy().transpose(1, 2, 0) * 255).astype(np.uint8)

        # 转换为PIL Image并直接输出为字节流
        pil_img = Image.fromarray(cv2.cvtColor(unwarped, cv2.COLOR_RGB2BGR))
        img_byte_arr = BytesIO()
        pil_img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)

        return Response(
            content=img_byte_arr.getvalue(),
            media_type="image/png"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing image: {str(e)}"
        )
