import numpy as np
import cv2

PRESET_MAPS = {
    "inferno": cv2.COLORMAP_INFERNO,   # 高对比度的暗背景火焰色系（黑→红→黄）。热像仪最常用之一，细节清晰。
    "magma": cv2.COLORMAP_MAGMA,       # 更暗、偏紫红渐变（黑→深紫→红→黄）。对低温细节敏感，视觉柔和。
    "jet": cv2.COLORMAP_JET,           # 经典彩虹图（蓝→青→绿→黄→红）。颜色跨度大，但易产生误解——科学上不推荐。
    "rainbow": cv2.COLORMAP_RAINBOW,   # 平滑版彩虹色，温度分布直观，但同样不适合精确分析。
    "turbo": cv2.COLORMAP_TURBO,       # Google 优化的“改进版彩虹图”，高线性、高保真。色彩丰富但更科学。
    "bone": cv2.COLORMAP_BONE,         # 类灰度（灰→蓝白）。接近黑白，对结构细节友好，适合医学与工业检测。
}


def process_thermal_for_display(thermal_matrix, out_size, rotation_angle=0, color_mode="inferno", nodes=None):
    if thermal_matrix is None: return None
    clean_matrix = cv2.medianBlur(thermal_matrix.astype(np.float32), 3)

    min_temp = np.min(clean_matrix)
    max_temp = np.max(clean_matrix)
    
    diff = max_temp - min_temp
    if diff < 0.1: diff = 0.1
    
    norm_img = ((clean_matrix - min_temp) / diff * 255).astype(np.uint8)
    
    lut = build_lut(color_mode,nodes)
    thermal_img = cv2.applyColorMap(norm_img, lut)
    
    thermal_img = cv2.resize(thermal_img, out_size, interpolation=cv2.INTER_LINEAR)
    if rotation_angle == 90:
        thermal_img = cv2.rotate(thermal_img, cv2.ROTATE_90_CLOCKWISE)
    elif rotation_angle == 180:
        thermal_img = cv2.rotate(thermal_img, cv2.ROTATE_180)
    elif rotation_angle == 270:
        thermal_img = cv2.rotate(thermal_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    
    text = f"Max: {max_temp:.1f}C  Min: {min_temp:.1f}C"
    
    cv2.putText(thermal_img, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
    cv2.putText(thermal_img, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
    return thermal_img

def build_lut(color_mode, nodes=None):
    if color_mode in PRESET_MAPS:
        gradient = np.linspace(0, 255, 256).astype(np.uint8).reshape((1, 256))
        lut = cv2.applyColorMap(gradient, PRESET_MAPS[color_mode])
        return lut.reshape((256, 1, 3))

    if color_mode == "custom":
        if nodes is None or len(nodes) < 2:
            print("[警告] 自定义模式需要至少2个颜色节点，使用默认inferno")
            gradient = np.linspace(0, 255, 256).astype(np.uint8).reshape((1, 256))
            return cv2.applyColorMap(gradient, PRESET_MAPS["inferno"]).reshape((256, 1, 3))
        
        # 确保节点按位置排序
        nodes = sorted(nodes, key=lambda x: x[0])
        
        # 确保包含起点和终点（位置0和255）
        if nodes[0][0] > 0:
            nodes.insert(0, (0, nodes[0][1]))
        if nodes[-1][0] < 255:
            nodes.append((255, nodes[-1][1]))
        
        lut = np.zeros((256, 3), dtype=np.uint8)

        for (p0, c0), (p1, c1) in zip(nodes[:-1], nodes[1:]):
            p0, p1 = int(p0), int(p1)
            # 关键修改：将RGB转换为BGR
            # c0和c1是RGB元组，OpenCV需要BGR，所以反转顺序
            c0_bgr = np.array((c0[2], c0[1], c0[0]), dtype=np.float32)
            c1_bgr = np.array((c1[2], c1[1], c1[0]), dtype=np.float32)

            # 避免除零错误
            if p1 == p0:
                lut[p0] = c0_bgr
                continue
                
            for x in range(p0, p1+1):
                t = (x - p0) / (p1 - p0)
                lut[x] = (c0_bgr * (1 - t) + c1_bgr * t)
    
        return lut.reshape((256, 1, 3))