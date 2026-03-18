# component/color_map_manager.py
import json
import os
from PySide2.QtWidgets import QInputDialog, QMessageBox

class ColorMapManager:
    def __init__(self, config_dir="custom_maps"):
        self.config_dir = config_dir
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
    
    def get_saved_maps(self):
        """获取所有已保存的颜色映射配置"""
        maps = {}
        if os.path.exists(self.config_dir):
            for filename in os.listdir(self.config_dir):
                if filename.endswith('.json'):
                    map_name = filename[:-5] 
                    maps[map_name] = os.path.join(self.config_dir, filename)
        return maps
    
    def save_map(self, map_name, nodes):
        """保存颜色映射配置到文件"""
        if not map_name or not map_name.strip():
            return False, "请输入有效的名称"
        
        map_name = map_name.strip()
        
        filepath = os.path.join(self.config_dir, f"{map_name}.json")

        if os.path.exists(filepath):
            reply = QMessageBox.question(
                None, "覆盖确认", 
                f"已存在名为'{map_name}'的配置，是否覆盖？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return False, "已取消保存"
        
        try:
            serializable_nodes = []
            for pos, color in nodes:
                serializable_nodes.append({
                    "position": pos,
                    "color": color  
                })
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    "name": map_name,
                    "nodes": serializable_nodes,
                    "type": "thermal_color_map"
                }, f, indent=2, ensure_ascii=False)
            
            return True, f"已保存为 '{map_name}'"
            
        except Exception as e:
            return False, f"保存失败: {str(e)}"
    
    def load_map(self, map_name):
        """从文件加载颜色映射配置"""
        filepath = os.path.join(self.config_dir, f"{map_name}.json")
        
        if not os.path.exists(filepath):
            return None, f"配置文件不存在: {map_name}"
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            nodes = []
            for node in data.get("nodes", []):
                pos = node.get("position", 0)
                color = tuple(node.get("color", (0, 0, 0)))
                nodes.append((pos, color))
            
            return nodes, "加载成功"
            
        except Exception as e:
            return None, f"加载失败: {str(e)}"
    
    def delete_map(self, map_name):
        """删除已保存的颜色映射配置"""
        filepath = os.path.join(self.config_dir, f"{map_name}.json")
        
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                return True, f"已删除 '{map_name}'"
            except Exception as e:
                return False, f"删除失败: {str(e)}"
        else:
            return False, f"配置文件不存在: {map_name}"
    
    def prompt_save_name(self, parent=None):
        """弹出对话框让用户输入保存的名称"""
        map_name, ok = QInputDialog.getText(
            parent, "保存颜色映射", 
            "请输入颜色映射名称:", 
            text="我的配色"
        )
        
        if ok and map_name:
            return map_name.strip()
        return None