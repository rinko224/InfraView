import usb.core
import usb.util
import platform
import usb.backend.libusb1
import os

# --- 配置区域 ---
VENDOR_ID = 0x2BDF
PRODUCT_ID = 0x0102
LIBUSB_PATH = "libusb-1.0.dll"

def hexdump(data, length=256):
    """
    一个漂亮的十六进制打印函数。
    """
    print(f"--- 数据预览 (前 {min(len(data), length)} 字节) ---")
    
    # 每行显示16个字节
    for i in range(0, min(len(data), length), 16):
        # 1. 偏移量
        line = f"{i:08x} : "
        
        # 2. 十六进制部分
        hex_part = ' '.join(f"{byte:02x}" for byte in data[i:i+16])
        line += f"{hex_part:<48} " # 左对齐，总宽度48
        
        # 3. ASCII可打印字符部分
        ascii_part = ''.join(chr(byte) if 32 <= byte < 127 else '.' for byte in data[i:i+16])
        line += f"|{ascii_part}|"
        
        print(line)
    print("----------------------------------------")

# --- 主程序 ---
dev = None
try:
    # (之前的初始化代码保持不变)
    backend = usb.backend.libusb1.get_backend(find_library=lambda x: LIBUSB_PATH)
    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID, backend=backend)
    if dev is None: raise ValueError('摄像头没找到！')
    if platform.system() == "Windows": dev.set_configuration()
    else:
        if dev.is_kernel_driver_active(0): dev.detach_kernel_driver(0)
        dev.set_configuration()
    print("摄像头已配置成功！")

    # (发送控制命令的代码保持不变)
    dev.ctrl_transfer(0x21, 0x01, 0x0305, 0x0A00, bytes([0x00, 0x02]))
    print("命令已发送：请求'全屏测温数据'流。")
    
    endpoint = dev[0][(1,0)][0]
    print(f"数据端点地址: {hex(endpoint.bEndpointAddress)}")

    # --- 核心：读取并打印原始数据 ---
    print("\n--- 正在读取原始数据流... ---")
    
    # 我们读取一大块数据，希望能捕获到至少一个完整的帧头
    read_size = 4096 
    
    try:
        data = endpoint.read(read_size, timeout=2000)
        
        if data:
            print(f"\n成功读取到 {len(data)} 字节！")
            
            # 使用 hexdump 函数来“审视”这些数据
            hexdump(data)
            
            # --- 手动分析时间 ---
            print("\n请将上面的十六进制输出，与开发指南附录B中的所有帧头格式进行比对。")
            print("特别注意开头的几个字节，它们是不是某个'Magic Number'？")
            print("例如，B.1.1格式的魔术数字是 0x70827773 (小端字节序下，显示为 73 77 82 70)")
            print("B.2.1格式的魔术数字是 0x050508e7 (小端字节序下，显示为 e7 08 05 05)")
            
        else:
            print("\n[失败] 未能读取到任何数据。")
            
    except usb.core.USBError as e:
        if e.args == ('Operation timed out',):
            print("读取超时。摄像头可能没有在发送数据。")
        else:
            raise e

finally:
    if dev:
        usb.util.dispose_resources(dev)
        print("\n--- 资源已释放 ---")