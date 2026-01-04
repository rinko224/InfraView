# component/preprocess.py
import numpy as np
import cv2
from . import config

def ai_normalization(thermal_matrix):
    """
    专为AI设计的预处理：截断温度 -> 归一化 -> CLAHE增强
    输入: 二维 float32 温度矩阵
    输出: (H, W) uint8 图像 (用于送入网络)
    """
    if thermal_matrix is None:
        return None

    # 1. 温度截断 (只关注人体温度区间)
    clipped = np.clip(thermal_matrix, config.TEMP_MIN, config.TEMP_MAX)

    # 2. 归一化到 0-255
    # 公式: (x - min) / (max - min) * 255
    norm_img = (clipped - config.TEMP_MIN) / (config.TEMP_MAX - config.TEMP_MIN) * 255.0
    norm_img = norm_img.astype(np.uint8)

    # 3. CLAHE (限制对比度自适应直方图均衡化)
    # 这步至关重要，能把模糊的热斑变成有纹理的图像
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced_img = clahe.apply(norm_img)

    return enhanced_img

def prepare_for_model(img, target_size):
    """缩放并转为 Tensor 格式 (模拟)"""
    img_resized = cv2.resize(img, target_size)
    # 在实际 PyTorch 中这里需要 ToTensor 和 Unsqueeze
    # 这里返回 numpy 用于演示流程
    return img_resized