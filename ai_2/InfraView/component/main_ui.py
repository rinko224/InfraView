# component/main_ui.py
from PySide2.QtWidgets import QMainWindow, QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QSpinBox, QComboBox, QMessageBox, QDialog, QSizePolicy, QPlainTextEdit, QAction
from PySide2.QtCore import QTimer, Qt, QFile
from PySide2.QtGui import QImage, QPixmap, QIcon
from PySide2.QtUiTools import QUiLoader
import cv2
import numpy as np
import time
import torch
import logging



# 引用组件
from . import config
from . import preprocess
from .theme_style import PurpleTheme
from .model_detector import CustomTinyYOLO
from .model_recognizer import MobileFaceNet_Thermal
from .database_manager import FaceLibrary
from .color_map_editor import ColorMapEditorDialog
from .color_map_manager import ColorMapManager
from .logger import GuiLogger, QtHandle

# 引用您提供的驱动文件 (注意文件名已改为 driver_*)
from .driver_camera import HikCamera
from .driver_util import unpack_thermal_frame
from .matrix_util import process_thermal_for_display
from .display_util import theraml_point_rotate

loader = QUiLoader()
class MainUI(QMainWindow):
    def __init__(self):
        super().__init__()

        ui_file = QFile("component/ui/display.ui")
        ui_file.open(QFile.ReadWrite)
        self.ui = loader.load(ui_file)
        ui_file.close()

        self.setCentralWidget(self.ui)

        self.setWindowTitle("InfraView Thermal Recognition System")
        self.setWindowIcon(QIcon("icon.ico"))
        self.resize(900, 500)
        self.setStyleSheet(PurpleTheme.STYLE_SHEET)
       
        menubar = self.menuBar()


        about_action = QAction("关于",self)
        about_action.triggered.connect(self.show_about_dialog)
        menubar.addAction(about_action)

        _action = QAction("")

        # ——— 一些基本属性 ———
        self.rotation_angle = 0
        self.measure_pos = None
        self.measure_info = ""
        self.area_max_temp = None
        self.area_min_temp = None
        self.roi_temp = None
        self.measure_h = 10
        self.measure_w = 10
        self.color_mode = "inferno"
        self.nodes = None
        self.current_thermal_raw = None
        self.app_mode = "Normal"

        # ——— 左边视频区域 ———
        self.video_label = self.ui.findChild(QLabel, "video_label")
        self.video_label.setMinimumSize(1, 1) 

        self.video_label.setMouseTracking(False)
        self.video_label.installEventFilter(self)
        self.video_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        # ——— 右侧信息面板 ———
        self.info_label = self.ui.findChild(QLabel, "info")
        self.info_label.setMinimumSize(1, 1) 

        # ——— 旋转按钮 ———
        self.rotate_button = self.ui.findChild(QPushButton, "rotate")
        self.rotate_button.clicked.connect(self.rotate_video)

        # ——— 伪彩模式设置按钮 ———
        self.color_combo_box = self.ui.findChild(QComboBox, "color_combo_box")
        self.color_combo_box.currentTextChanged.connect(self.on_color_combo_changed)
        self.map_manager = ColorMapManager()
        self.refresh_color_preset_list()

        # ——— 区域测量相关 ———
        self.measure_ensure = self.ui.findChild(QPushButton, "measure_ensure")
        self.measure_ensure.clicked.connect(self.ensure_measure)

        self.measure_area_h_edit = self.ui.findChild(QSpinBox, "measure_h")
        self.measure_area_w_edit = self.ui.findChild(QSpinBox, "measure_w")

        # ——— 日志输出相关 ———
        self.log_box = self.ui.findChild(QPlainTextEdit, "logger")
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumBlockCount(500) 
        self.log_box.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.log_box.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.log_box.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.logger = self.setup_logger(self.log_box)
        

        self.video_label.setScaledContents(True)

        self.sampling_sub_mode = "MaxMin"
        self.sampling_freq = 1.0
        self.sampling_duration = 10
        self.is_sampling_running = False 
        self.sampling_start_time = 0.0
        self.last_sample_time = 0.0
        self.sampling_data = [] 
        self.sampling_target_rect = None 


        self.init_system()
        self.start_timer()
    
    def init_system(self):
        self.detector = CustomTinyYOLO()
        self.recognizer = MobileFaceNet_Thermal()
        self.db = FaceLibrary()

        self.camera = HikCamera(vendor_id=0x2BDF, product_id=0x0102)
        if not self.camera.connect():
            print("相机打开失败")
            self.logger.error("相机打开失败")
            return
        self.camera.start_stream()
        self.prev_time = time.time()
        self.last_embedding = None
    
    def start_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)  # 30ms 刷新一次
    def update_frame(self):
        now = time.time()
        fps = 1 / (now - self.prev_time)
        self.prev_time = now

        if not self.camera.is_connected:
            self.info_label.setText("Camera Disconnected")
            return
        
        # ——— 读取热成像数据 ———
        full_frame = self.camera.read_next_frame()
        if full_frame is None:
            return

        thermal = unpack_thermal_frame(full_frame)
        if thermal is None:
            return
        self.current_thermal_raw = thermal
        
        w = self.video_label.width()
        h = self.video_label.height()
        out_size = (w, h)
        raw_h, raw_w = thermal.shape

        # ——— 生成展示图（彩色） ———
        display_img = process_thermal_for_display(
            thermal, 
            out_size, 
            self.rotation_angle, 
            self.color_mode, 
            self.custom_nodes if self.color_mode == "custom" else None
        )

        self._process_measurement(thermal, display_img, self.measure_h, self.measure_w)

        if self.app_mode == "Sampling" and self.is_sampling_running and self.sampling_target_rect:
            elapsed = now - self.sampling_start_time
            if elapsed >= self.sampling_duration:
                self.stop_sampling_session(save=True)
            else:
                if now - self.last_sample_time >= self.sampling_freq:
                    self.last_sample_time = now
                    rect = self.sampling_target_rect
                    if self.sampling_sub_mode == "MaxMin":
                        max_temp = np.max(thermal[rect[1]:rect[1]+rect[3], rect[0]:rect[0]+rect[2]])
                        min_temp = np.min(thermal[rect[1]:rect[1]+rect[3], rect[0]:rect[0]+rect[2]])
                        self.sampling_data.append((elapsed, max_temp, min_temp))
                    elif self.sampling_sub_mode == "ROI":
                        roi_temp = thermal[rect[1]:rect[1]+rect[3], rect[0]:rect[0]+rect[2]]
                        avg_temp = np.mean(roi_temp)
                        self.sampling_data.append((elapsed, avg_temp))
        # ——— 用 QLabel 显示左侧图像 ———
        qimg = self.numpy_to_qimage(display_img)
        self.video_label.setPixmap(QPixmap.fromImage(qimg))

        text = f"FPS: {fps:.1f}\n\n"
        if self.area_max_temp is not None and self.area_min_temp is not None:
            text += f"{self.measure_info}\n"

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
            roi_mean = np.mean(measure_area)
            self.area_max_temp = temp_max
            self.area_min_temp = temp_min
            self.roi_temp = roi_mean
            self.measure_info = f"Max Temp: {temp_max:.2f}°C\nMin Temp: {temp_min:.2f}°C\nROI Mean: {roi_mean:.2f}°C"

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
            self.measure_pos = (local_pos.x() / self.video_label.width(), 
                                local_pos.y() / self.video_label.height())
        super().mousePressEvent(event)

    def ensure_measure(self):
        self.measure_h = self.measure_area_h_edit.value()
        self.measure_w = self.measure_area_w_edit.value()
    
    def set_color_map(self, color_mode):
        self.color_mode = color_mode

    def openColorMapEditor(self):
        
        # 如果已有自定义节点，传递给编辑器初始化
        initial_nodes = getattr(self, 'custom_nodes', None)
        
        # 创建对话框实例 - 使用exec()而不是exec_()以确保正确的模态行为
        dialog = ColorMapEditorDialog(self, initial_nodes)
        
        # 只连接自定义映射创建完成的信号
        dialog.customMapCreated.connect(self.onCustomMapCreated)
        
        # 显示对话框（模态阻塞）
        result = dialog.exec()
        
        # 对话框关闭后的处理
        if result == QDialog.Accepted:
            print("[调试] 编辑器被接受")
        else:
            print("[调试] 编辑器被拒绝或关闭")
            # 确保下拉框显示正确
            if not hasattr(self, 'custom_nodes') or not self.custom_nodes:
                # 没有自定义配置，确保显示预设模式
                self.color_combo_box.blockSignals(True)
                self.color_combo_box.setCurrentText("inferno (火焰)")
                self.color_combo_box.blockSignals(False)

    def on_editor_finished(self, result):
        print(f"[调试] 编辑器关闭，结果码: {result}")
        
        # 更新下拉框显示（如果有新的自定义预设）
        self.refresh_color_preset_list()
        
        # 如果编辑器被取消或关闭，确保下拉框显示正确的项
        if result == 0:  # 0通常表示取消/关闭
            print("[调试] 编辑器被取消或关闭")
            
            # 如果没有有效的自定义节点，恢复到默认模式
            if not hasattr(self, 'custom_nodes') or not self.custom_nodes:
                self.color_mode = "inferno"
                # 临时阻塞信号避免递归
                self.color_combo_box.blockSignals(True)
                self.color_combo_box.setCurrentText("inferno (火焰)")
                self.color_combo_box.blockSignals(False)
            else:
                # 如果有自定义节点，确保下拉框显示"自定义..."（或者我们可以创建一个虚拟项）
                print("[调试] 保持自定义模式")

    def on_editor_closed(self, result):
        """当编辑器关闭时刷新下拉框中的预设列表"""
        self.refresh_color_preset_list()

    def refresh_color_preset_list(self):
        """刷新颜色预设下拉列表，添加已保存的自定义预设"""
        # 保存当前选择
        current_text = self.color_combo_box.currentText()
        
        # 阻塞信号防止递归
        self.color_combo_box.blockSignals(True)
        
        # 清空下拉框
        self.color_combo_box.clear()
        
        # 重新添加预设
        presets = [
            "inferno (火焰)",
            "magma (岩浆)", 
            "jet (彩虹)",
            "rainbow (彩虹平滑)",
            "turbo (优化彩虹)",
            "bone (骨骼灰)",
            "自定义..."
        ]
        
        for preset in presets:
            self.color_combo_box.addItem(preset)
        
        # 添加已保存的自定义预设
        saved_maps = self.map_manager.get_saved_maps()
        if saved_maps:
            self.color_combo_box.insertSeparator(len(presets))
            for map_name in sorted(saved_maps.keys()):
                self.color_combo_box.addItem(f"★ {map_name}")
        
        # 恢复之前的选择（如果还存在）
        items = [self.color_combo_box.itemText(i) for i in range(self.color_combo_box.count())]
        if current_text in items:
            self.color_combo_box.setCurrentText(current_text)
        else:
            # 如果之前的选择不存在了，设为第一个预设
            self.color_combo_box.setCurrentText("inferno (火焰)")
        
        # 重新启用信号
        self.color_combo_box.blockSignals(False)

    def onCustomMapCreated(self, nodes):
        """当用户从自定义编辑器确认时调用"""
        print(f"[调试] 收到自定义节点: {nodes}")
        self.custom_nodes = nodes
        self.color_mode = "custom"
        
        # 更新下拉框列表以包含新保存的预设
        self.refresh_color_preset_list()
        
        # 找到并选择新保存的预设（如果有）
        saved_maps = self.map_manager.get_saved_maps()
        if saved_maps:
            # 可以选择最近保存的一个，这里简单选择第一个
            if saved_maps:
                first_map = list(saved_maps.keys())[0]
                self.color_combo_box.blockSignals(True)
                for i in range(self.color_combo_box.count()):
                    if self.color_combo_box.itemText(i) == f"★ {first_map}":
                        self.color_combo_box.setCurrentIndex(i)
                        break
                self.color_combo_box.blockSignals(False)
        
        print(f"[信息] 已应用自定义颜色映射")
        self.logger.info("已应用自定义颜色映射")

    def on_color_combo_changed(self, text):
        """当下拉选择框内容改变时调用"""
        print(f"[调试] 下拉框选择变化: '{text}'")
        
        # 1. 处理“自定义...”选项 - 关键修复：立即改变下拉框选择，避免后续信号
        if text == "自定义...":
            print("[调试] 选择自定义，打开编辑器")
            
            # 立即将下拉框设为安全状态（比如第一个预设）
            # 这是防止循环的关键！
            self.color_combo_box.blockSignals(True)
            self.color_combo_box.setCurrentText("inferno (火焰)")
            self.color_combo_box.blockSignals(False)
            
            # 然后再打开编辑器
            self.openColorMapEditor()
            return
        
        # 2. 检查是否为已保存的自定义预设（带★标记的）
        if text.startswith("★ "):
            map_name = text[2:]  # 去掉"★ "前缀
            nodes, message = self.map_manager.load_map(map_name)
            if nodes:
                self.custom_nodes = nodes
                self.color_mode = "custom"
                print(f"[信息] 已加载自定义预设: {map_name}")
                self.logger.info(f"已加载自定义预设: {map_name}")
            else:
                QMessageBox.warning(self, "加载失败", message)
                # 回退到默认
                self.color_mode = "inferno"
                self.color_combo_box.blockSignals(True)
                self.color_combo_box.setCurrentText("inferno (火焰)")
                self.color_combo_box.blockSignals(False)
            return
        
        # 3. 处理预设选项
        preset_map = {
            "inferno (火焰)": "inferno",
            "magma (岩浆)": "magma", 
            "jet (彩虹)": "jet",
            "rainbow (彩虹平滑)": "rainbow",
            "turbo (优化彩虹)": "turbo",
            "bone (骨骼灰)": "bone"
        }
        
        if text in preset_map:
            mode_name = preset_map[text]
            self.color_mode = mode_name
            if hasattr(self, 'custom_nodes'):
                self.custom_nodes = None  # 切换到预设时清除自定义节点
            print(f"[信息] 已切换颜色模式至预设: {mode_name}")
            self.logger.info(f"已切换颜色模式至预设: {mode_name}")
        else:
            print(f"[警告] 未知的颜色模式选项: {text}")
            self.logger.warning(f"未知的颜色模式选项: {text}")

        
    def setup_logger(self, text_widget: QPlainTextEdit):
        logger = logging.getLogger("app")
        logger.setLevel(logging.INFO)

        formatter = logging.Formatter("[%(levelname)s] %(message)s")

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        qt_handler = QtHandle()
        qt_handler.setFormatter(formatter)
        qt_handler.emitter.log_signal.connect(text_widget.appendPlainText)

        logger.addHandler(console_handler)
        logger.addHandler(qt_handler)

        return logger
    
    def show_about_dialog(self):
        about_dialog = QDialog(self)
        about_dialog.setWindowTitle("关于")
        about_dialog.setModal(True)
        about_dialog.setFixedSize(300, 200)
        about_dialog.setStyleSheet(PurpleTheme.STYLE_SHEET)
        
        layout = QVBoxLayout(about_dialog)
        
        title_label = QLabel("InfraView 1.0")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title_label)
        
        version_label = QLabel("版本 1.0.0")
        layout.addWidget(version_label)
        
        author_label = QLabel("作者: 贺卓男 罗佳勇 林子杰 余承恩")
        layout.addWidget(author_label)
        
        camera_label = QLabel("相机型号:HikCamera 256*192")
        layout.addWidget(camera_label)

        ok_button = QPushButton("确定")
        ok_button.clicked.connect(about_dialog.accept)
        layout.addWidget(ok_button)
        
        about_dialog.exec_()

    def stop_sampling_session(self, save=False):
        if save and self.sampling_data:
            filename = "sampling_output.txt"
            try:
                with open(filename, 'w') as f:
                    if self.sampling_sub_mode == "ROI":
                        f.write("Time(s), Temperature(C)\n")
                        for t, val in self.sampling_data:
                            f.write(f"{t:.2f}, {val:.2f}\n")
                    else:
                        f.write("Time(s), Max(C), Min(C)\n")
                        for t, max_v, min_v in self.sampling_data:
                            f.write(f"{t:.2f}, {max_v:.2f}, {min_v:.2f}\n")
                print(f"[成功] 采样完成，文件已保存至 {filename}")
                QMessageBox.information(self, "采样完成", f"数据已保存至 {filename}")
            except Exception as e:
                print(f"[错误] 保存文件失败: {e}")