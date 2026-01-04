# component/model_recognizer.py
import torch
import torch.nn as nn
import numpy as np

class MobileFaceNet_Thermal(nn.Module):
    def __init__(self, embedding_size=128):
        super().__init__()
        # 输入单通道热成像图
        self.conv1 = nn.Conv2d(1, 64, 3, 2, 1, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.prelu = nn.PReLU(64)
        
        # 这里省略中间复杂的 Residual Blocks 以节省篇幅
        # 实际使用时需要完整的 MobileFaceNet 结构
        self.body = nn.Sequential(
            nn.Conv2d(64, 128, 3, 2, 1, groups=64), # 模拟下采样
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d(1)
        )
        self.linear = nn.Linear(128, embedding_size)
        self.bn_out = nn.BatchNorm1d(embedding_size)

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.prelu(x)
        x = self.body(x)
        x = x.view(x.size(0), -1)
        x = self.linear(x)
        x = self.bn_out(x)
        return x

    def extract_dummy(self, face_img):
        """模拟输出一个归一化的特征向量"""
        # 实际应调用 self.forward(input_tensor)
        vec = np.random.rand(128).astype(np.float32)
        norm = np.linalg.norm(vec)
        return vec / norm