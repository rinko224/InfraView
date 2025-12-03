# component/main_ui.py
from PySide2.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QSpinBox
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
from .matrix_util import process_thermal_for_display
from .display_util import theraml_point_rotate

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
        self.measure_pos = None
        self.measure_info = ""
        self.area_max_temp = None
        self.area_min_temp = None
        self.measure_h = None
        self.measure_w = None
        self.color_mode = "inferno"
        self.nodes = None

        # ——— 左边视频区域 ———
        self.video_label = self.ui.findChild(QLabel, "video_label")
        self.video_label.setMinimumSize(1, 1) 
        self.video_label.setStyleSheet("background:black;")

        self.video_label.setMouseTracking(False)
        self.video_label.installEventFilter(self)

        # ——— 右侧信息面板 ———
        self.info_label = self.ui.findChild(QLabel, "info")
        self.info_label.setMinimumSize(1, 1) 
        self.info_label.setStyleSheet("background:#222; color:white; font-size:18px; padding:10px;")

        # ——— 旋转按钮 ———
        self.rotate_button = self.ui.findChild(QPushButton, "rotate")
        self.rotate_button.clicked.connect(self.rotate_video)

        # ——— 伪彩模式设置按钮 ———
        self.color_set = self.ui.findChild(QPushButton, "color_mode")
        self.color_set.clicked.connect(self.set_color_map)

        # ——— 区域测量相关 ———
        self.measure_ensure = self.ui.findChild(QPushButton, "measure_ensure")
        self.measure_ensure.clicked.connect(self.ensure_measure)

        self.measure_area_h_edit = self.ui.findChild(QSpinBox, "measure_h")
        self.measure_area_w_edit = self.ui.findChild(QSpinBox, "measure_w")

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
        display_img = process_thermal_for_display(thermal, out_size, self.rotation_angle, self.color_mode, self.nodes)

        self._process_measurement(thermal, display_img, self.measure_h, self.measure_w)
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
            if self.area_max_temp is not None and self.area_min_temp is not None:
                text += f"{self.measure_info}\n"
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

    def _process_measurement(self, thermal, display_img, measure_h, measure_w):
        self.measure_info = ""

        if self.measure_pos is None:
            return
        raw_h, raw_w = thermal.shape
        norm_x, norm_y = self.measure_pos
        h, w = display_img.shape[:2]

        rx, ry = 0, 0
        if self.rotation_angle == 0:
            rx = int(norm_x * raw_w)
            ry = int(norm_y * raw_h)
        elif self.rotation_angle == 90:
            rx = int(norm_y * raw_w)
            ry = int((1 - norm_x) * raw_h)
        elif self.rotation_angle == 180:
            rx = int((1 - norm_x) * raw_w)
            ry = int((1 - norm_y) * raw_h)
        elif self.rotation_angle == 270:
            rx = int((1 - norm_y) * raw_w)
            ry = int(norm_x * raw_h)

        rx = max(0, min(raw_w - 1, rx))
        ry = max(0, min(raw_h - 1, ry))

        y1, y2 = max(0, ry-measure_h//2), min(raw_h, ry+measure_h//2)
        x1, x2 = max(0, rx-measure_w//2), min(raw_w, rx+measure_w//2)

        measure_area = thermal[y1:y2, x1:x2]
        
        if measure_area.size > 0:
            temp_max = np.percentile(measure_area.flatten(),98)
            temp_min = np.min(measure_area)
            self.area_max_temp = temp_max
            self.area_min_temp = temp_min
            self.measure_info = f"Max Temp: {temp_max:.2f}°C\nMin Temp: {temp_min:.2f}°C"

            corners_thermal = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
            display_corners = [theraml_point_rotate(self.rotation_angle, tx, ty, raw_w, raw_h, w, h) for (tx, ty) in corners_thermal]
            
            xs = [c[0] for c in display_corners]
            ys = [c[1] for c in display_corners]
            disp_x1, disp_x2 = min(xs), max(xs)
            disp_y1, disp_y2 = min(ys), max(ys)

            cv2.rectangle(display_img, (disp_x1 , disp_y1), (disp_x2, disp_y2), (0, 255, 0), 2)
            
            center_tx = (x1 + x2) / 2.0
            center_ty = (y1 + y2) / 2.0
            label_x, label_y = theraml_point_rotate(self.rotation_angle, center_tx, center_ty, raw_w, raw_h, w, h)
            cv2.putText(display_img, f"{temp_max:.1f}", (label_x + 10, label_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
    def mousePressEvent(self, event):
        child = self.childAt(event.pos())

        if child == self.video_label:
            local_pos = self.video_label.mapFrom(self, event.pos())
            self.measure_pos = (local_pos.x() / self.video_label.width(), #相对坐标
                                local_pos.y() / self.video_label.height())
        super().mousePressEvent(event)

    def ensure_measure(self):
        self.measure_h = self.measure_area_h_edit.value()
        self.measure_w = self.measure_area_w_edit.value()
    
    def set_color_map(self, color_mode):
        self.color_mode = color_mode


        