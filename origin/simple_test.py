import uvc
import logging
import time
import cv2
import numpy as np

# 配置日志
logging.basicConfig(level=logging.INFO)

# --- 使用从设备发现脚本中获得的 VID 和 PID ---
VENDOR_ID = 11231
PRODUCT_ID = 258

# --- 期望的视频模式 ---
WIDTH = 120
HEIGHT = 160
FPS = 25
# ---

cap = None
try:
    # 1. 获取所有设备列表
    print("正在扫描UVC设备...")
    devices = uvc.device_list()
    print(f"扫描完成，找到 {len(devices)} 个设备。")

    # 2. 遍历列表，通过VID和PID找到我们的目标设备
    target_device_uid = None
    for device in devices:
        if device['idVendor'] == VENDOR_ID and device['idProduct'] == PRODUCT_ID:
            target_device_uid = device['uid']
            print(f"成功匹配到设备！UID: {target_device_uid}")
            break

    # 3. 检查是否找到设备，如果找到，则使用其UID进行初始化
    if target_device_uid:
        cap = uvc.Capture(target_device_uid)
        print("设备已成功打开！")
    else:
        # 如果循环结束都没找到，则抛出错误
        raise uvc.Error(f"找不到 VID={VENDOR_ID}, PID={PRODUCT_ID} 的设备。请检查连接和Zadig驱动。")

    # 4. 设置带宽因子
    cap.bandwidth_factor = 3.0
    print(f"带宽因子已设置为 {cap.bandwidth_factor}")
    
    # 5. 查找并设置帧模式
    print(f"可用的视频模式: {cap.available_modes}")
    selected_mode = None
    for mode in cap.available_modes:
        if mode.width == WIDTH and mode.height == HEIGHT and mode.fps == FPS:
            selected_mode = mode
            break
    
    if selected_mode:
        cap.frame_mode = selected_mode
        print(f"成功设置帧模式为: {selected_mode}")
    else:
        raise uvc.Error(f"错误: 找不到模式 {WIDTH}x{HEIGHT} @ {FPS}fps")

    # 6. 尝试获取一帧
    print("\n正在尝试获取第一帧 (最多等待5秒)...")
    frame = cap.get_frame(timeout=5.0)
    
    print("成功获取到一帧！")

    # 7. 解码并显示图像
    if frame.frame_format.name == 'MJPG':
        print("正在解码MJPG帧...")
        data = cv2.imdecode(np.frombuffer(frame.data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if data is not None:
            print("解码成功！显示图像，按任意键关闭。")
            cv2.imshow("Thermal Frame", data)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        else:
            print("解码失败！")

except uvc.Error as e:
    # 捕捉所有来自 uvc 库的错误
    print(f"\n发生 UVC 错误: {e}")
except Exception as e:
    # 捕捉其他可能的错误 (例如 cv2 的错误)
    print(f"\n发生未知错误: {e}")

finally:
    if cap:
        cap.close()
        print("设备已关闭")