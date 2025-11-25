# component/config.py
import os

# --- 硬件与温度参数 ---
TEMP_MIN = 28.0      # 人体感兴趣温度下限
TEMP_MAX = 38.0      # 人体感兴趣温度上限
INPUT_WIDTH = 160    # 检测网络输入宽
INPUT_HEIGHT = 160   # 检测网络输入高

# --- 识别参数 ---
FACE_MATCH_THRESHOLD = 0.75  # 相似度阈值 (>0.75 认为是同一人)
DET_CONF_THRESHOLD = 0.5     # 检测置信度阈值

# --- 路径配置 ---
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEIGHTS_DIR = os.path.join(ROOT_DIR, 'weights')
DB_DIR = os.path.join(ROOT_DIR, 'face_db')
DB_FILE = os.path.join(DB_DIR, 'database.npy')

DETECTOR_PATH = os.path.join(WEIGHTS_DIR, 'detector.pth')
RECOGNIZER_PATH = os.path.join(WEIGHTS_DIR, 'recognizer.pth')