# component/main_ui.py
from PySide2.QtWidgets import QMainWindow, QLabel, QSpinBox, QComboBox, QMessageBox, QDialog, QSizePolicy, QPlainTextEdit, QAction, QShortcut, QPushButton, QWidget
from PySide2.QtCore import QTimer, Qt, QFile, QPoint
from PySide2.QtGui import QImage, QPixmap, QIcon, QKeySequence, QPainter, QPen, QColor, QBrush
from PySide2.QtUiTools import QUiLoader
import cv2
import numpy as np
import time
import datetime
import logging

# 引用组件
from . import config
# 确保这里引用的是最新的 theme_style.py
from .theme_style import PurpleTheme 
from .color_map_editor import ColorMapEditorDialog
from .color_map_manager import ColorMapManager
from .logger import GuiLogger, QtHandle

# 引用驱动与工具
from .driver_camera import HikCamera
from .driver_util import unpack_thermal_frame
from .matrix_util import process_thermal_for_display

loader = QUiLoader()

class MainUI(QMainWindow):
    MODE_POINT = 0
    MODE_RECT = 1

    def __init__(self):
        super().__init__()

        # 加载UI
        ui_file = QFile("component/ui/display.ui")
        ui_file.open(QFile.ReadWrite)
        self.ui = loader.load(ui_file)
        ui_file.close()
        self.setCentralWidget(self.ui)

        # ——— 基础窗口设置与美化 ———
        self.setWindowTitle("InfraView Thermal Analysis System")
        self.setWindowIcon(QIcon("icon.ico"))
        self.resize(1000, 650) 
        
        self.setStyleSheet(PurpleTheme.STYLE_SHEET)
       
        # 菜单栏
        menubar = self.menuBar()
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about_dialog)
        menubar.addAction(about_action)

        # ——— 属性初始化 ———
        self.rotation_angle = 0
        self.current_mode = self.MODE_POINT
        self.color_mode = "inferno"
        self.current_thermal_raw = None
        
        # ——— 鼠标交互相关 ———
        self.is_drawing = False
        self.start_pos_norm = None
        self.end_pos_norm = None
        self.point_pos_norm = None

        # ——— 控件绑定 ———
        self.video_label = self.ui.findChild(QLabel, "video_label")
        self.video_label.setMouseTracking(True)
        self.video_label.installEventFilter(self)
        self.video_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.video_label.setScaledContents(False)

        self.info_label = self.ui.findChild(QLabel, "info")
        # 设置初始提示文字
        self.info_label.setText(f"当前模式: 单点测温模式 (单击选点) | 按 Ctrl+M 切换")
        
        self.rotate_button = self.ui.findChild(QPushButton, "rotate")
        self.rotate_button.clicked.connect(self.rotate_video)

        self.color_combo_box = self.ui.findChild(QComboBox, "color_combo_box")
        self.color_combo_box.currentTextChanged.connect(self.on_color_combo_changed)
        self.map_manager = ColorMapManager()
        self.refresh_color_preset_list()

        # ——— 采样控制 ———
        self.spin_duration = self.ui.findChild(QSpinBox, "measure_w")
        self.spin_freq = self.ui.findChild(QSpinBox, "measure_h")
        self.btn_measure_ensure = self.ui.findChild(QPushButton, "measure_ensure")
        
        self.spin_duration.setRange(1, 3600)
        self.spin_duration.setValue(10)
        self.spin_duration.setToolTip("采样总时长 (秒)")
        self.spin_duration.setSuffix(" s")
        
        self.spin_freq.setRange(1, 30)
        self.spin_freq.setValue(2)
        self.spin_freq.setToolTip("采样频率 (次/秒)")
        self.spin_freq.setSuffix(" Hz")
        
        self.btn_measure_ensure.setText("应用采样配置")
        self.btn_measure_ensure.clicked.connect(self.apply_sampling_settings)

        # 采样按钮
        self.btn_start_sampling = self.ui.findChild(QPushButton, "pushButton")
        self.btn_start_sampling.setText("开始记录 (未开始)")
        self.btn_start_sampling.clicked.connect(self.toggle_sampling)

        # ——— 快捷键 Ctrl+M ———
        self.shortcut_mode = QShortcut(QKeySequence("Ctrl+M"), self)
        self.shortcut_mode.activated.connect(self.switch_interaction_mode)

        # ——— 日志 ———
        self.log_box = self.ui.findChild(QPlainTextEdit, "logger")
        self.logger = self.setup_logger(self.log_box)
        self.logger.info("系统UI美化加载完成. 当前模式: 单点测温. 按 Ctrl+M 切换.")

        # ——— 采样状态 ———
        self.is_sampling = False
        self.sampling_start_time = 0
        self.sampling_next_record_time = 0
        self.sampling_data = []
        self.target_duration = 10
        self.target_interval = 0.5

        self.init_camera()
        self.start_timer()

    def init_camera(self):
        self.camera = HikCamera(vendor_id=0x2BDF, product_id=0x0102)
        if not self.camera.connect():
            self.logger.error("相机连接失败，请检查设备连接。")
            # 即使相机失败，也继续运行UI，显示黑色背景
            return
        self.camera.start_stream()

    def start_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

    def switch_interaction_mode(self):
        if self.is_sampling:
            self.stop_sampling(save=True)
            self.logger.info("模式切换，自动停止当前采样")

        self.current_mode = 1 - self.current_mode 
        mode_name = "单点测温模式 (单击选点)" if self.current_mode == self.MODE_POINT else "区域测温模式 (拖拽框选)"
        msg = f"当前模式: {mode_name} | 按 Ctrl+M 切换"
        self.logger.info(f"模式已切换为: {mode_name}")
        self.info_label.setText(msg)
        
        self.start_pos_norm = None
        self.end_pos_norm = None
        self.point_pos_norm = None
        self.is_drawing = False

    def apply_sampling_settings(self):
        duration = self.spin_duration.value()
        freq = self.spin_freq.value()
        self.target_duration = duration
        self.target_interval = 1.0 / freq
        self.logger.info(f"采样设置已更新: 时长={duration}s, 频率={freq}Hz")
        QMessageBox.information(self, "设置更新", f"采样设置已生效。\n时长: {duration}秒\n频率: {freq}Hz")

    def toggle_sampling(self):
        if not self.is_sampling:
            if self.current_mode == self.MODE_POINT and self.point_pos_norm is None:
                QMessageBox.warning(self, "警告", "请先在画面中点击选择一个测温点")
                return
            if self.current_mode == self.MODE_RECT and (self.start_pos_norm is None or self.end_pos_norm is None):
                QMessageBox.warning(self, "警告", "请先在画面中框选一个区域")
                return

            self.is_sampling = True
            self.sampling_data = []
            self.sampling_start_time = time.time()
            self.sampling_next_record_time = self.sampling_start_time
            self.btn_start_sampling.setText("停止采样 (进行中...)")
            # 采样时让按钮变色提醒
            self.btn_start_sampling.setStyleSheet("background-color: #FF7043; color: white;") 
            
            mode_str = "单点" if self.current_mode == self.MODE_POINT else "区域"
            self.logger.info(f"开始 {mode_str} 数据采样...")
        else:
            self.stop_sampling(save=True)

    def stop_sampling(self, save=False):
        self.is_sampling = False
        self.btn_start_sampling.setText("开始记录")
        # 恢复按钮样式 (清除内联样式，恢复到主题样式)
        self.btn_start_sampling.setStyleSheet("") 
        if save and self.sampling_data:
            self.save_sampling_data()

    def save_sampling_data(self):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"thermal_log_{timestamp}.txt"
        try:
            with open(filename, 'w') as f:
                f.write(f"--- InfraView Thermal Data Log ---\n")
                f.write(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Mode: {'Point Measurement' if self.current_mode == self.MODE_POINT else 'Region (ROI) Measurement'}\n")
                f.write(f"Settings: Duration={self.target_duration}s, Interval={self.target_interval:.2f}s\n")
                f.write("-" * 40 + "\n")
                if self.current_mode == self.MODE_POINT:
                    f.write("Time(s), Temperature(C)\n")
                    for t, v in self.sampling_data:
                        f.write(f"{t:.2f}, {v:.2f}\n")
                else:
                    f.write("Time(s), Temperature(C)\n")
                    for t, av in self.sampling_data:
                        f.write(f"{t:.2f}, {av:.2f}\n")
            self.logger.info(f"数据已保存至: {filename}")
            QMessageBox.information(self, "完成", f"采样结束。\n文件已保存为:\n{filename}")
        except Exception as e:
            self.logger.error(f"保存失败: {e}")
            QMessageBox.critical(self, "错误", f"保存文件失败:\n{e}")

    def update_frame(self):
        if not self.camera or not self.camera.is_connected:
            return

        full_frame = self.camera.read_next_frame()
        if full_frame is None: return
        
        thermal = unpack_thermal_frame(full_frame)
        if thermal is None: return
        self.current_thermal_raw = thermal

        w_widget = self.video_label.width()
        h_widget = self.video_label.height()
        
        display_img = process_thermal_for_display(
            thermal, 
            (w_widget, h_widget), 
            self.rotation_angle, 
            self.color_mode, 
            self.custom_nodes if self.color_mode == "custom" else None
        )

        qimg = self.numpy_to_qimage(display_img)
        pixmap = QPixmap.fromImage(qimg).scaled(w_widget, h_widget, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        current_temp_data = None 

        if self.current_mode == self.MODE_RECT:
            if self.start_pos_norm and self.end_pos_norm:
                sx, sy = int(self.start_pos_norm[0] * w_widget), int(self.start_pos_norm[1] * h_widget)
                ex, ey = int(self.end_pos_norm[0] * w_widget), int(self.end_pos_norm[1] * h_widget)
                
                rect_x, rect_y = min(sx, ex), min(sy, ey)
                rect_w, rect_h = abs(ex - sx), abs(ey - sy)
                
                pen = QPen(QColor("#69F0AE"), 2) 
                painter.setPen(pen)
                painter.drawRect(rect_x, rect_y, rect_w, rect_h)

                roi_stats = self.get_roi_stats(thermal, self.start_pos_norm, self.end_pos_norm)
                if roi_stats:
                    t_max, t_min, t_avg = roi_stats
                    current_temp_data = (t_avg)
                    info_text = [f"Max: {t_max:.1f} °C", f"Min: {t_min:.1f} °C", f"Avg: {t_avg:.1f} °C"]
                    self.draw_info_box(painter, rect_x + rect_w + 10, rect_y, info_text)

        elif self.current_mode == self.MODE_POINT:
            if self.point_pos_norm:
                px, py = int(self.point_pos_norm[0] * w_widget), int(self.point_pos_norm[1] * h_widget)
                
                pen = QPen(QColor("#FF5252"), 2)
                painter.setPen(pen)
                painter.drawLine(px - 12, py, px + 12, py)
                painter.drawLine(px, py - 12, px, py + 12)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPoint(px, py), 6, 6)

                val = self.get_point_temp(thermal, self.point_pos_norm)
                if val is not None:
                    current_temp_data = val
                    self.draw_info_box(painter, px + 20, py - 20, [f"Temp: {val:.1f} °C"])

        painter.end()
        self.video_label.setPixmap(pixmap)

        if self.is_sampling:
            now = time.time()
            elapsed = now - self.sampling_start_time
            
            if elapsed >= self.target_duration:
                self.stop_sampling(save=True)
                return

            if now >= self.sampling_next_record_time:
                if current_temp_data is not None:
                    if self.current_mode == self.MODE_POINT:
                        self.sampling_data.append((elapsed, current_temp_data))
                    elif self.current_mode == self.MODE_RECT:
                        self.sampling_data.append((elapsed, current_temp_data))
                    
                    self.sampling_next_record_time += self.target_interval
                    
                    remaining = self.target_duration - elapsed
                    # 更新按钮文本，显示倒计时
                    self.btn_start_sampling.setText(f"停止 ({remaining:.1f}s)")

    def draw_info_box(self, painter, x, y, lines):
        font = painter.font()
        font.setFamily("Segoe UI")
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()
        
        max_w = 0
        h_per_line = fm.height() + 4 
        for line in lines:
            w = fm.width(line)
            if w > max_w: max_w = w
        
        box_w = max_w + 30 
        box_h = len(lines) * h_per_line + 16
        
        # 边界检查
        if x + box_w > self.video_label.width(): x -= box_w + 40
        if y + box_h > self.video_label.height(): y -= box_h
        x = max(10, x)
        y = max(10, y)


        brush = QBrush(QColor(69, 39, 160, 200)) 
        painter.setBrush(brush)
        # 使用半透明的白色边框
        pen = QPen(QColor(255, 255, 255, 150), 1.5)
        painter.setPen(pen)
        # 绘制圆角矩形背景
        painter.drawRoundedRect(x, y, box_w, box_h, 8, 8)

        # 绘制文字 (纯白色)
        painter.setPen(Qt.white)
        for i, line in enumerate(lines):
            # 稍微调整文字位置以居中
            painter.drawText(x + 15, y + (i+1) * h_per_line + 2, line)

    def get_raw_coords(self, norm_x, norm_y, raw_w, raw_h):
        rx, ry = 0, 0
        if self.rotation_angle == 0:
            rx = int(norm_x * raw_w); ry = int(norm_y * raw_h)
        elif self.rotation_angle == 90:
            rx = int(norm_y * raw_w); ry = int((1 - norm_x) * raw_h)
        elif self.rotation_angle == 180:
            rx = int((1 - norm_x) * raw_w); ry = int((1 - norm_y) * raw_h)
        elif self.rotation_angle == 270:
            rx = int((1 - norm_y) * raw_w); ry = int(norm_x * raw_h)
        return max(0, min(raw_w-1, rx)), max(0, min(raw_h-1, ry))

    def get_point_temp(self, thermal, norm_pos):
        raw_h, raw_w = thermal.shape
        rx, ry = self.get_raw_coords(norm_pos[0], norm_pos[1], raw_w, raw_h)
        return float(thermal[ry, rx])

    def get_roi_stats(self, thermal, norm_start, norm_end):
        raw_h, raw_w = thermal.shape
        x1_raw, y1_raw = self.get_raw_coords(norm_start[0], norm_start[1], raw_w, raw_h)
        x2_raw, y2_raw = self.get_raw_coords(norm_end[0], norm_end[1], raw_w, raw_h)
        x1, x2 = min(x1_raw, x2_raw), max(x1_raw, x2_raw)
        y1, y2 = min(y1_raw, y2_raw), max(y1_raw, y2_raw)
        if x2 == x1: x2 += 1
        if y2 == y1: y2 += 1
        roi = thermal[y1:y2, x1:x2]
        if roi.size == 0: return None
        return np.max(roi), np.min(roi), np.mean(roi)

    # ——— 鼠标事件 (保持不变) ———
    def mousePressEvent(self, event):
        child = self.childAt(event.pos())
        if child != self.video_label: return super().mousePressEvent(event)
        local_pos = self.video_label.mapFrom(self, event.pos())
        norm_x = local_pos.x() / self.video_label.width()
        norm_y = local_pos.y() / self.video_label.height()
        if self.current_mode == self.MODE_POINT:
            if event.button() == Qt.LeftButton: self.point_pos_norm = (norm_x, norm_y)
        elif self.current_mode == self.MODE_RECT:
            if event.button() == Qt.LeftButton:
                self.is_drawing = True
                self.start_pos_norm = (norm_x, norm_y)
                self.end_pos_norm = (norm_x, norm_y)

    def mouseMoveEvent(self, event):
        if self.current_mode == self.MODE_RECT and self.is_drawing:
            local_pos = self.video_label.mapFrom(self, event.pos())
            w, h = self.video_label.width(), self.video_label.height()
            norm_x = max(0.0, min(1.0, local_pos.x() / w))
            norm_y = max(0.0, min(1.0, local_pos.y() / h))
            self.end_pos_norm = (norm_x, norm_y)

    def mouseReleaseEvent(self, event):
        if self.current_mode == self.MODE_RECT and self.is_drawing: self.is_drawing = False

    # ——— 其他辅助函数 ———
    def rotate_video(self):
        self.rotation_angle = (self.rotation_angle + 90) % 360
        self.start_pos_norm = None; self.end_pos_norm = None; self.point_pos_norm = None

    def numpy_to_qimage(self, img):
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        return QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()

    def on_color_combo_changed(self, text):
        if text.startswith("★ "):
            map_name = text[2:]
            nodes, msg = self.map_manager.load_map(map_name)
            if nodes: self.custom_nodes = nodes; self.color_mode = "custom"
            return
        if text == "自定义...": self.openColorMapEditor(); return
        preset_map = {"inferno (火焰)": "inferno", "magma (岩浆)": "magma", 
                      "jet (彩虹)": "jet", "rainbow (彩虹平滑)": "rainbow",
                      "turbo (优化彩虹)": "turbo", "bone (骨骼灰)": "bone"}
        if text in preset_map: self.color_mode = preset_map[text]

    def refresh_color_preset_list(self):
        current = self.color_combo_box.currentText()
        self.color_combo_box.blockSignals(True)
        self.color_combo_box.clear()
        items = ["inferno (火焰)", "magma (岩浆)", "jet (彩虹)", "rainbow (彩虹平滑)", 
                 "turbo (优化彩虹)", "bone (骨骼灰)", "自定义..."]
        self.color_combo_box.addItems(items)
        saved = self.map_manager.get_saved_maps()
        if saved:
            self.color_combo_box.insertSeparator(len(items))
            for name in saved: self.color_combo_box.addItem(f"★ {name}")
        self.color_combo_box.setCurrentText(current) if current else None
        self.color_combo_box.blockSignals(False)

    def openColorMapEditor(self):
        dialog = ColorMapEditorDialog(self, getattr(self, 'custom_nodes', None))
        dialog.customMapCreated.connect(self.onCustomMapCreated)
        dialog.exec()

    def onCustomMapCreated(self, nodes):
        self.custom_nodes = nodes
        self.color_mode = "custom"
        self.refresh_color_preset_list()

    def setup_logger(self, text_widget):
        logger = logging.getLogger("app")
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
        qt_handler = QtHandle()
        qt_handler.setFormatter(formatter)
        qt_handler.emitter.log_signal.connect(text_widget.appendPlainText)
        logger.addHandler(qt_handler)
        return logger

    def show_about_dialog(self):
        QMessageBox.about(self, "关于", "InfraView 热成像分析系统")