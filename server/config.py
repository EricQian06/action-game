"""
服务器配置文件
"""
import os

# 基础配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEBUG = True
SECRET_KEY = 'your-secret-key-change-in-production'

# 数据库配置
SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(BASE_DIR, "game.db")}'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Flask-SocketIO配置
SOCKETIO_ASYNC_MODE = 'eventlet'
SOCKETIO_CORS_ALLOWED_ORIGINS = "*"
SOCKETIO_PING_TIMEOUT = 60
SOCKETIO_PING_INTERVAL = 25

# 串口配置
SERIAL_PORT = 'COM3'  # Windows默认，Linux用 '/dev/ttyUSB0'
SERIAL_BAUDRATE = 115200
SERIAL_TIMEOUT = 5
SERIAL_READ_SIZE = 4096

# 图像传输配置
IMAGE_PACKET_SIZE = 512  # 每包数据大小
MAX_IMAGE_SIZE = 65535   # 最大图像大小(字节)
IMAGE_FORMAT = 'JPEG'
IMAGE_QUALITY = 85

# MediaPipe配置
MEDIAPIPE_MODEL_COMPLEXITY = 1  # 0=轻量, 1=完整, 2=重型
MEDIAPIPE_MIN_DETECTION_CONFIDENCE = 0.5
MEDIAPIPE_MIN_TRACKING_CONFIDENCE = 0.5

# 游戏配置
GAME_COUNTDOWN_SECONDS = 3      # 拍照倒计时(秒)
GAME_ACTION_TIMEOUT = 10        # 每个动作的超时时间(秒)
GAME_SCORE_THRESHOLD = 0.75     # 动作匹配阈值(0-1)
GAME_MAX_LEVELS = 10            # 最大关卡数

# 姿势匹配配置
POSE_SIMILARITY_THRESHOLD = 0.7  # 相似度阈值
POSE_KEYPOINT_WEIGHTS = {
    # 身体部位权重，重要部位权重更高
    'nose': 1.0,
    'left_eye': 0.8,
    'right_eye': 0.8,
    'left_ear': 0.6,
    'right_ear': 0.6,
    'left_shoulder': 1.2,
    'right_shoulder': 1.2,
    'left_elbow': 1.0,
    'right_elbow': 1.0,
    'left_wrist': 1.0,
    'right_wrist': 1.0,
    'left_hip': 1.2,
    'right_hip': 1.2,
    'left_knee': 1.0,
    'right_knee': 1.0,
    'left_ankle': 1.0,
    'right_ankle': 1.0
}

# 日志配置
LOG_LEVEL = 'DEBUG'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_FILE = os.path.join(BASE_DIR, 'logs', 'app.log')

# 静态文件配置
STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

# 跨域配置
CORS_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:5000"]
CORS_SUPPORTS_CREDENTIALS = True
