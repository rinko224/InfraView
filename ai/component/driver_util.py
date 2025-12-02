import numpy as np
import struct
import cv2
HEAD_SIZE = 4636
def unpack_thermal_frame(thermal_frame):
    if thermal_frame is None or len(thermal_frame) < HEAD_SIZE:
        print("[错误] 输入数据为空或长度不足")
        return None
    header = thermal_frame[:HEAD_SIZE]
    
    
    stream_len, = struct.unpack_from('<I', header, 12)
    data_mode, = struct.unpack_from('<I', header, 20)
    width, = struct.unpack_from('<I', header, 64)
    height, = struct.unpack_from('<I', header, 68)
    print(f"[信息]: 流长度={stream_len}, 数据模式={data_mode}, 宽度={width}, 高度={height}")
    
    pixel_data = thermal_frame[HEAD_SIZE + 4:HEAD_SIZE + stream_len]
    
    if data_mode == 1:
        raw_values = np.frombuffer(pixel_data, dtype='<u2', count=width*height)
        np.savetxt("raw_thermal_matrix.csv", raw_values, delimiter=',', fmt='%.2f')
        temperature = raw_values.astype(np.float32) / 64 - 50
    
    elif data_mode == 0:
        temperature = np.frombuffer(pixel_data, dtype='<f4', count=width*height)
    
    else:
        print("[错误] 未知的数据模式")
        return None
    
    thermal_matrix = temperature.reshape((height, width))

    return thermal_matrix
   
def yuv422_to_bgr(yuv_data, width, height):
    try:
        yuv_array = np.frombuffer(yuv_data, dtype = np.uint8).reshape(height, width, 2)

        bgr_image = cv2.cvtColor(yuv_array, cv2.COLOR_YUV2BGR_VYUY)
        

        return bgr_image
    except Exception as e:
        print(f"[错误]转化为图像失败:{e}")
        return None

def upack_YUV_frame(thermal_frame):
    header = thermal_frame[:HEAD_SIZE]
    stream_len, = struct.unpack_from('<I', header, 12)
    YUV_lenth, = struct.unpack_from("<I", header, 96)
    YUV_width, = struct.unpack_from('<I', header, 88)
    YUV_height, = struct.unpack_from('<I', header, 92)

    YUV_body = thermal_frame[HEAD_SIZE + stream_len:]
    bgr_image = yuv422_to_bgr(YUV_body, width= YUV_width, height = YUV_height)
    

    if bgr_image is not None:
        cv2.imshow("Image", bgr_image)
