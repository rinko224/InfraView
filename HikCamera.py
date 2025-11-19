import usb.core
import usb.util
import time
import struct
import cv2
import numpy as np
from datetime import datetime
from util import unpack_thermal_frame
from heatmap import create_thermal_image
from util import upack_YUV_frame

SET_CUR = 0x01 #设置类指令
GET_CUR = 0x81 #获取类指令
GET_LEN = 0x85 #获取长度类指令
UNIT_ID = 0x0A

HEADER_SIZE = 4636


class HikCamera:
    def __init__(self, vendor_id = 0x2BDF, product_id = 0x0102):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.device = None
        self.is_connected = False
        self.last_error = ""
        self.config = None
        self.vc_interface_num = None#控制接口
        self.vs_interface_num = None#视频流接口
        self.vs_endpoint_addr = None#视频流数据输入端点
        self.fps = None

    def connect(self):
        if self.is_connected:
            return True
        
        try:
            self.device = usb.core.find(idVendor=self.vendor_id, idProduct=self.product_id)
            if self.device is None:
                self.last_error = "设备未找到"
                print(f"[失败] {self.last_error}")
                return False
            
            self.device.set_configuration()
            self.config = self.device.get_active_configuration()
            
            vc_interface = usb.util.find_descriptor(self.config, bInterfaceClass=14, bInterfaceSubClass=1)
            vs_interface = usb.util.find_descriptor(self.config, bInterfaceClass=14, bInterfaceSubClass=2)

            if vc_interface is None or vs_interface is None:
                self.last_error = "未找到视频控制接口或视频流接口"
                print(f"[失败] {self.last_error}")
                return False
            
            self.vs_interface_num = vs_interface.bInterfaceNumber
            print(f"[信息] 找到视频流接口 (VS): {self.vs_interface_num}")
            self.vc_interface_num = vc_interface.bInterfaceNumber
            print(f"[信息] 找到视频控制接口 (VC): {self.vc_interface_num}")

            active_alt_setting = None
            for iface in self.config.interfaces():
                if iface.bNumEndpoints > 0 and iface.bInterfaceNumber == self.vs_interface_num:
                    active_alt_setting = iface
                    break
                
            if active_alt_setting is None:
                self.last_error = "未找到有效视频流备用设置"
                print(f"[失败] {self.last_error}")
                return False
            
            print(f"[信息] 找到视频流接口 (VS) 的有效备用设置: {active_alt_setting.bAlternateSetting}")

            for ep in active_alt_setting:
                if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
                    self.vs_endpoint_addr = ep.bEndpointAddress
                    break

            if self.vs_endpoint_addr is None:
                self.last_error = "未找到视频流数据输入端点"
                print(f"[失败] {self.last_error}")
                return False
            
            alt_setting_num = active_alt_setting.bAlternateSetting

            print(f"[信息]   - 找到活动备用设置: {alt_setting_num}")
            print(f"[信息]   - 找到数据输入端点 (Endpoint): 0x{self.vs_endpoint_addr:02x}")

            print(f"[步骤] 激活视频流接口 (VS) {self.vs_interface_num} -> 使用备用设置 {alt_setting_num}...")
            self.device.set_interface_altsetting(interface=self.vs_interface_num, alternate_setting=alt_setting_num)
            print("[信息] 视频流接口已激活")
            
            # for interface in self.config:
            #     if interface.bInterfaceClass == 14: # Video Class
            #         if interface.bInterfaceSubClass == 1: # VideoControl
            #             self.vc_interface_num = interface.bInterfaceNumber
            #             print(f"[信息] 找到视频控制接口 (VC): {self.vc_interface_num}")
            #         elif interface.bInterfaceSubClass == 2: # VideoStreaming
            #             self.vs_interface_num = interface.bInterfaceNumber
            #             print(f"[信息] 找到视频流接口 (VS): {self.vs_interface_num}")
            #             for ep in interface:
            #                 print(f"  --- 备用设置 #{ep.bAlternateSetting} ---")
            #                 print(f"  该设置的 bNumEndpoints: {ep.bNumEndpoints}")
            #                 if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
            #                     self.vs_endpoint_addr = ep.bEndpointAddress
            #                     print(f"[信息]   - 找到数据输入端点 (Endpoint): 0x{self.vs_endpoint_addr:02x}")
            #                     break 
        except Exception as e:
            self.last_error = str(e)
            print(f"[失败] {self.last_error}")
            return False
        
        response = self.send_xu_control_command(GET_CUR, UNIT_ID, cs_id = 0x04, data=None, length=4)
        protocol_version = response.tobytes().decode('utf-8', 'ignore').strip('\x00')
        if(protocol_version != "2.0"):
            self.last_error = f"协议版本不正确: {protocol_version}"
            print(f"[失败] {self.last_error}")
            return False
        print(f"[信息] 协议版本: {protocol_version}")
        print(f"[信息] 连接成功")
        self.is_connected = True
        return True
    
    def set_time(self):
        try:
            lenserp = self.send_xu_control_command(GET_LEN, UNIT_ID, cs_id=0x05, length=2)
            payload_switch_set_time = bytearray([0x01, 0x05])
            self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id = 0x05, data=payload_switch_set_time) #切换到校时功能

            lenserp = self.send_xu_control_command(GET_LEN, UNIT_ID, cs_id=0x01, length=2)
            millisecond_cur = datetime.now().microsecond // 1000
            second_cur = datetime.now().second
            minute_cur = datetime.now().minute
            hour_cur = datetime.now().hour

            payload_set_time = struct.pack('<HBBBBBH', millisecond_cur, second_cur, minute_cur, hour_cur, 0, 0, 0)

            self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id = 0x01, data=payload_set_time) 
            return True
        except Exception as e:
            self.last_error = str(e)
            print(f"[失败] {self.last_error}")
            return False


    
    def disconnect(self):
        if self.is_connected:
            try:
                print("[信息]正在发送指令以停止数据流……")
                payload_switch_to_stream_type = bytearray([0x03, 0x05])
                self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id = 0x05, data=payload_switch_to_stream_type)

                payload_set_stream_to_mjpeg = bytearray([0x01,0x05])
                self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id = 0x03, data=payload_set_stream_to_mjpeg)

                print("[信息]码流已切换回默认模式")
                time.sleep(0.1)
            except usb.core.USBError as e:
                self.last_error = f"{e}"
                print(f"[失败] {self.last_error}")
        if self.device:
            usb.util.dispose_resources(self.device)
            self.device = None
            self.is_connected = False
            print(f"[信息] 已断开连接")
        else:
            print(f"[警告] 未连接任何设备")
        
    def send_xu_control_command(self, bRequest, unit_id, cs_id, data=None, length=None):
        # 通用的命令发送函数
        if usb.util.endpoint_direction(bRequest) == usb.util.ENDPOINT_OUT: # Host to Device
            bmRequestType = 0x21
            payload = data
        else: # Device to Host
            bmRequestType = 0xA1
            payload = length
        wValue = (cs_id << 8)
        wIndex = (unit_id << 8) | self.vc_interface_num
        return self.device.ctrl_transfer(bmRequestType, bRequest, wValue, wIndex, payload)
    
    def read_from_vs_endpoint(self, size, timeout=1000):
        if not self.is_connected:
            self.last_error = "未连接到设备"
            print(f"[失败] {self.last_error}")
            return None
        
        data = bytearray()
        bytes_read = 0
        while bytes_read < size:
            try:
                chunk = self.device.read(self.vs_endpoint_addr, size - bytes_read, timeout)
                if not chunk:
                    print(f"[警告] 读取超时，已读取 {bytes_read} 字节")
                    break
                
                data.extend(chunk)
                bytes_read += len(chunk)
            except usb.core.USBError as e:
                self.last_error = f"从端点 0x{self.vs_endpoint_addr:02x} 读取数据失败: {e}"
                print(f"[失败] {self.last_error}")
                raise e
        return data if bytes_read >= size else None
    
    def start_stream(self):
        if not self.is_connected:
            self.last_error = "未连接到设备"
            print(f"[失败]{self.last_error}")
            return None
        try:
            lenserp = self.send_xu_control_command(GET_LEN, UNIT_ID, cs_id=0x05, length=2)
            payload_switch_to_thermometry = bytearray([0x03, 0x01])
            self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id=0x05, data=payload_switch_to_thermometry)

            lenserp = self.send_xu_control_command(GET_LEN, UNIT_ID, cs_id=0x03, length=2)
            payload_enable_thermometry = bytearray([0x01, 0x01]) # Channel 1, enabled=1
            self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id=0x03, data=payload_enable_thermometry)
            time.sleep(0.1)

            lenserp = self.send_xu_control_command(GET_LEN, UNIT_ID, cs_id=0x05, length=2)
            payload_switch_to_thermometry_mode = bytearray([0x03, 0x02])
            self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id = 0x05, data=payload_switch_to_thermometry_mode)

            lenserp = self.send_xu_control_command(GET_LEN, UNIT_ID, cs_id=0x03, length=2)
            payload_set_thermometry_mode = bytearray([0x01, 0x02]) # Channel 1, mode=2
            self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id=0x03, data=payload_set_thermometry_mode)
            time.sleep(0.1)

            lenserp = self.send_xu_control_command(GET_LEN, UNIT_ID, cs_id=0x05, length=2)
            payload_switch_to_stream_type = bytearray([0x03, 0x05])
            self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id=0x05, data=payload_switch_to_stream_type)

            lenserp = self.send_xu_control_command(GET_LEN, UNIT_ID, cs_id=0x03, length=2)
            payload_set_stream_type = bytearray([0x01, 0x08]) # Channel 1, streamType=8
            self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id=0x03, data=payload_set_stream_type)
            time.sleep(0.1)

            self.clear_endpoint_buffer()

            return True
        except Exception as e:
            print(f"[初始化失败]{e}")
            return False
    def read_next_frame(self):
        if not self.is_connected:
            return None
        
        try:
            raw_len = self.read_from_vs_endpoint(1, timeout = 1000)
            if not raw_len: return None
            uvc_len = raw_len[0]
            if uvc_len > 1:
                self.read_from_vs_endpoint(uvc_len - 1, timeout= 1000)
            header = self.read_from_vs_endpoint(HEADER_SIZE, timeout=1000)
            if not header or len(header) < HEADER_SIZE:
                return None
            
            stream_len, = struct.unpack_from('<I', header, 12)
            yuv_len, = struct.unpack_from('<I', header, 96)

            if stream_len <= 0 or yuv_len <= 0:
                return None
            
            data_body = self.read_from_vs_endpoint(stream_len, timeout=1000)
            yuv_body = self.read_from_vs_endpoint(yuv_len, timeout=1000)

            if data_body and yuv_body:
                return header + data_body + yuv_body
            
            return None
        except Exception as e:
            self.last_error = f"[错误]{e}"
            return None

    # def _read_uvc_packet(self, size, timeout=1000):
        # try:
            # raw_header_len = self.read_from_vs_endpoint(1, timeout)
            # if not raw_header_len:
                # self.last_error = "获取UVC头长度失败"
                # print(f"[失败] {self.last_error}")
                # return None
            # uvc_header_len = raw_header_len[0]

            # if uvc_header_len > 1:
                # self.read_from_vs_endpoint(uvc_header_len - 1, timeout)
            
            # print(f"[信息]已剥离UVC头长度{uvc_header_len}字节的UVC头")
            # data = bytearray()
            # read_count = 0
            # while read_count < size:
                # chunk = self.device.read
    # def get_next_frame(self):
    #     if not self.is_connected:
    #         self.last_error = "未连接到设备"
    #         print(f"[失败] {self.last_error}")
    #         return None
    #     try:
    #     # --- 步骤 1: 开启测温功能 ---
    #     # 1a. 预告: 告诉设备，下一步要操作的是 "测温基本参数配置" (CS=0x03, Sub=0x01)
    #         print("[步骤1] 预告: 将操作'测温基本参数配置'...")
    #         lenserp = self.send_xu_control_command(GET_LEN, UNIT_ID, cs_id=0x05, length=2)
    #         payload_switch_to_thermometry = bytearray([0x03, 0x01])
    #         self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id=0x05, data=payload_switch_to_thermometry)

    #     # 1b. 执行: 发送开启测温的指令
    #         print("[步骤1.5] 执行: 开启测温功能...")
    #         lenserp = self.send_xu_control_command(GET_LEN, UNIT_ID, cs_id=0x03, length=2)
    #         payload_enable_thermometry = bytearray([0x01, 0x01]) # Channel 1, enabled=1
    #         self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id=0x03, data=payload_enable_thermometry)
    #         print("[信息] 测温功能已开启")
    #         time.sleep(0.1)

    #         print("[步骤2]预告:将操作'测温模式配置'")
    #         lenserp = self.send_xu_control_command(GET_LEN, UNIT_ID, cs_id=0x05, length=2)
    #         payload_switch_to_thermometry_mode = bytearray([0x03, 0x02])
    #         self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id = 0x05, data=payload_switch_to_thermometry_mode)

    #         print("[步骤2.5] 执行: 配置测温模式为'专家模式'")
    #         lenserp = self.send_xu_control_command(GET_LEN, UNIT_ID, cs_id=0x03, length=2)
    #         payload_set_thermometry_mode = bytearray([0x01, 0x02]) # Channel 1, mode=1
    #         self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id=0x03, data=payload_set_thermometry_mode)
    #         print("[信息] 测温模式已配置为'专家模式'")
    #         time.sleep(0.1)

    #     # --- 步骤 2: 配置码流类型 ---
    #     # 2a. 预告: 告诉设备，下一步要操作的是 "实时上传码流类型配置" (CS=0x03, Sub=0x05)
    #         print("[步骤3] 预告: 将操作'实时上传码流类型配置'...")
    #         lenserp = self.send_xu_control_command(GET_LEN, UNIT_ID, cs_id=0x05, length=2)
    #         payload_switch_to_stream_type = bytearray([0x03, 0x05])
    #         self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id=0x05, data=payload_switch_to_stream_type)
        
    #     # 2b. 执行: 发送设置码流类型的指令
    #         print("[步骤3.5] 执行: 配置码流类型为‘全屏测温数据+YUV'...")
    #         lenserp = self.send_xu_control_command(GET_LEN, UNIT_ID, cs_id=0x03, length=2)
    #         payload_set_stream_type = bytearray([0x01, 0x08]) # Channel 1, streamType=8
    #         self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id=0x03, data=payload_set_stream_type)
    #         print("[信息] 码流类型已配置为'全屏测温数据+YUV'")
    #         time.sleep(0.1)

    #         print("[步骤4] 同步数据流,丢弃UVC负载头...")
    #         uvc_header = self.read_from_vs_endpoint(4, timeout=500)
    #         uvc_header_len = uvc_header[0]
    #         if uvc_header_len is None:
    #             self.last_error = "同步UVC头长度失败"
    #             print(f"[失败] {self.last_error}")
    #             return None
    #         print(f"[信息] 已丢弃 {uvc_header_len} 字节的UVC头")

    #         print("[步骤5] 读取一帧热成像数据...")
    #         header = self.read_from_vs_endpoint(HEADER_SIZE, timeout=500)
    #         print(f"[信息] 读取到 {len(header)} 字节的帧头")
    #         magic_number, = struct.unpack_from('<I', header, offset=0)
    #         print(f"[信息] 帧头中的魔数: 0x{magic_number:08x}")

    #         if header is None or len(header) < HEADER_SIZE:
    #             self.last_error = "读取帧头失败或长度不足"
    #             return None
            

    #         stream_len, = struct.unpack_from('<I', header, offset=12)
    #         if stream_len <= 0:
    #             self.last_error = f"无效的流长度: {stream_len}"
    #             return None
            
    #         YUV_len, = struct.unpack_from('<I', header, offset=96)
    #         if YUV_len <= 0:
    #             self.last_error = f"无效的YUV长度: {YUV_len}"
    #             return None
            

    #         data_body = self.read_from_vs_endpoint(stream_len, timeout=500)
    #         if data_body is None or len(data_body) < stream_len:
    #             self.last_error = "读取帧数据失败或长度不足"
    #             return None
            
    #         YUV_body = self.read_from_vs_endpoint(YUV_len, timeout=500)
    #         if YUV_body is None or len(YUV_body) < YUV_len:
    #             self.last_error = "读取YUV数据长度不够"
    #             return None

    #         full_frame = header + data_body + YUV_body
    #         return full_frame
    #     except Exception as e:
    #         self.last_error = f"在 get_thermal_frame 中发生未知错误: {e}"
    #         print(f"[失败] {self.last_error}")
    #         return None
        
    def clear_endpoint_buffer(self):
        print("[清理]正在清空残留缓冲区.....")
        try:
            while True:
                self.device.read(self.vs_endpoint_addr, 1024*16, timeout=10)
        except usb.core.USBError:
            pass

        print("[清理]缓冲区已清空")

if __name__ == "__main__":
    print("--- 海康摄像头连接测试程序 ---")
    camera = HikCamera(vendor_id = 0x2BDF, product_id = 0x0102)
    if camera.connect():
        print(f"[成功] 连接成功")
        camera.set_time()
        camera.clear_endpoint_buffer()
        if camera.start_stream():
            print("视频流启动成功,按'q'退出")

            try:
                while True:
                    full_frame = camera.read_next_frame()

                    if full_frame:
                        thermal_matrix = unpack_thermal_frame(full_frame)
                        np.savetxt('temperature.csv', thermal_matrix, delimiter=',', fmt='%.2f')

                        create_thermal_image('temperature.csv')
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break
                    else:
                        pass
            except KeyboardInterrupt:
                pass
            finally:
                camera.disconnect()
                cv2.destroyAllWindows()
    else:
        print(f"[失败] {camera.last_error}")
    
    camera.disconnect()
    print("\n--- 测试程序结束 ---")
    