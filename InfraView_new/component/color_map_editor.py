# component/color_map_editor.py
from .color_map_manager import ColorMapManager
from PySide2.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QSlider, QListWidget, QListWidgetItem,
                               QColorDialog, QFrame, QMessageBox, QInputDialog, QMenu, QAction)
from PySide2.QtCore import Qt, Signal, QPoint
from PySide2.QtGui import QColor, QPainter, QLinearGradient, QPen
from functools import partial
import numpy as np

class GradientPreview(QFrame):
    """用于预览颜色渐变的自定义Widget"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(60)
        self.setFrameStyle(QFrame.Box)
        self.lut = np.zeros((256, 3), dtype=np.uint8)  # 默认黑色渐变

    def setLut(self, lut):
        self.lut = lut
        self.update()  # 触发重绘

    def paintEvent(self, event):
        painter = QPainter(self)
        width = self.width()
        height = self.height()
        # 绘制渐变条
        for i in range(width):
            idx = int(i * 255.0 / width)
            color = QColor(*self.lut[idx])
            painter.setPen(color)
            painter.drawLine(i, 0, i, height)
        # 画边框
        painter.setPen(Qt.gray)
        painter.drawRect(0, 0, width-1, height-1)


class ColorControlPoint:
    """颜色控制点的数据类"""
    def __init__(self, position, color):
        # position: 0-255 之间的整数，表示在渐变中的位置
        self.position = position
        self.color = color  # QColor对象

    def toTuple(self):
        """转换为 matrix_util.build_lut 可用的格式"""
        return (self.position, (self.color.red(), self.color.green(), self.color.blue()))


class ColorMapEditorDialog(QDialog):
    """主编辑器对话框"""
    # 定义一个信号，当用户确认时，传递生成的nodes列表
    customMapCreated = Signal(list)

    def __init__(self, parent=None, initial_nodes=None):
        super().__init__(parent)
        self.setWindowTitle("自定义颜色映射")
        self.resize(600, 400)
        self.control_points = []
        self.current_lut = np.zeros((256, 3), dtype=np.uint8)
        self.map_manager = ColorMapManager()
        
        # 如果传入初始节点（例如之前保存的配置），则加载
        if initial_nodes:
            for pos, rgb in initial_nodes:
                self.control_points.append(ColorControlPoint(pos, QColor(*rgb)))
        else:
            # 否则提供默认的两个端点（黑到白）
            self.control_points.append(ColorControlPoint(0, QColor(0, 0, 0)))
            self.control_points.append(ColorControlPoint(255, QColor(255, 255, 255)))
        
        self.initUI()
        self.sortPoints()
        self.updateLutAndPreview()

    def initUI(self):
        layout = QVBoxLayout(self)
        # 1. 渐变预览区域
        self.preview = GradientPreview()
        layout.addWidget(QLabel("渐变预览:"))
        layout.addWidget(self.preview)
        
        # 2. 控制点列表和操作按钮
        control_layout = QHBoxLayout()
        self.point_list = QListWidget()
        self.point_list.itemSelectionChanged.connect(self.onPointSelected)
        control_layout.addWidget(self.point_list, 1)
        
        btn_layout = QVBoxLayout()
        self.add_btn = QPushButton("添加控制点")
        self.add_btn.clicked.connect(self.addControlPoint)
        btn_layout.addWidget(self.add_btn)
        
        self.delete_btn = QPushButton("删除选中点")
        self.delete_btn.clicked.connect(self.deleteControlPoint)
        self.delete_btn.setEnabled(False)
        btn_layout.addWidget(self.delete_btn)
        
        self.color_btn = QPushButton("修改颜色...")
        self.color_btn.clicked.connect(self.changePointColor)
        self.color_btn.setEnabled(False)
        btn_layout.addWidget(self.color_btn)
        # 添加分隔线
        from PySide2.QtWidgets import QFrame
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        btn_layout.addWidget(separator)
        
        # 保存/加载按钮
        self.save_btn = QPushButton("保存预设...")
        self.save_btn.clicked.connect(self.saveCustomMap)
        btn_layout.addWidget(self.save_btn)
        
        # 创建加载按钮（带下拉菜单）
        self.load_btn = QPushButton("加载预设")
        self.load_btn.setMenu(self.createLoadMenu())
        btn_layout.addWidget(self.load_btn)
        
        self.delete_preset_btn = QPushButton("删除预设...")
        self.delete_preset_btn.clicked.connect(self.deleteCustomMap)
        btn_layout.addWidget(self.delete_preset_btn)
        
        btn_layout.addStretch()
        control_layout.addLayout(btn_layout)
        layout.addLayout(control_layout)
        
        btn_layout.addStretch()
        control_layout.addLayout(btn_layout)
        layout.addLayout(control_layout)
        
        # 3. 选中点的位置微调
        pos_layout = QHBoxLayout()
        pos_layout.addWidget(QLabel("位置 (0-255):"))
        self.pos_slider = QSlider(Qt.Horizontal)
        self.pos_slider.setRange(0, 255)
        self.pos_slider.valueChanged.connect(self.onPositionChanged)
        self.pos_slider.setEnabled(False)
        pos_layout.addWidget(self.pos_slider, 1)
        self.pos_label = QLabel("0")
        pos_layout.addWidget(self.pos_label)
        layout.addLayout(pos_layout)
        
        # 4. 对话框按钮
        button_layout = QHBoxLayout()
        self.ok_btn = QPushButton("确定")
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)
        
        # 初始化列表显示
        self.updatePointList()

    def addControlPoint(self):
        """在中间位置添加一个新控制点"""
        print("[DEBUG] addControlPoint: 函数开始")
        new_pos = 128
        new_color = QColor(128, 128, 128)  # 默认灰色
        # 确保位置不重复（简单处理，可优化）
        while any(p.position == new_pos for p in self.control_points):
            new_pos = (new_pos + 10) % 256
        new_point = ColorControlPoint(new_pos, new_color)
        self.control_points.append(new_point)
        self.sortPoints()
        self.updatePointList()
        self.updateLutAndPreview()
        print(f"[DEBUG] addControlPoint: 函数结束，当前点数 {len(self.control_points)}")

    def deleteControlPoint(self):
        """删除选中的控制点，但至少保留两个端点"""
        if len(self.control_points) <= 2:
            QMessageBox.warning(self, "警告", "至少需要保留两个控制点（起点和终点）。")
            return
        
        current_row = self.point_list.currentRow()
        if 0 <= current_row < len(self.control_points):
            del self.control_points[current_row]
            self.updatePointList()
            self.updateLutAndPreview()

    def changePointColor(self):
        """修改选中点的颜色"""
        print("[DEBUG] changePointColor: 方法被调用")
        
        current_row = self.point_list.currentRow()
        print(f"[DEBUG] 当前选中的行索引: {current_row}")
        
        if current_row < 0 or current_row >= len(self.control_points):
            print("[ERROR] 没有选中的点或索引越界")
            return
        
        point = self.control_points[current_row]
        print(f"[DEBUG] 将要修改的点: 位置={point.position}, 颜色=({point.color.red()}, {point.color.green()}, {point.color.blue()})")
        
        # 打开颜色选择对话框
        try:
            print("[DEBUG] 正在打开颜色对话框...")
            # 使用当前颜色作为初始值
            new_color = QColorDialog.getColor(
                point.color, 
                self,  # 父窗口
                "选择颜色",  # 对话框标题
                QColorDialog.ShowAlphaChannel  # 可选：是否显示透明度通道
            )
            print(f"[DEBUG] 颜色对话框返回: {new_color}, 是否有效: {new_color.isValid()}")
            
            if new_color.isValid():
                # 更新颜色
                old_color = point.color
                point.color = new_color
                print(f"[DEBUG] 颜色已修改: 从({old_color.red()},{old_color.green()},{old_color.blue()}) 到 ({new_color.red()},{new_color.green()},{new_color.blue()})")
                
                # 更新界面
                self.updatePointList()
                self.updateLutAndPreview()
                
                # 重新选中同一行（因为列表更新会丢失选择）
                self.point_list.setCurrentRow(current_row)
            else:
                print("[DEBUG] 用户取消了颜色选择")
                
        except Exception as e:
            print(f"[ERROR] 打开颜色对话框时出错: {e}")
            import traceback
            traceback.print_exc()

    def onPointSelected(self):
        """当列表中选择点改变时，更新按钮状态和滑块"""
        current_row = self.point_list.currentRow()
        has_selection = current_row >= 0
        
        print(f"[DEBUG] 列表选择变化: 行={current_row}, 有选择={has_selection}")
        
        self.delete_btn.setEnabled(has_selection and len(self.control_points) > 2)
        self.color_btn.setEnabled(has_selection)  # 确保这行存在且为 True
        self.pos_slider.setEnabled(has_selection)
        
        if has_selection:
            point = self.control_points[current_row]
            # === 关键修复 3: 更新滑块时也临时断开信号 ===
            self.pos_slider.blockSignals(True)
            self.pos_slider.setValue(point.position)
            self.pos_slider.blockSignals(False)
            # === 关键修复 3结束 ===
            self.pos_label.setText(str(point.position))
        else:
            self.pos_slider.blockSignals(True)
            self.pos_slider.setValue(0)
            self.pos_slider.blockSignals(False)
            self.pos_label.setText("0")
        
        # 添加调试，确认按钮状态
        print(f"[DEBUG] ‘修改颜色’按钮启用状态: {self.color_btn.isEnabled()}")

    def onPositionChanged(self, value):
        """当滑块改变时，更新选中点的位置"""
        current_row = self.point_list.currentRow()
        if 0 <= current_row < len(self.control_points):
            point = self.control_points[current_row]
            
            # 检查新位置是否已被其他点占用
            position_taken = any(p.position == value for p in self.control_points if p != point)
            if position_taken:
                print(f"[DEBUG] 位置 {value} 已被占用，忽略此次修改")
                # 需要将滑块设回原来的值，并避免再次触发此函数
                self.pos_slider.blockSignals(True)  # 临时断开滑块信号
                self.pos_slider.setValue(point.position)
                self.pos_slider.blockSignals(False)
                return
            
            # === 关键修复 2: 修改位置前，也临时断开滑块信号 ===
            self.pos_slider.blockSignals(True)
            old_pos = point.position
            point.position = value
            self.sortPoints()  # 排序可能改变列表顺序
            
            # 排序后，当前选中的点可能移动到了新行，需要找到它
            new_row = self.control_points.index(point) if point in self.control_points else current_row
            
            self.sortPoints()
            self.updatePointList()  # 这会触发界面更新
            
            # 更新滑块显示（值已改变，这里只是同步标签）
            self.pos_slider.setValue(value)  # 由于信号被阻断，不会再次触发
            self.pos_label.setText(str(value))
            self.pos_slider.blockSignals(False)  # 重新连接信号
            # === 关键修复 2结束 ===
            
            self.updateLutAndPreview()
            print(f"[DEBUG] 点位置从 {old_pos} 修改为 {value}")

    def sortPoints(self):
        """按位置排序控制点"""
        # 仅在有实际变化时打印
        sorted_positions = [p.position for p in self.control_points]
        self.control_points.sort(key=lambda p: p.position)
        if sorted_positions != [p.position for p in self.control_points]:
            print(f"[DEBUG] sortPoints: 顺序已变化")

    def updatePointList(self):
        """更新列表控件显示"""
        print(f"[DEBUG] updatePointList: 更新列表，共 {len(self.control_points)} 个点")

        # === 关键修复 1: 保存当前选择，并临时断开列表选择信号 ===
        current_row = self.point_list.currentRow()
        # 临时断开信号，防止 setCurrentRow 触发 onPointSelected
        self.point_list.blockSignals(True)

        self.point_list.clear()
        for idx, point in enumerate(self.control_points):
            item_text = f"位置: {point.position}, 颜色: ({point.color.red()}, {point.color.green()}, {point.color.blue()})"
            item = QListWidgetItem(item_text)
            item.setBackground(point.color)
            
            luminance = point.color.red() * 0.299 + point.color.green() * 0.587 + point.color.blue() * 0.114
            if luminance > 128:
                item.setForeground(Qt.black)
            else:
                item.setForeground(Qt.white)
            self.point_list.addItem(item)
        
        # 恢复选择状态（如果之前有选择）
        if 0 <= current_row < self.point_list.count():
            self.point_list.setCurrentRow(current_row)
            print(f"[DEBUG] updatePointList: 恢复选择行 {current_row}")
        # === 关键修复 1结束: 重新连接信号 ===
        self.point_list.blockSignals(False)

    def updateLutAndPreview(self):
        """根据当前控制点生成LUT并更新预览"""
        print(f"[DEBUG] updateLutAndPreview: 开始，共 {len(self.control_points)} 个点")
        
        if len(self.control_points) < 2:
            print("[DEBUG] updateLutAndPreview: 点数不足，跳过")
            return
            
        nodes = [p.toTuple() for p in self.control_points]
        print(f"[DEBUG] updateLutAndPreview: 转换的nodes = {nodes}")
        
        try:
            # 确保导入 matrix_util
            from .matrix_util import build_lut
            lut_array = build_lut("custom", nodes)
            print(f"[DEBUG] updateLutAndPreview: LUT生成成功，形状 {lut_array.shape}")
            self.current_lut = lut_array.reshape(256, 3)
            self.preview.setLut(self.current_lut)
        except Exception as e:
            print(f"[ERROR] updateLutAndPreview: 生成LUT时出错 - {e}")
            import traceback
            traceback.print_exc()
        print(f"[DEBUG] updateLutAndPreview: 完成，共 {len(self.control_points)} 个点")

    def getNodes(self):
        """获取最终的nodes列表，用于传递给主程序"""
        return [p.toTuple() for p in self.control_points]

    def accept(self):
        """重写accept方法，在对话框关闭前发出信号"""
        self.customMapCreated.emit(self.getNodes())
        super().accept()

    def createLoadMenu(self):
        """创建加载预设的下拉菜单"""
        menu = QMenu(self.load_btn)
        
        # 获取已保存的映射
        saved_maps = self.map_manager.get_saved_maps()
        
        if saved_maps:
            for map_name in sorted(saved_maps.keys()):
                action = QAction(map_name, menu)
                # 使用partial绑定参数，避免lambda参数问题
                action.triggered.connect(partial(self.loadCustomMap, map_name))
                menu.addAction(action)
        else:
            action = QAction("(无保存的预设)", menu)
            action.setEnabled(False)
            menu.addAction(action)
        
        return menu

    def saveCustomMap(self):
        """保存当前自定义映射"""
        if len(self.control_points) < 2:
            QMessageBox.warning(self, "保存失败", "至少需要2个控制点才能保存")
            return
        
        # 获取保存名称
        map_name = self.map_manager.prompt_save_name(self)
        if not map_name:
            return
        
        # 获取当前nodes
        nodes = self.getNodes()
        
        # 保存
        success, message = self.map_manager.save_map(map_name, nodes)
        
        if success:
            QMessageBox.information(self, "保存成功", message)
            # 更新加载按钮的菜单
            self.load_btn.setMenu(self.createLoadMenu())
        else:
            QMessageBox.warning(self, "保存失败", message)

    def loadCustomMap(self, map_name):
        """加载指定的自定义映射"""
        # 注意：这里可能会接收到checked参数，但被partial处理了
        print(f"[DEBUG] 加载预设: {map_name}")
        
        nodes, message = self.map_manager.load_map(map_name)
        
        if nodes:
            # 清空现有控制点
            self.control_points.clear()
            
            # 添加新的控制点
            for pos, color in nodes:
                qcolor = QColor(*color)
                self.control_points.append(ColorControlPoint(pos, qcolor))
            
            # 更新界面
            self.sortPoints()
            self.updatePointList()
            self.updateLutAndPreview()
            
            # 可选：显示成功消息
            print(f"[INFO] 已加载预设: {map_name}")
            # QMessageBox.information(self, "加载成功", f"已加载预设 '{map_name}'")
        else:
            print(f"[ERROR] 加载失败: {message}")
            # QMessageBox.warning(self, "加载失败", message)

    def deleteCustomMap(self):
        """删除已保存的自定义映射"""
        saved_maps = self.map_manager.get_saved_maps()
        
        if not saved_maps:
            QMessageBox.information(self, "删除", "没有可删除的预设")
            return
        
        # 弹出选择对话框
        map_name, ok = QInputDialog.getItem(
            self, "删除预设", 
            "选择要删除的预设:", 
            sorted(saved_maps.keys()), 
            0, False
        )
        
        if ok and map_name:
            reply = QMessageBox.question(
                self, "确认删除", 
                f"确定要删除预设 '{map_name}' 吗？",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                success, message = self.map_manager.delete_map(map_name)
                if success:
                    QMessageBox.information(self, "删除成功", message)
                    # 更新加载按钮的菜单
                    self.load_btn.setMenu(self.createLoadMenu())
                else:
                    QMessageBox.warning(self, "删除失败", message)