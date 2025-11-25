import usb.core
import usb.util
import time
import logging
import struct
import cv2
import numpy as np
from datetime import datetime
from util import unpack_thermal_frame
from heatmap import process_thermal_for_display
from util import upack_YUV_frame

SET_CUR = 0x01 #设置类指令
GET_CUR = 0x81 #获取类指令
GET_LEN = 0x85 #获取长度类指令
UNIT_ID = 0x0A

HEADER_SIZE = 4636

logger = logging.getLogger("HikBackend")

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
                logger.error(f"{self.last_error}")
                return False
            
            self.device.set_configuration()
            self.config = self.device.get_active_configuration()
            
            vc_interface = usb.util.find_descriptor(self.config, bInterfaceClass=14, bInterfaceSubClass=1)
            vs_interface = usb.util.find_descriptor(self.config, bInterfaceClass=14, bInterfaceSubClass=2)

            if vc_interface is None or vs_interface is None:
                self.last_error = "未找到视频控制接口或视频流接口"
                logger.error(f"{self.last_error}")
                return False
            
            self.vs_interface_num = vs_interface.bInterfaceNumber
            logger.info(f"找到视频流接口 (VS): {self.vs_interface_num}")
            self.vc_interface_num = vc_interface.bInterfaceNumber
            logger.info(f"找到视频控制接口 (VC): {self.vc_interface_num}")

            active_alt_setting = None
            for iface in self.config.interfaces():
                if iface.bNumEndpoints > 0 and iface.bInterfaceNumber == self.vs_interface_num:
                    active_alt_setting = iface
                    break
                
            if active_alt_setting is None:
                self.last_error = "未找到有效视频流备用设置"
                logger.error(f"{self.last_error}")
                return False
            
            logger.info(f"找到视频流接口 (VS) 的有效备用设置: {active_alt_setting.bAlternateSetting}")

            for ep in active_alt_setting:
                if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
                    self.vs_endpoint_addr = ep.bEndpointAddress
                    break

            if self.vs_endpoint_addr is None:
                self.last_error = "未找到视频流数据输入端点"
                logger.error(f"{self.last_error}")
                return False
            
            alt_setting_num = active_alt_setting.bAlternateSetting

            logger.info(f"   - 找到活动备用设置: {alt_setting_num}")
            logger.info(f"   - 找到数据输入端点 (Endpoint): 0x{self.vs_endpoint_addr:02x}")

            logger.info(f"[步骤] 激活视频流接口 (VS) {self.vs_interface_num} -> 使用备用设置 {alt_setting_num}...")
            self.device.set_interface_altsetting(interface=self.vs_interface_num, alternate_setting=alt_setting_num)
            logger.info("视频流接口已激活")
            
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"{self.last_error}")
            return False
        
        response = self.send_xu_control_command(GET_CUR, UNIT_ID, cs_id = 0x04, data=None, length=4)
        protocol_version = response.tobytes().decode('utf-8', 'ignore').strip('\x00')
        if(protocol_version != "2.0"):
            self.last_error = f"协议版本不正确: {protocol_version}"
            logger.error(f"{self.last_error}")
            return False
        logger.info(f"协议版本: {protocol_version}")
        logger.info(f"连接成功")
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
            logger.info(f"当前时间: {hour_cur:02d}:{minute_cur:02d}:{second_cur:02d}.{millisecond_cur:03d}")
            return True
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"{self.last_error}")
            return False


    
    def disconnect(self):
        if self.is_connected:
            try:
                logger.info("正在发送指令以停止数据流……")
                payload_switch_to_stream_type = bytearray([0x03, 0x05])
                self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id = 0x05, data=payload_switch_to_stream_type)

                payload_set_stream_to_mjpeg = bytearray([0x01,0x05])
                self.send_xu_control_command(SET_CUR, UNIT_ID, cs_id = 0x03, data=payload_set_stream_to_mjpeg)

                logger.info("码流已切换回默认模式")
                time.sleep(0.1)
            except usb.core.USBError as e:
                self.last_error = f"{e}"
                logger.error(f"{self.last_error}")
        if self.device:
            usb.util.dispose_resources(self.device)
            self.device = None
            self.is_connected = False
            logger.info("已断开连接")
        else:
            logger.warning("未连接任何设备")
        
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
    
    def read_from_vs_endpoint(self, size, timeout=100):
        if not self.is_connected:
            self.last_error = "未连接到设备"
            logger.error(f"{self.last_error}")
            return None
        
        data = bytearray()
        bytes_read = 0
        while bytes_read < size:
            try:
                chunk = self.device.read(self.vs_endpoint_addr, size - bytes_read, timeout)
                if not chunk:
                    logger.warning(f"读取超时，已读取 {bytes_read} 字节")
                    break
                
                data.extend(chunk)
                bytes_read += len(chunk)
            except usb.core.USBError as e:
                self.last_error = f"从端点 0x{self.vs_endpoint_addr:02x} 读取数据失败: {e}"
                logger.error(f"{self.last_error}")
                raise e
        return data if bytes_read >= size else None
    
    def start_stream(self):
        if not self.is_connected:
            self.last_error = "未连接到设备"
            logger.error(f"{self.last_error}")
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
            self.last_error = f"[初始化失败]{e}"
            logger.error(f"{self.last_error}")
            return False
    def read_next_frame(self):
        if not self.is_connected:
            return None
        
        self.clear_endpoint_buffer()
        
        try:
            raw_len = self.read_from_vs_endpoint(1, timeout = 100)
            if not raw_len: return None
            uvc_len = raw_len[0]
            if uvc_len > 1:
                self.read_from_vs_endpoint(uvc_len - 1, timeout= 100)

            magic_buf = self.read_from_vs_endpoint(4, timeout=100)
            if not magic_buf: return None
            
            magic_val, = struct.unpack('<I', magic_buf)
            
            if magic_val != 0x70827773:
                logger.warning(f"[错位] 读到: 0x{magic_val:08x}，正在重新同步...")
                self.read_from_vs_endpoint(512, timeout=10) 
                return None
            header = self.read_from_vs_endpoint(HEADER_SIZE - 4, timeout=100)
            if not header:
                return None
            header = magic_buf + header
            
            stream_len, = struct.unpack_from('<I', header, 12)
            yuv_len, = struct.unpack_from('<I', header, 96)

            if stream_len <= 0 or yuv_len <= 0:
                return None
            
            data_body = self.read_from_vs_endpoint(stream_len, timeout=100)
            yuv_body = self.read_from_vs_endpoint(yuv_len, timeout=100)

            if data_body and yuv_body:
                return header + data_body + yuv_body
            
            return None
        except Exception as e:
            self.last_error = f"[读取错误]{e}"
            logger.error(f"{self.last_error}")
            return None

    def clear_endpoint_buffer(self):
        logger.info("[清理]正在清空残留缓冲区.....")
        try:
            while True:
                self.device.read(self.vs_endpoint_addr, 1024*16, timeout=10)
        except usb.core.USBError:
            pass

        print("[清理]缓冲区已清空")

if __name__ == "__main__":
    logger.info("--- 海康摄像头连接测试程序 ---")
    camera = HikCamera(vendor_id = 0x2BDF, product_id = 0x0102)
    if camera.connect():
        logger.info(f"[成功] 连接成功")
        camera.set_time()
        camera.clear_endpoint_buffer()
        if camera.start_stream():
            print("视频流启动成功,按'q'退出")

            try:
                while True:
                    full_frame = camera.read_next_frame()

                    if full_frame:
                        thermal_matrix = unpack_thermal_frame(full_frame)
                        if thermal_matrix is not None:
                            thermal_img = process_thermal_for_display(thermal_matrix)
                            if thermal_img is not None:
                                cv2.imshow("Thermal Stream", thermal_img)
                    else:
                        pass

                    if (cv2.waitKey(1) & 0xFF) == ord('q'):
                            break
            except KeyboardInterrupt:
                pass
            finally:
                camera.disconnect()
                cv2.destroyAllWindows()
    else:
        print(f"[失败] {camera.last_error}")
    
    camera.disconnect()
    print("\n--- 测试程序结束 ---")
    