# component/database_manager.py
import numpy as np
import os
from . import config

class FaceLibrary:
    def __init__(self):
        self.db_path = config.DB_FILE
        self.features = {} # 格式: {'name': vector_array}
        self.load_db()

    def load_db(self):
        if os.path.exists(self.db_path):
            try:
                self.features = np.load(self.db_path, allow_pickle=True).item()
                print(f"[系统] 载入人脸库，共 {len(self.features)} 人")
            except:
                print("[警告] 数据库文件损坏或为空")
        else:
            if not os.path.exists(config.DB_DIR):
                os.makedirs(config.DB_DIR)
            print("[系统] 新建空人脸库")

    def save_db(self):
        np.save(self.db_path, self.features)

    def register_person(self, name, vector):
        self.features[name] = vector
        self.save_db()
        print(f"[系统] 已注册用户: {name}")

    def identify(self, current_vector):
        """
        计算余弦相似度并返回最佳匹配
        """
        if not self.features:
            return "Unknown (库为空)", 0.0

        max_score = -1.0
        best_match = "Unknown"

        for name, db_vector in self.features.items():
            # 计算余弦相似度: (A . B) / (|A|*|B|)
            # 假设向量已经归一化过，则直接点积即可
            score = np.dot(current_vector, db_vector)
            
            if score > max_score:
                max_score = score
                best_match = name

        if max_score > config.FACE_MATCH_THRESHOLD:
            return best_match, max_score
        else:
            return "Unknown", max_score