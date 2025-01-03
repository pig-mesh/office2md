import os
import torch
import torch.nn.functional as F
from app.utils.model import UVDocnet

IMG_SIZE = [488, 712]
GRID_SIZE = [45, 31]


def load_model(ckpt_path):
    """
    Load UVDocnet model.
    """
    model = UVDocnet(num_filter=32, kernel_size=5)
    ckpt = torch.load(ckpt_path, map_location=torch.device('cpu'))
    model.load_state_dict(ckpt["model_state"])
    return model


def bilinear_unwarping(warped_img, point_positions, img_size):
    """
    Utility function that unwarps an image.
    Unwarp warped_img based on the 2D grid point_positions with a size img_size.
    """
    upsampled_grid = F.interpolate(
        point_positions, size=(img_size[1], img_size[0]), mode="bilinear", align_corners=True
    )
    unwarped_img = F.grid_sample(warped_img, upsampled_grid.transpose(1, 2).transpose(2, 3), align_corners=True)
    return unwarped_img 