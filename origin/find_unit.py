# 文件名: uvc_discover.py

import sys

try:
    import uvc
except ImportError:
    print("错误: uvc 库未安装。请运行 'pip install python-uvc'")
    sys.exit(1)

# ========================== 用户配置 ==========================
# 确保这里的VID和PID与你的设备匹配
VENDOR_ID = 0x2BDF
PRODUCT_ID = 0x0102
# ============================================================

def main():
    print("--- UVC 设备侦察脚本 ---")
    
    print("\n[步骤 1] 正在扫描UVC设备...")
    devices = uvc.device_list()
    print(f"       扫描完成，找到 {len(devices)} 个设备。")

    target_device_info = None
    for device in devices:
        if device['idVendor'] == VENDOR_ID and device['idProduct'] == PRODUCT_ID:
            target_device_info = device
            break
        
    if not target_device_info:
        print(f"\n[错误] 未找到指定的设备 (VID=0x{VENDOR_ID:04x}, PID=0x{PRODUCT_ID:04x})。")
        return

    print(f"\n[步骤 2] 成功匹配到设备，正在打开...")
    print(f"       设备信息: {target_device_info}")

    capture = None
    try:
        capture = uvc.Capture(target_device_info['uid'])
        print(f"[成功] 设备已打开: {capture.name}")

        # --- 核心侦察部分 ---

        print("\n\n--- [侦察报告] 设备上的所有 'Controls' ---")
        if not capture.controls:
            print("       未发现任何控件。")
        else:
            # 遍历并打印每个控件的详细信息
            for i, ctrl in enumerate(capture.controls):
                print(f"\n--- 控件 #{i+1} ---")
                try:
                    # ctrl.display_name 是必须有的
                    print(f"  Display Name: '{ctrl.display_name}'")
                    # ctrl.unit 是我们最关心的
                    print(f"  Unit ID: {ctrl.unit}")
                    print(f"  Selector: {ctrl.selector}")
                    # 其他一些可能有用的属性
                    print(f"  Interface Number: {ctrl.interface_num}")
                    # 尝试打印控件的当前值，可能会失败，所以用try-except包裹
                    try:
                        print(f"  Current Value: {ctrl.value}")
                    except Exception as e:
                        print(f"  Current Value: (获取失败 - {e})")
                except Exception as e:
                    print(f"  (无法解析此控件的详细信息: {e})")
        
        # python-uvc 库没有直接暴露 Units 列表的公共API，
        # 但控件的 unit 属性已经给了我们最重要的信息。

        print("\n\n--- [侦察结论] ---")
        print("请仔细检查上面列出的所有控件的 'Unit ID'。")
        print("我们需要找到一个看起来像是用于私有协议的扩展单元。")
        print("它的 Display Name 可能是 'Extension Unit' 或未知名称。")
        print("找到那个可疑的 Unit ID 后，请用它替换主程序中的 `UNIT_ID = 10`。")

    except Exception as e:
        print(f"\n[错误] 在操作设备时发生异常: {e}")
    
    finally:
        if capture:
            # 释放设备
            del capture
            print("\n设备已释放。")

if __name__ == "__main__":
    main()