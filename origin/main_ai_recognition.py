import usb.core
import usb.util
import time
import struct
import cv2
import numpy as np
import os
from datetime import datetime
from http import HTTPStatus

# 导入阿里云 DashScope SDK
import dashscope

# 导入你原本的工具模块 (必须确保这些文件在同级目录)
try:
    from util import unpack_thermal_frame
    from heatmap import process_thermal_for_display
except ImportError:
    print("[错误] 缺少 util.py 或 heatmap.py，无法解析热成像数据。")
    exit()

# ================= 配置区域 =================
#在此处填入你的阿里云 DashScope API Key
dashscope.api_key = "sk-f29944fbb2c049d4a34ae639589ed88e"

# 使用的模型，推荐 qwen-vl-max 或 qwen-vl-plus
MODEL_NAME = "qwen-vl-max" 
# ===========================================

# 常量定义 (保持原样)
SET_CUR = 0x01
GET_CUR = 0x81
GET_LEN = 0x85
UNIT_ID = 0x0A
HEADER_SIZE = 4636

class HikCamera:
    # ... (此处为你提供的 HikCamera 类代码，保持不变) ...
    # 为了节省篇幅，这里复用你提供的类的逻辑，实际运行时请包含完整的类定义
    def __init__(self, vendor_id=0x2BDF, product_id=0x0102):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.device = None
        self.is_connected = False
        self.last_error = ""
        self.config = None
        self.vc_interface_num = None
        self.vs_interface_num = None
        self.vs_endpoint_addr = None

    def connect(self):
        # ... (复制你原来的 connect 代码) ...
        if self.is_connected: return True
        try:
            self.device = usb.core.find(idVendor=self.vendor_id, idProduct=self.product_id)
            if self.device is None:
                self.last_error = "设备未找到"
                return False
            self.device.set_configuration()
            self.config = self.device.get_active_configuration()
            vc_interface = usb.util.find_descriptor(self.config, bInterfaceClass=14, bInterfaceSubClass=1)
            vs_interface = usb.util.find_descriptor(self.config, bInterfaceClass=14, bInterfaceSubClass=2)
            if vc_interface is None or vs_interface is None: return False
            self.vs_interface_num = vs_interface.bInterfaceNumber
            self.vc_interface_num = vc_interface.bInterfaceNumber
            
            active_alt_setting = None
            for iface in self.config.interfaces():
                if iface.bNumEndpoints > 0 and iface.bInterfaceNumber == self.vs_interface_num:
                    active_alt_setting = iface
                    break
            if active_alt_setting is None: return False
            
            for ep in active_alt_setting:
                if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
                    self.vs_endpoint_addr = ep.bEndpointAddress
                    break
            if self.vs_endpoint_addr is None: return False
            
            alt_setting_num = active_alt_setting.bAlternateSetting
            self.device.set_interface_altsetting(interface=self.vs_interface_num, alternate_setting=alt_setting_num)
            
            # 简单的版本检查，确保通讯正常
            response = self.send_xu_control_command(GET_CUR, UNIT_ID, cs_id=0x04, data=None, length=4)
            protocol_version = response.tobytes().decode('utf-8', 'ignore').strip('\x00')
            if protocol_version != "2.0": return False
            
            self.is_connected = True
            return True
        except Exception as e:
            self.last_error = str(e)
            return False

    def set_time(self):
        # ... (复制你原来的 set_time 代码) ...
        try:
            self.send_xu_control_command(GET_LEN, UNIT_ID, cs_id=0x05, length=2)
            self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id=0x05, data=bytearray([0x01, 0x05]))
            millisecond_cur = datetime.now().microsecond // 1000
            second_cur = datetime.now().second
            minute_cur = datetime.now().minute
            hour_cur = datetime.now().hour
            payload_set_time = struct.pack('<HBBBBBH', millisecond_cur, second_cur, minute_cur, hour_cur, 0, 0, 0)
            self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id=0x01, data=payload_set_time)
            return True
        except: return False

    def disconnect(self):
        # ... (复制你原来的 disconnect 代码) ...
        if self.is_connected:
            try:
                self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id=0x05, data=bytearray([0x03, 0x05]))
                self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id=0x03, data=bytearray([0x01, 0x05]))
                time.sleep(0.1)
            except: pass
        if self.device:
            usb.util.dispose_resources(self.device)
        self.is_connected = False

    def send_xu_control_command(self, bRequest, unit_id, cs_id, data=None, length=None):
        if usb.util.endpoint_direction(bRequest) == usb.util.ENDPOINT_OUT:
            bmRequestType = 0x21; payload = data
        else:
            bmRequestType = 0xA1; payload = length
        wValue = (cs_id << 8)
        wIndex = (unit_id << 8) | self.vc_interface_num
        return self.device.ctrl_transfer(bmRequestType, bRequest, wValue, wIndex, payload)

    def read_from_vs_endpoint(self, size, timeout=100):
        if not self.is_connected: return None
        data = bytearray(); bytes_read = 0
        while bytes_read < size:
            try:
                chunk = self.device.read(self.vs_endpoint_addr, size - bytes_read, timeout)
                if not chunk: break
                data.extend(chunk)
                bytes_read += len(chunk)
            except usb.core.USBError: break
        return data if bytes_read >= size else None

    def start_stream(self):
        # ... (复制你原来的 start_stream 代码) ...
        if not self.is_connected: return None
        try:
            # 简化流程，直接复制原有逻辑序列
            self.send_xu_control_command(GET_LEN, UNIT_ID, cs_id=0x05, length=2)
            self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id=0x05, data=bytearray([0x03, 0x01]))
            self.send_xu_control_command(GET_LEN, UNIT_ID, cs_id=0x03, length=2)
            self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id=0x03, data=bytearray([0x01, 0x01]))
            time.sleep(0.1)
            self.send_xu_control_command(GET_LEN, UNIT_ID, cs_id=0x05, length=2)
            self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id=0x05, data=bytearray([0x03, 0x02]))
            self.send_xu_control_command(GET_LEN, UNIT_ID, cs_id=0x03, length=2)
            self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id=0x03, data=bytearray([0x01, 0x02]))
            time.sleep(0.1)
            self.send_xu_control_command(GET_LEN, UNIT_ID, cs_id=0x05, length=2)
            self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id=0x05, data=bytearray([0x03, 0x05]))
            self.send_xu_control_command(GET_LEN, UNIT_ID, cs_id=0x03, length=2)
            self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id=0x03, data=bytearray([0x01, 0x08]))
            time.sleep(0.1)
            self.clear_endpoint_buffer()
            return True
        except: return False

    def read_next_frame(self):
        # ... (复制你原来的 read_next_frame 代码) ...
        if not self.is_connected: return None
        self.clear_endpoint_buffer()
        try:
            raw_len = self.read_from_vs_endpoint(1, timeout=100)
            if not raw_len: return None
            uvc_len = raw_len[0]
            if uvc_len > 1: self.read_from_vs_endpoint(uvc_len - 1, timeout=100)
            magic_buf = self.read_from_vs_endpoint(4, timeout=100)
            if not magic_buf: return None
            magic_val, = struct.unpack('<I', magic_buf)
            if magic_val != 0x70827773:
                self.read_from_vs_endpoint(512, timeout=10); return None
            header = self.read_from_vs_endpoint(HEADER_SIZE - 4, timeout=100)
            if not header: return None
            header = magic_buf + header
            stream_len, = struct.unpack_from('<I', header, 12)
            yuv_len, = struct.unpack_from('<I', header, 96)
            data_body = self.read_from_vs_endpoint(stream_len, timeout=100)
            yuv_body = self.read_from_vs_endpoint(yuv_len, timeout=100)
            if data_body and yuv_body: return header + data_body + yuv_body
            return None
        except: return None

    def clear_endpoint_buffer(self):
        try:
            while True:
                self.device.read(self.vs_endpoint_addr, 1024*16, timeout=10)
        except: pass

# ================= AI 识别功能 =================

def call_qwen_vl(image_path):
    """
    调用通义千问 VL 模型识别本地图片
    """
    print(f"[AI] 正在请求 Qwen 识别图片: {image_path} ...")
    
    # 构建 Prompt：要求识别、描述并给出置信度
    prompt_text = (
        "这是一张热成像相机的图片。请分析画面：\n"
        "1. 识别画面中的主要物体。\n"
        "2. 简要描述物体状态（如温度分布特征）。\n"
        "3. 给出你对识别结果的置信度（0-100%）。\n"
        "请按以下格式输出：\n"
        "【识别物体】: ...\n"
        "【简要描述】: ...\n"
        "【置信度】: ...%"
    )

    try:
        messages = [
            {
                "role": "user",
                "content": [
                    {"image": f"file://{os.path.abspath(image_path)}"},
                    {"text": prompt_text}
                ]
            }
        ]
        
        response = dashscope.MultiModalConversation.call(model=MODEL_NAME, messages=messages)
        
        if response.status_code == HTTPStatus.OK:
            return response.output.choices[0].message.content
        else:
            return f"API 错误: {response.code} - {response.message}"
            
    except Exception as e:
        return f"请求异常: {str(e)}"

# ================= 主程序逻辑 =================

def capture_and_identify_one_shot():
    print("--- 热成像 AI 单帧识别工具 ---")
    
    if dashscope.api_key == "YOUR_DASHSCOPE_API_KEY_HERE":
        print("[错误] 请先在代码中设置 dashscope.api_key")
        return

    camera = HikCamera()
    
    if not camera.connect():
        print(f"[失败] 无法连接相机: {camera.last_error}")
        return

    print("[成功] 相机连接成功，初始化中...")
    camera.set_time()
    camera.clear_endpoint_buffer()
    
    if not camera.start_stream():
        print("[失败] 视频流启动失败")
        camera.disconnect()
        return

    print("[信息] 正在预热并捕获图像 (读取前 10 帧以稳定画面)...")
    
    valid_frame_img = None
    
    # 读取几帧以清空缓存并获得稳定图像
    for i in range(15):
        full_frame = camera.read_next_frame()
        if full_frame:
            thermal_matrix = unpack_thermal_frame(full_frame)
            if thermal_matrix is not None:
                # 转换为可视化的 OpenCV 图像 (heatmap.py 中的逻辑)
                img = process_thermal_for_display(thermal_matrix)
                if img is not None:
                    valid_frame_img = img
        time.sleep(0.05)

    if valid_frame_img is not None:
        # 1. 保存临时文件
        temp_filename = "temp_thermal_shot.jpg"
        cv2.imwrite(temp_filename, valid_frame_img)
        print(f"[快照] 已保存临时图像: {temp_filename}")
        
        # 2. 显示图片给用户看
        cv2.imshow("Captured Thermal Frame", valid_frame_img)
        cv2.waitKey(100) # 刷新界面
        
        # 3. 调用 AI 识别
        print("------------------------------------------------")
        ai_result = call_qwen_vl(temp_filename)
        print(">>> Qwen 识别结果:\n")
        print(ai_result)
        print("------------------------------------------------")
        
        # 等待用户按键后退出
        print("按任意键退出程序...")
        cv2.waitKey(0)
        
        # 清理临时文件
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
    else:
        print("[失败] 未能获取有效的热成像帧")

    camera.disconnect()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    capture_and_identify_one_shot()