import cv2
import numpy as np
import time

try:
    import uvc
except ImportError:
    print("错误: pyuvc 库未安装。")
    print("请运行: pip install pyuvc")
    exit()

# ========================== 用户配置 ==========================
# !!! 请务必将这里的 VID 和 PID 修改为您自己的摄像头硬件ID !!!
TARGET_VID = 0x2BDF
TARGET_PID = 0x0102
# ============================================================

VENDOR_ID = 11231
PRODUCT_ID = 258

def perform_camera_setup(device):
    """
    根据UVC开发指南，严格按照流程执行与摄像头的底层命令交互。
    包含协议版本检查 -> 功能切换 -> 码流类型配置。
    """
    print("\n--- 正在执行底层UVC扩展命令 ---")
    
    # 从手册第10页得知，扩展单元的Unit ID是 0x0A
    UNIT_ID = 0x0A 
    
    try:
        # 1. 查找扩展单元(Extension Unit, XU)控件
        xu_control = None
        for ctrl in device.controls:
            if ctrl.unit == UNIT_ID:
                xu_control = ctrl
                print(f"[信息] 找到扩展单元(Extension Unit)，Unit ID: {ctrl.unit}")
                break
        
        if not xu_control:
            print(f"[致命错误] 未能找到 Unit ID 为 {UNIT_ID} 的扩展单元。程序无法继续。")
            return False

        # 2. 【新增步骤】查询协议版本 (参考手册 1.2.1 节, 第11页)
        print("\n步骤1: 查询协议版本 (CS_ID=0x04)")
        # wValue的高字节是控件选择器(CS ID), 手册P9定义 XU_CS_ID_PROTOCOL_VER = 0x04
        protocol_selector = 0x0400  
        # 手册P11的请求报文示例显示，GET_CUR请求后，设备返回4字节 ("2.0" + null)
        expected_length = 4
        
        # 使用 GET 请求获取数据
        response = xu_control.get(protocol_selector, expected_length)
        
        # 解析返回的数据
        # pyuvc返回的是一个memoryview, 需转换为bytes再解码
        protocol_version = response.tobytes().decode('utf-8', errors='ignore').strip('\x00')
        print(f"       设备返回的协议版本字符串: '{protocol_version}'")

        # 验证版本是否正确
        if protocol_version != "2.0":
            print(f"[致命错误] 设备返回的协议版本不是 '2.0' (实际为: {protocol_version})。")
            print("         本程序是基于2.0协议编写的，无法继续。")
            return False
        
        print("[成功] 协议版本确认为 2.0，可以继续。")

        # 3. 发送功能切换命令 (参考手册 1.2.2 节)
        print("\n步骤2: 发送功能切换命令 -> 热成像测温管理(CS_ID=0x03)")
        # wValue的高字节是CS ID, P9定义 XU_CS_ID_COMMAND_SWITCH = 0x05
        cmd_switch_selector = 0x0500
        # data是我们要切换到的目标功能ID，P9定义 XU_CS_ID_THERMAL = 0x03
        data_to_send = b'\x03' 
        xu_control.set(cmd_switch_selector, data_to_send)
        print("       命令已发送。")
        time.sleep(0.1)

        # 4. 配置实时上传码流类型 (参考手册 A.3.5 节)
        print("\n步骤3: 配置实时码流类型 -> 6-YUV实时流")
        # selector的高字节是CS ID, P36定义子功能为0x05 (THERMAL_STREAM_PARAM)
        stream_param_selector = 0x0500 
        # data是要设置的码流类型值 (6 = YUV实时流)
        data_to_send = b'\x06'
        xu_control.set(stream_param_selector, data_to_send)
        print("       命令已发送。")
        time.sleep(0.1)

        print("\n--- 底层UVC扩展命令执行完毕 ---")
        return True

    except Exception as e:
        print(f"[致命错误] 在发送UVC扩展命令时发生异常: {e}")
        print("         这通常意味着设备不支持此命令，或者驱动存在问题。")
        return False

# 主函数部分与之前相同，这里为了完整性全部放出
def main():
    print("--- 启动热成像摄像头测试程序 (V2 - 带协议检查) ---")
    
    print("正在扫描UVC设备...")
    devices = uvc.device_list()
    print(f"扫描完成，找到 {len(devices)} 个设备。")

    target_device_uid = None
    for device in devices:
        if device['idVendor'] == VENDOR_ID and device['idProduct'] == PRODUCT_ID:
            target_device_uid = device['uid']
            print(f"成功匹配到设备！UID: {target_device_uid}")
            break

    if not target_device_uid:
        print(f"[错误] 未找到指定的设备 (VID=0x{TARGET_VID:04x}, PID=0x{TARGET_PID:04x})。")
        return

    device = uvc.Capture(target_device_uid)
    print(f"[成功] 找到设备: {device.name}")


    if not perform_camera_setup(device):
        device.close()
        return

    print("\n--- 正在查找可用的视频流模式 ---")
    supported_mode = None
    # 查找YUYV格式
    for mode in device.streams[0].modes:
        if 'YUYV' in mode.format.name:
            print(f"找到支持的YUYV模式: {mode.width}x{mode.height} @ {mode.max_fps}fps")
            supported_mode = mode
            if mode.width == 120 and mode.height == 160:
                break
    
    if not supported_mode:
        print("[错误] 未找到任何支持的 YUYV 视频流模式。")
        device.close()
        return
        
    print(f"选择模式: {supported_mode.width}x{supported_mode.height} @ {supported_mode.max_fps}fps")

    stream = device.streams[0]
    stream.open(supported_mode)
    queue = stream.get_frame_queue(2)

    try:
        print("\n--- 开始捕获视频流 ---")
        print("按 'q' 键关闭窗口。")
        
        stream.start_capture()

        while True:
            frame = queue.get()
            
            # YUV转BGR
            yuv_image = np.frombuffer(frame.data.tobytes(), dtype=np.uint8).reshape(
                frame.height, frame.width, 2
            )
            bgr_frame = cv2.cvtColor(yuv_image, cv2.COLOR_YUV2BGR_YUYV)
            
            # (可选) 旋转
            # bgr_frame = cv2.rotate(bgr_frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

            cv2.imshow("Thermal Camera (pyuvc - V2)", bgr_frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    
    finally:
        print("\n--- 正在关闭程序 ---")
        stream.stop_capture()
        stream.close()
        device.close()
        cv2.destroyAllWindows()
        print("程序已退出。")


if __name__ == "__main__":
    main()