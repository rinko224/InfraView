import cv2
import time

# =================== 用户配置 ===================
CAMERA_INDEX = 1 
# ===============================================

print("--- 终极诊断脚本 V2 ---")
print("目标：检查摄像头数据流是否曾经发生过变化。")
print("本脚本不会显示图像，请观察命令行输出。")

# 关键1：强制使用 DSHOW 后端
cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)

if not cap.isOpened():
    print(f"\n[致命错误] 无法打开摄像头索引 {CAMERA_INDEX}。程序退出。")
    exit()

print(f"\n[成功] 摄像头已打开。")
# 关键2：完全不使用任何 cap.set() 命令，让摄像头使用其最默认的模式工作。
print("[信息] 未设置任何参数，使用摄像头默认模式。")

print("\n--- 开始长时间帧分析 (将检测 500 帧) ---")
print("如果没有输出，说明所有帧的数据都是统一的。如果数据有变化，会立即打印信息。")

found_dynamic_frame = False

try:
    for i in range(500): # 循环读取大量帧
        ret, frame = cap.read()
        
        if not ret or frame is None:
            # 每隔50帧打印一次错误，避免刷屏
            if i % 50 == 0:
                print(f"第 {i+1} 帧: 读取失败 (ret=False)。")
            time.sleep(0.1)
            continue

        # 转换为灰度图进行分析
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 检查灰度图的最大值和最小值
        min_val, max_val, _, _ = cv2.minMaxLoc(gray_frame)
        
        # 这是整个脚本的核心：检查数据是否有动态范围
        if min_val != max_val:
            print(f"\n\n[!!! 重大发现 !!!] 在第 {i+1} 帧检测到动态数据！")
            print(f"    - 最小值: {min_val}")
            print(f"    - 最大值: {max_val}")
            print("    - 这意味着摄像头开始输出有效数据了！问题可能在于初始化时间过长。")
            found_dynamic_frame = True
            break # 找到后即可退出循环
        
        # 每隔 20 帧打印一次状态，让我们知道程序在运行
        if (i + 1) % 20 == 0:
            print(f"已分析 {i+1} 帧... 数据仍然是统一的 (所有像素值都等于 {min_val})。")
            
    # 循环结束后的总结
    print("\n--- 诊断结束 ---")
    if not found_dynamic_frame:
        print("[结论] 在分析了 500 帧之后，所有成功读取的帧内容都是完全统一的。")
        print("      这强烈表明 OpenCV 的 VideoCapture 无法正确解码此摄像头的数据流。")

finally:
    cap.release()
    print("摄像头已释放。")