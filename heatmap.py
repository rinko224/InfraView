import numpy as np
import cv2

def process_thermal_for_display(thermal_matrix):
    if thermal_matrix is None: return None
    clean_matrix = cv2.medianBlur(thermal_matrix.astype(np.float32), 3)

    min_temp = np.min(clean_matrix)
    max_temp = np.max(clean_matrix)
    
    diff = max_temp - min_temp
    if diff < 0.1: diff = 0.1
    
    norm_img = ((clean_matrix - min_temp) / diff * 255).astype(np.uint8)
    
    thermal_img = cv2.applyColorMap(norm_img, cv2.COLORMAP_INFERNO)
    
    thermal_img = cv2.resize(thermal_img, (512, 384), interpolation=cv2.INTER_LINEAR)
    
    text = f"Max: {max_temp:.1f}C  Min: {min_temp:.1f}C"
    
    cv2.putText(thermal_img, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
    cv2.putText(thermal_img, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
    return thermal_img