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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(60)
        self.setFrameStyle(QFrame.Box)
        self.lut = np.zeros((256, 3), dtype=np.uint8) 

    def setLut(self, lut):
        self.lut = lut
        self.update()  

    def paintEvent(self, event):
        painter = QPainter(self)
        width = self.width()
        height = self.height()

        for i in range(width):
            idx = int(i * 255.0 / width)
            color = QColor(*self.lut[idx])
            painter.setPen(color)
            painter.drawLine(i, 0, i, height)

        painter.setPen(Qt.gray)
        painter.drawRect(0, 0, width-1, height-1)


class ColorControlPoint:
    def __init__(self, position, color):

        self.position = position
        self.color = color  

    def toTuple(self):
        return (self.position, (self.color.red(), self.color.green(), self.color.blue()))


class ColorMapEditorDialog(QDialog):
    """主编辑器对话框"""

    customMapCreated = Signal(list)

    def __init__(self, parent=None, initial_nodes=None):
        super().__init__(parent)
        self.setWindowTitle("自定义颜色映射")
        self.resize(600, 400)
        self.control_points = []
        self.current_lut = np.zeros((256, 3), dtype=np.uint8)
        self.map_manager = ColorMapManager()


        if initial_nodes:
            for pos, rgb in initial_nodes:
                self.control_points.append(ColorControlPoint(pos, QColor(*rgb)))
        else:
            self.control_points.append(ColorControlPoint(0, QColor(0, 0, 0)))
            self.control_points.append(ColorControlPoint(255, QColor(255, 255, 255)))
        
        self.initUI()
        self.sortPoints()
        self.updateLutAndPreview()

    def initUI(self):
        layout = QVBoxLayout(self)
        self.preview = GradientPreview()
        layout.addWidget(QLabel("渐变预览:"))
        layout.addWidget(self.preview)
        
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
 
        from PySide2.QtWidgets import QFrame
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        btn_layout.addWidget(separator)
        
        self.save_btn = QPushButton("保存预设...")
        self.save_btn.clicked.connect(self.saveCustomMap)
        btn_layout.addWidget(self.save_btn)
        
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
        
        button_layout = QHBoxLayout()
        self.ok_btn = QPushButton("确定")
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)
        
        self.updatePointList()

    def addControlPoint(self):
        """在中间位置添加一个新控制点"""
        print("[DEBUG] addControlPoint: 函数开始")
        new_pos = 128
        new_color = QColor(128, 128, 128)  
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
        
        try:
            print("[DEBUG] 正在打开颜色对话框...")
            new_color = QColorDialog.getColor(
                point.color, 
                self,  
                "选择颜色",  
                QColorDialog.ShowAlphaChannel  
            )
            print(f"[DEBUG] 颜色对话框返回: {new_color}, 是否有效: {new_color.isValid()}")
            
            if new_color.isValid():
                old_color = point.color
                point.color = new_color
                print(f"[DEBUG] 颜色已修改: 从({old_color.red()},{old_color.green()},{old_color.blue()}) 到 ({new_color.red()},{new_color.green()},{new_color.blue()})")
                
                self.updatePointList()
                self.updateLutAndPreview()
                
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
        self.color_btn.setEnabled(has_selection)  
        self.pos_slider.setEnabled(has_selection)
        
        if has_selection:
            point = self.control_points[current_row]
            self.pos_slider.blockSignals(True)
            self.pos_slider.setValue(point.position)
            self.pos_slider.blockSignals(False)
            self.pos_label.setText(str(point.position))
        else:
            self.pos_slider.blockSignals(True)
            self.pos_slider.setValue(0)
            self.pos_slider.blockSignals(False)
            self.pos_label.setText("0")
        
        print(f"[DEBUG] ‘修改颜色’按钮启用状态: {self.color_btn.isEnabled()}")

    def onPositionChanged(self, value):
        """当滑块改变时，更新选中点的位置"""
        current_row = self.point_list.currentRow()
        if 0 <= current_row < len(self.control_points):
            point = self.control_points[current_row]
            
            position_taken = any(p.position == value for p in self.control_points if p != point)
            if position_taken:
                print(f"[DEBUG] 位置 {value} 已被占用，忽略此次修改")
                self.pos_slider.blockSignals(True)  
                self.pos_slider.setValue(point.position)
                self.pos_slider.blockSignals(False)
                return
            
            self.pos_slider.blockSignals(True)
            old_pos = point.position
            point.position = value
            self.sortPoints()  
            
            new_row = self.control_points.index(point) if point in self.control_points else current_row
            
            self.sortPoints()
            self.updatePointList() 
            
            self.pos_slider.setValue(value)
            self.pos_label.setText(str(value))
            self.pos_slider.blockSignals(False)  

            
            self.updateLutAndPreview()
            print(f"[DEBUG] 点位置从 {old_pos} 修改为 {value}")

    def sortPoints(self):
        """按位置排序控制点"""
        sorted_positions = [p.position for p in self.control_points]
        self.control_points.sort(key=lambda p: p.position)
        if sorted_positions != [p.position for p in self.control_points]:
            print(f"[DEBUG] sortPoints: 顺序已变化")

    def updatePointList(self):
        """更新列表控件显示"""
        print(f"[DEBUG] updatePointList: 更新列表，共 {len(self.control_points)} 个点")

        current_row = self.point_list.currentRow()
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
        
        if 0 <= current_row < self.point_list.count():
            self.point_list.setCurrentRow(current_row)
            print(f"[DEBUG] updatePointList: 恢复选择行 {current_row}")

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
        
        saved_maps = self.map_manager.get_saved_maps()
        
        if saved_maps:
            for map_name in sorted(saved_maps.keys()):
                action = QAction(map_name, menu)
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
        
        map_name = self.map_manager.prompt_save_name(self)
        if not map_name:
            return
        
        nodes = self.getNodes()
        
        success, message = self.map_manager.save_map(map_name, nodes)
        
        if success:
            QMessageBox.information(self, "保存成功", message)
            self.load_btn.setMenu(self.createLoadMenu())
        else:
            QMessageBox.warning(self, "保存失败", message)

    def loadCustomMap(self, map_name):
        """加载指定的自定义映射"""
        print(f"[DEBUG] 加载预设: {map_name}")
        
        nodes, message = self.map_manager.load_map(map_name)
        
        if nodes:
            self.control_points.clear()

            for pos, color in nodes:
                qcolor = QColor(*color)
                self.control_points.append(ColorControlPoint(pos, qcolor))
            
            self.sortPoints()
            self.updatePointList()
            self.updateLutAndPreview()
            
            print(f"[INFO] 已加载预设: {map_name}")
        else:
            print(f"[ERROR] 加载失败: {message}")

    def deleteCustomMap(self):
        """删除已保存的自定义映射"""
        saved_maps = self.map_manager.get_saved_maps()
        
        if not saved_maps:
            QMessageBox.information(self, "删除", "没有可删除的预设")
            return
        
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
                    self.load_btn.setMenu(self.createLoadMenu())
                else:
                    QMessageBox.warning(self, "删除失败", message)