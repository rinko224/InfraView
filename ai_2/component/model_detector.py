# component/model_detector.py
import torch
import torch.nn as nn

# 深度可分离卷积 (轻量化的核心)
class DepthwiseSeparableConv(nn.Module):
    def __init__(self, in_ch, out_ch, stride=1):
        super().__init__()
        self.depthwise = nn.Conv2d(in_ch, in_ch, 3, stride, 1, groups=in_ch, bias=False)
        self.pointwise = nn.Conv2d(in_ch, out_ch, 1, bias=False)
        self.bn = nn.BatchNorm2d(out_ch)
        self.act = nn.ReLU6(inplace=True)

    def forward(self, x):
        x = self.depthwise(x)
        x = self.pointwise(x)
        x = self.bn(x)
        return self.act(x)

class CustomTinyYOLO(nn.Module):
    def __init__(self):
        super().__init__()
        # 极简 Backbone
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, 3, 2, 1, bias=False), # 输入单通道
            nn.BatchNorm2d(16),
            nn.ReLU6(inplace=True),
            DepthwiseSeparableConv(16, 32, 2),
            DepthwiseSeparableConv(32, 64, 2),
            DepthwiseSeparableConv(64, 128, 2),
            DepthwiseSeparableConv(128, 256, 2),
        )
        # 极简检测头 (C=1, only Face)
        # 输出: 5 (x,y,w,h,conf) + 1 (cls) = 6
        self.head = nn.Conv2d(256, 6, 1)

    def forward(self, x):
        x = self.features(x)
        x = self.head(x)
        return x

    def detect_dummy(self, img_shape):
        """
        因为没有真实权重，这里模拟一个返回结果
        返回格式: [ [x1, y1, x2, y2, score], ... ]
        """
        # 假装检测到了屏幕中间有一个人脸
        h, w = img_shape
        return [[w//4, h//4, w*3//4, h*3//4, 0.99]]