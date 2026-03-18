import numpy as np
import cv2

PRESET_MAPS = {
    "inferno": cv2.COLORMAP_INFERNO,   
    "magma": cv2.COLORMAP_MAGMA,       
    "jet": cv2.COLORMAP_JET,          
    "rainbow": cv2.COLORMAP_RAINBOW,   
    "turbo": cv2.COLORMAP_TURBO,       
    "bone": cv2.COLORMAP_BONE,        
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
        
        nodes = sorted(nodes, key=lambda x: x[0])
        
        if nodes[0][0] > 0:
            nodes.insert(0, (0, nodes[0][1]))
        if nodes[-1][0] < 255:
            nodes.append((255, nodes[-1][1]))
        
        lut = np.zeros((256, 3), dtype=np.uint8)

        for (p0, c0), (p1, c1) in zip(nodes[:-1], nodes[1:]):
            p0, p1 = int(p0), int(p1)
            c0_bgr = np.array((c0[2], c0[1], c0[0]), dtype=np.float32)
            c1_bgr = np.array((c1[2], c1[1], c1[0]), dtype=np.float32)

            if p1 == p0:
                lut[p0] = c0_bgr
                continue
                
            for x in range(p0, p1+1):
                t = (x - p0) / (p1 - p0)
                lut[x] = (c0_bgr * (1 - t) + c1_bgr * t)
    
        return lut.reshape((256, 1, 3))