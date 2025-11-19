# 文件名: final_and_correct.py

import usb.core
import usb.util
import sys
import time
import struct

# ========================== 用户配置 ==========================
VENDOR_ID = 0x2BDF
PRODUCT_ID = 0x0102
# ============================================================

def send_xu_control_command(dev, interface_num, unit_id, cs_id, data=None, length=None):
    """通用的命令发送函数"""
    if data is not None:
        bmRequestType = 0x21; bRequest = 0x01; payload = data
    else:
        bmRequestType = 0xa1; bRequest = 0x81; payload = length
    wValue = (cs_id << 8); wIndex = (unit_id << 8) | interface_num
    return dev.ctrl_transfer(bmRequestType, bRequest, wValue, wIndex, payload, timeout=1000)

def main():
    dev = None
    try:
        print("--- 最终数据流验证脚本 (已采用最终修正逻辑) ---")

        # --- 步骤 1: 查找设备 ---
        print("\n[步骤 1] 查找设备...")
        dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        if dev is None: raise ValueError("设备未找到")
        dev.set_configuration()
        config = dev.get_active_configuration()
        print("[成功] 设备已找到并配置。")

        # --- 步骤 2: 查找接口和端点 (使用绝对正确的遍历逻辑) ---
        print("\n[步骤 2] 查找接口和端点...")
        
        # 2.1 使用 find_descriptor 精确查找 VC 和 VS 接口
        vc_interface = usb.util.find_descriptor(config, bInterfaceClass=14, bInterfaceSubClass=1)
        if vc_interface is None: raise ValueError("视频控制(VC)接口未找到")
        vc_interface_num = vc_interface.bInterfaceNumber

        vs_interface = usb.util.find_descriptor(config, bInterfaceClass=14, bInterfaceSubClass=2)
        if vs_interface is None: raise ValueError("视频流(VS)接口未找到")
        
        # *** 这是最关键的、绝对正确的遍历方式 ***
        # 'Interface'对象可以通过数字索引访问其'AlternateSetting'
        vs_alt_setting = None
        vs_endpoint_addr = -1
        # len(vs_interface) 会返回 AlternateSetting 的数量
        for i in range(len(vs_interface)):
            setting = vs_interface[i] # 'setting' 现在绝对是一个 AlternateSetting 对象
            if setting.bNumEndpoints > 0:
                vs_alt_setting = setting
                vs_endpoint_addr = setting[0].bEndpointAddress
                break # 找到第一个有端点的就停止

        if vs_alt_setting is None:
            raise ValueError("在视频流接口中未找到任何可用的Alternate Setting")

        print(f"[成功] VC接口: {vc_interface_num}, VS接口: {vs_interface.bInterfaceNumber}, AltSetting: {vs_alt_setting.bAlternateSetting}, Endpoint: 0x{vs_endpoint_addr:02x}")
        
        # --- 步骤 3: 发送配置命令序列 (已验证成功) ---
        print("\n[步骤 3] 发送配置命令...")
        UNIT_ID = 0x0A
        send_xu_control_command(dev, vc_interface_num, UNIT_ID, cs_id=0x04, length=4)
        print("       -> 协议查询 OK")
        time.sleep(0.05)
        send_xu_control_command(dev, vc_interface_num, UNIT_ID, cs_id=0x05, data=b'\x03')
        print("       -> 功能切换 OK")
        time.sleep(0.05)
        send_xu_control_command(dev, vc_interface_num, UNIT_ID, cs_id=0x05, data=b'\x02')
        print("       -> 码流配置为类型 '2' (全屏测温) OK")
        time.sleep(0.05)
        print("[成功] 所有配置命令已发送。")
        
        # --- 步骤 4: 激活视频流接口 ---
        print("\n[步骤 4] 激活视频流接口...")
        dev.set_interface_altsetting(
            interface=vs_interface.bInterfaceNumber,
            alternate_setting=vs_alt_setting.bAlternateSetting
        )
        print("[成功] Alternate Setting 已设置。")

        # --- 步骤 5: 尝试读取数据流 ---
        print("\n[步骤 5] 尝试从端点读取数据 (超时5秒)...")
        read_size = vs_alt_setting[0].wMaxPacketSize * 500
        data = dev.bulk_read(vs_endpoint_addr, read_size, timeout=5000)
        
        print(f"\n[成功] 已从端点读取到 {len(data)} 字节的数据！")
        
        # --- 步骤 6: 解析并验证B.1.1头部 ---
        print("\n--- [步骤 6] 解析B.1.1数据头 (前132字节) ---")
        if len(data) < 132: raise ValueError(f"数据长度({len(data)})小于头部长度(132)")

        header = data[:132]
        magic_no = struct.unpack('<I', header[0:4])[0]
        header_size = struct.unpack('<I', header[4:8])[0]
        rt_data_type = struct.unpack('<I', header[16:20])[0]
        width = struct.unpack('<I', header[44:48])[0]
        height = struct.unpack('<I', header[48:52])[0]
        
        print("\n--- 头部关键字段验证 ---")
        print(f"  Magic Number: 0x{magic_no:08x} (手册期望: 0x70827773 'FRMI')")
        print(f"  Header Size: {header_size} (手册期望: 132)")
        print(f"  RT Data Type: {rt_data_type} (手册期望: 2 for '全屏测温结果数据')")
        print(f"  Width: {width}")
        print(f"  Height: {height}")
        
        print("\n[最终结论] 如果上面的值看起来都合理，我们已经成功接收到了正确格式的数据！")

    except Exception as e:
        print(f"\n[严重错误] 在执行过程中发生异常: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if dev:
            try: usb.util.release_interface(dev, vs_interface)
            except: pass
            dev.reset()
            print("[完成] 设备已释放。")

if __name__ == "__main__":
    main()