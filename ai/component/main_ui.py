# component/main_ui.py
from PySide2.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PySide2.QtCore import QTimer, Qt, QFile
from PySide2.QtGui import QImage, QPixmap
from PySide2.QtUiTools import QUiLoader
import cv2
import numpy as np
import time
import torch


# 引用组件
from . import config
from . import preprocess
from .model_detector import CustomTinyYOLO
from .model_recognizer import MobileFaceNet_Thermal
from .database_manager import FaceLibrary

# 引用您提供的驱动文件 (注意文件名已改为 driver_*)
from .driver_camera import HikCamera
from .driver_util import unpack_thermal_frame
from .viz_heatmap import process_thermal_for_display

loader = QUiLoader()
class MainUI(QWidget):
    def __init__(self):
        super().__init__()

        ui_file = QFile("component/ui/display.ui")
        ui_file.open(QFile.ReadWrite)
        self.ui = loader.load(ui_file, self)
        ui_file.close()

        self.setWindowTitle("Thermal Recognition System")
        self.resize(900, 500)

        # ——— 一些基本属性 ———
        self.rotation_angle = 0

        # ——— 左边视频区域 ———
        self.video_label = self.ui.findChild(QLabel, "video_label")
        self.video_label.setMinimumSize(1, 1) 
        self.video_label.setStyleSheet("background:black;")

        # ——— 右侧信息面板 ———
        self.info_label = self.ui.findChild(QLabel, "info")
        self.info_label.setMinimumSize(1, 1) 
        self.info_label.setStyleSheet("background:#222; color:white; font-size:18px; padding:10px;")

        # ——— 旋转按钮 ———
        self.rotate_button = self.ui.findChild(QPushButton, "rotate")
        self.rotate_button.clicked.connect(self.rotate_video)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0) 
        layout.addWidget(self.ui)

        self.video_label.setScaledContents(True)

        self.init_system()
        self.start_timer()
    
    def init_system(self):
        self.detector = CustomTinyYOLO()
        self.recognizer = MobileFaceNet_Thermal()
        self.db = FaceLibrary()

        self.camera = HikCamera(vendor_id=0x2BDF, product_id=0x0102)
        if not self.camera.connect():
            print("相机打开失败")
            return
        self.camera.start_stream()
        self.prev_time = time.time()
        self.last_embedding = None
    
    def start_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)  # 30ms 刷新一次
    def update_frame(self):
        # ——— 计算 FPS ———
        now = time.time()
        fps = 1 / (now - self.prev_time)
        self.prev_time = now

        # ——— 读取热成像数据 ———
        full_frame = self.camera.read_next_frame()
        if full_frame is None:
            return

        thermal = unpack_thermal_frame(full_frame)
        if thermal is None:
            return
        
        w = self.video_label.width()
        h = self.video_label.height()
        out_size = (w, h)

        # ——— 生成展示图（彩色） ———
        display_img = process_thermal_for_display(thermal, out_size, self.rotation_angle)

        # ——— 生成 AI 图（灰度增强） ———
        ai_img = preprocess.ai_normalization(thermal)

        # ========== 模拟检测过程 ==========
        boxes = self.detector.detect_dummy(ai_img.shape)
        current_result = None

        if boxes:
            x1, y1, x2, y2, conf = boxes[0]
            cv2.rectangle(display_img, (x1, y1), (x2, y2), (255,255,255), 2)

            embedding = self.recognizer.extract_dummy(ai_img)
            self.last_embedding = embedding

            name, score = self.db.identify(embedding)
            current_result = (name, score)

        # ——— 用 QLabel 显示左侧图像 ———
        qimg = self.numpy_to_qimage(display_img)
        self.video_label.setPixmap(QPixmap.fromImage(qimg))

        # ——— 更新右侧识别信息 ———
        if current_result:
            name, score = current_result
            text = f"FPS: {fps:.1f}\n\n"
            text += f"ID: {name}\n"
            text += f"Conf: {score:.2f}\n"
        else:
            text = f"FPS: {fps:.1f}\n\nSearching..."

        self.info_label.setText(text)

    # ========== numpy → QImage ==========
    def numpy_to_qimage(self, img):
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        return QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()
    
    def rotate_video(self):
        self.rotation_angle += 90
        self.rotation_angle %= 360

def draw_ui(frame_display, results, fps):
    """
    绘制前端 UI：左边是热成像图，右边是信息面板
    """
    # 创建一个 800x400 的大画布
    canvas_height = 400
    canvas_width = 800
    canvas = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)

    # 1. 左侧：放置热成像画面 (缩放到 400x300)
    if frame_display is not None:
        disp_h, disp_w = frame_display.shape[:2]
        # 保持比例缩放
        scale = min(400/disp_w, 400/disp_h)
        new_w, new_h = int(disp_w * scale), int(disp_h * scale)
        resized_frame = cv2.resize(frame_display, (new_w, new_h))
        
        # 居中放置在左半边 (0-400)
        y_offset = (canvas_height - new_h) // 2
        x_offset = (400 - new_w) // 2
        canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized_frame

    # 2. 右侧：信息面板
    # 绘制分割线
    cv2.line(canvas, (400, 0), (400, 400), (100, 100, 100), 2)
    
    # 绘制文字
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(canvas, "SYSTEM STATUS", (420, 40), font, 0.8, (0, 255, 0), 2)
    cv2.putText(canvas, f"FPS: {fps:.1f}", (420, 80), font, 0.6, (200, 200, 200), 1)
    
    cv2.putText(canvas, "RECOGNITION:", (420, 140), font, 0.7, (0, 255, 255), 2)
    
    if results:
        name, score, box = results
        color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
        cv2.putText(canvas, f"ID: {name}", (420, 180), font, 0.8, color, 2)
        cv2.putText(canvas, f"Conf: {score:.2f}", (420, 220), font, 0.6, (200, 200, 200), 1)
    else:
        cv2.putText(canvas, "Searching...", (420, 180), font, 0.8, (100, 100, 100), 2)

    return canvas

def start_system():
    print("--- 启动热成像识别系统 ---")
    
    # 1. 初始化模型
    detector = CustomTinyYOLO()
    recognizer = MobileFaceNet_Thermal()
    db = FaceLibrary()
    
    # 注意：此处应加载 .pth 权重
    # try:
    #     detector.load_state_dict(torch.load(config.DETECTOR_PATH))
    #     recognizer.load_state_dict(torch.load(config.RECOGNIZER_PATH))
    # except:
    #     print("[警告] 未找到权重文件，将运行在演示模式")

    # 2. 初始化相机
    camera = HikCamera(vendor_id=0x2BDF, product_id=0x0102)
    if not camera.connect():
        return
    camera.start_stream()
    
    # 3. 主循环
    prev_time = time.time()
    
    try:
        while True:
            # 计算FPS
            curr_time = time.time()
            fps = 1 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0
            prev_time = curr_time

            # A. 获取数据
            full_frame = camera.read_next_frame()
            if not full_frame:
                continue
                
            thermal_matrix = unpack_thermal_frame(full_frame)
            if thermal_matrix is None:
                continue

            # B. 处理用于显示的图像 (彩色热力图)
            # 使用 viz_heatmap 中的逻辑生成给左侧框看的图
            display_img = process_thermal_for_display(thermal_matrix)

            # C. 处理用于 AI 的图像 (增强灰度图)
            ai_img = preprocess.ai_normalization(thermal_matrix)
            
            # D. 核心流程：检测 -> 识别
            # 1. 假装检测到了人脸 (模拟检测器输出)
            # 实际应为: boxes = detector(ai_img)
            boxes = detector.detect_dummy(ai_img.shape) 
            
            current_result = None
            
            if boxes:
                # 取第一个框
                x1, y1, x2, y2, conf = boxes[0]
                
                # 2. 在显示图上画框
                cv2.rectangle(display_img, (x1, y1), (x2, y2), (255, 255, 255), 2)
                
                # 3. 抠图并识别
                # 实际应为: embedding = recognizer(cropped_face)
                embedding = recognizer.extract_dummy(ai_img) 
                
                # 4. 数据库比对
                name, score = db.identify(embedding)
                current_result = (name, score, (x1, y1, x2, y2))

            # E. 绘制 UI 并显示
            final_ui = draw_ui(display_img, current_result, fps)
            cv2.imshow("Thermal Recognition System", final_ui)

            # 注册功能 (按 'r' 键将当前人注册为 User_Timestamp)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r') and current_result:
                new_name = f"User_{int(time.time())}"
                # 这里的 embedding 应该是最近一次提取的特征
                db.register_person(new_name, embedding)

    finally:
        camera.disconnect()
        cv2.destroyAllWindows()
        print("--- 系统关闭 ---")