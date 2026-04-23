"""
动作闯关游戏 - Flask主应用
整合所有模块，提供Web服务、WebSocket通信和游戏逻辑处理
"""
import os
import sys
import json
import logging
import base64
import io
import cv2
import numpy as np
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_sqlalchemy import SQLAlchemy

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# 导入配置和模块
from config import *
from game_logic.game_manager import GameManager
from hardware.serial_manager import SerialManager

# 导入深蹲检测相关模块
sys.path.insert(0, os.path.join(BASE_DIR, 'detect'))
from squat_detector import SquatDetector

# 初始化Flask应用 - 使用项目根目录下的web文件夹作为静态文件
web_folder = os.path.join(os.path.dirname(BASE_DIR), 'web')
app = Flask(__name__,
            static_folder=web_folder,
            static_url_path='')

# 加载配置
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
app.config['DEBUG'] = DEBUG

# 启用CORS
CORS(app, origins=CORS_ORIGINS, supports_credentials=CORS_SUPPORTS_CREDENTIALS)

# 初始化扩展
db = SQLAlchemy(app)
socketio = SocketIO(app,
                    async_mode=SOCKETIO_ASYNC_MODE,
                    cors_allowed_origins=SOCKETIO_CORS_ALLOWED_ORIGINS,
                    ping_timeout=SOCKETIO_PING_TIMEOUT,
                    ping_interval=SOCKETIO_PING_INTERVAL)

# 配置日志
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding='utf-8') if os.path.exists(os.path.dirname(LOG_FILE)) else logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== 深蹲检测全局变量 ====================
squat_detector = None
squat_target_count = 5  # 目标深蹲次数

# ==================== 数据库模型 ====================

class User(db.Model):
    """用户模型"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # 游戏进度
    current_level = db.Column(db.Integer, default=1)
    total_score = db.Column(db.Integer, default=0)

    # 关系
    game_sessions = db.relationship('GameSession', backref='user', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'current_level': self.current_level,
            'total_score': self.total_score
        }

class GameSession(db.Model):
    """游戏会话模型"""
    __tablename__ = 'game_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    level_id = db.Column(db.Integer, nullable=False)

    # 游戏状态
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='active')  # active, completed, abandoned

    # 得分
    total_score = db.Column(db.Integer, default=0)
    actions_completed = db.Column(db.Integer, default=0)
    actions_total = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'level_id': self.level_id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'status': self.status,
            'total_score': self.total_score,
            'actions_completed': self.actions_completed,
            'actions_total': self.actions_total
        }

class ActionTemplate(db.Model):
    """动作模板模型"""
    __tablename__ = 'action_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    name_en = db.Column(db.String(100))
    description = db.Column(db.Text)
    difficulty = db.Column(db.Integer, default=1)

    # 目标姿势定义 (JSON格式)
    target_pose = db.Column(db.Text)

    # 评分参数
    score_threshold = db.Column(db.Float, default=0.75)
    duration_seconds = db.Column(db.Integer, default=3)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'name_en': self.name_en,
            'description': self.description,
            'difficulty': self.difficulty,
            'target_pose': json.loads(self.target_pose) if self.target_pose else None,
            'score_threshold': self.score_threshold,
            'duration_seconds': self.duration_seconds
        }

class GameLevel(db.Model):
    """游戏关卡模型"""
    __tablename__ = 'game_levels'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    difficulty = db.Column(db.Integer, default=1)

    # 关卡动作 (JSON数组，存储action_ids)
    action_sequence = db.Column(db.Text)

    # 通关条件
    required_score = db.Column(db.Integer, default=60)
    time_limit = db.Column(db.Integer, default=300)  # 秒

    # 解锁条件
    unlock_level_id = db.Column(db.Integer)  # 需要通关的上一关卡

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'difficulty': self.difficulty,
            'action_sequence': json.loads(self.action_sequence) if self.action_sequence else [],
            'required_score': self.required_score,
            'time_limit': self.time_limit
        }

# ==================== 全局变量 ====================

# 管理器实例 (将在应用启动时初始化)
game_manager = None
serial_manager = None

# 活跃的游戏会话存储 (内存中，用于WebSocket rooms)
active_sessions = {}

# ==================== REST API路由 ====================

@app.route('/')
def index():
    """首页"""
    return app.send_static_file('index.html')

@app.route('/api/v1/auth/register', methods=['POST'])
def register():
    """用户注册"""
    data = request.get_json()

    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'success': False, 'error': '用户名和密码不能为空'}), 400

    if User.query.filter_by(username=data['username']).first():
        return jsonify({'success': False, 'error': '用户名已存在'}), 409

    import hashlib
    password_hash = hashlib.sha256(data['password'].encode()).hexdigest()

    user = User(username=data['username'], password_hash=password_hash)
    db.session.add(user)
    db.session.commit()

    return jsonify({
        'success': True,
        'data': {
            'user_id': user.id,
            'username': user.username
        }
    }), 201

@app.route('/api/v1/auth/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.get_json()

    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'success': False, 'error': '用户名和密码不能为空'}), 400

    user = User.query.filter_by(username=data['username']).first()

    if not user:
        return jsonify({'success': False, 'error': '用户不存在'}), 404

    import hashlib
    password_hash = hashlib.sha256(data['password'].encode()).hexdigest()

    if password_hash != user.password_hash:
        return jsonify({'success': False, 'error': '密码错误'}), 401

    user.last_login = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'success': True,
        'data': {
            'user_id': user.id,
            'username': user.username,
            'current_level': user.current_level,
            'total_score': user.total_score
        }
    })

@app.route('/api/v1/user/profile', methods=['GET'])
def get_profile():
    """获取用户信息"""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': '缺少user_id参数'}), 400

    user = User.query.get(int(user_id))
    if not user:
        return jsonify({'success': False, 'error': '用户不存在'}), 404

    return jsonify({
        'success': True,
        'data': user.to_dict()
    })

@app.route('/api/v1/game/levels', methods=['GET'])
def get_levels():
    """获取关卡列表"""
    levels = GameLevel.query.all()
    return jsonify({
        'success': True,
        'data': [level.to_dict() for level in levels]
    })

@app.route('/api/v1/game/level/<int:level_id>', methods=['GET'])
def get_level(level_id):
    """获取关卡详情"""
    level = GameLevel.query.get(level_id)
    if not level:
        return jsonify({'success': False, 'error': '关卡不存在'}), 404

    # 获取动作详情
    action_ids = json.loads(level.action_sequence) if level.action_sequence else []
    actions = []
    for action_id in action_ids:
        action = ActionTemplate.query.get(action_id)
        if action:
            actions.append(action.to_dict())

    level_dict = level.to_dict()
    level_dict['actions'] = actions

    return jsonify({
        'success': True,
        'data': level_dict
    })

@app.route('/api/v1/game/start', methods=['POST'])
def start_game():
    """开始游戏"""
    data = request.get_json()

    user_id = data.get('user_id')
    level_id = data.get('level_id')

    if not user_id or not level_id:
        return jsonify({'success': False, 'error': '缺少必要参数'}), 400

    # 检查STM32连接
    if serial_manager and not serial_manager.is_connected():
        return jsonify({
            'success': False,
            'error': 'STM32未连接',
            'code': 'E001'
        }), 503

    # 创建游戏会话
    level = GameLevel.query.get(level_id)
    if not level:
        return jsonify({'success': False, 'error': '关卡不存在'}), 404

    actions = json.loads(level.action_sequence) if level.action_sequence else []

    session = GameSession(
        user_id=user_id,
        level_id=level_id,
        actions_total=len(actions)
    )
    db.session.add(session)
    db.session.commit()

    # 初始化游戏管理器
    game_manager.start_session(session.id, level_id, actions)

    # 获取第一个动作
    first_action = game_manager.get_current_action(session.id)

    return jsonify({
        'success': True,
        'data': {
            'session_id': session.id,
            'level_id': level_id,
            'first_action': first_action
        }
    })

@app.route('/api/v1/system/status', methods=['GET'])
def system_status():
    """获取系统状态"""
    return jsonify({
        'success': True,
        'data': {
            'stm32_connected': serial_manager.is_connected() if serial_manager else False,
            'camera_ready': serial_manager.camera_ready if serial_manager else False,
            'squat_detector_ready': squat_detector is not None,
            'active_sessions': len(active_sessions)
        }
    })

# ==================== WebSocket事件处理 ====================

@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    logger.info(f'客户端已连接: {request.sid}')
    emit('connected', {'status': 'ok', 'timestamp': datetime.utcnow().isoformat()})

@socketio.on('disconnect')
def handle_disconnect():
    """客户端断开连接"""
    logger.info(f'客户端已断开: {request.sid}')
    # 清理该客户端相关的深蹲检测会话
    for client_id, session_data in list(active_sessions.items()):
        if session_data.get('sid') == request.sid:
            del active_sessions[client_id]
            logger.info(f'清理深蹲会话: {client_id}')

@socketio.on('start_squat_challenge')
def handle_start_squat_challenge(data):
    """开始深蹲挑战"""
    global squat_detector
    client_id = request.sid

    logger.info(f'开始深蹲挑战: {client_id}')

    try:
        # 初始化深蹲检测器（如果尚未初始化）
        if squat_detector is None:
            samples_path = os.path.join(BASE_DIR, 'detect', 'pose_samples')
            squat_detector = SquatDetector(
                pose_samples_folder=samples_path,
                confidence_threshold=0.6,
                display_size=(640, 480)
            )
            logger.info("深蹲检测器初始化完成")

        # 重置计数器
        squat_detector.squat_counter.reset()

        # 记录会话
        active_sessions[client_id] = {
            'sid': request.sid,
            'type': 'squat_challenge',
            'started_at': datetime.utcnow(),
            'target_count': data.get('target_count', 5)
        }

        emit('squat_challenge_started', {
            'target_count': active_sessions[client_id]['target_count'],
            'message': '深蹲挑战开始！请面对摄像头做好准备。'
        })

        logger.info(f"深蹲挑战已启动，目标次数: {active_sessions[client_id]['target_count']}")

    except Exception as e:
        logger.error(f"启动深蹲挑战失败: {str(e)}")
        emit('squat_error', {'message': f'启动失败: {str(e)}'})

@socketio.on('video_frame')
def handle_video_frame(data):
    """接收视频帧并进行深蹲检测"""
    global squat_detector
    client_id = request.sid

    # 检查是否有活跃的深蹲会话
    if client_id not in active_sessions:
        return

    session = active_sessions[client_id]
    if session.get('type') != 'squat_challenge':
        return

    try:
        # 解码base64图像数据
        image_data = data.get('image', '')
        if not image_data:
            return

        # 移除data URL前缀
        if ',' in image_data:
            image_data = image_data.split(',')[1]

        # Base64解码
        img_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            return

        # 处理帧
        if squat_detector is not None:
            annotated_frame, results = squat_detector.process_frame(frame)

            # 将处理后的图像编码为base64
            _, buffer = cv2.imencode('.jpg', annotated_frame)
            processed_image = base64.b64encode(buffer).decode('utf-8')

            # 获取当前计数
            squat_count = results.get('squat_count', 0)
            target_count = session.get('target_count', 5)

            # 发送处理结果
            emit('squat_update', {
                'count': squat_count,
                'target': target_count,
                'state': results.get('state', 'unknown'),
                'image': f'data:image/jpeg;base64,{processed_image}',
                'progress': min(100, int(squat_count / target_count * 100))
            })

            # 检查是否达到目标
            if squat_count >= target_count:
                # 挑战完成
                emit('squat_completed', {
                    'final_count': squat_count,
                    'message': '恭喜！你已完成5个深蹲，闯关成功！'
                })

                # 清理会话
                if client_id in active_sessions:
                    del active_sessions[client_id]

                logger.info(f"深蹲挑战完成: {client_id}, 最终次数: {squat_count}")

    except Exception as e:
        logger.error(f"处理视频帧失败: {str(e)}")
        emit('squat_error', {'message': f'处理失败: {str(e)}'})

@socketio.on('stop_squat_challenge')
def handle_stop_squat_challenge(data):
    """停止深蹲挑战"""
    client_id = request.sid

    logger.info(f'停止深蹲挑战: {client_id}')

    if client_id in active_sessions:
        del active_sessions[client_id]

    emit('squat_stopped', {'message': '深蹲挑战已停止'})

# ==================== 初始化函数 ====================

def init_database():
    """初始化数据库"""
    with app.app_context():
        db.create_all()

        # 添加默认数据
        if not GameLevel.query.first():
            # 添加示例关卡
            levels = [
                GameLevel(
                    name='入门训练',
                    description='学习基本动作',
                    difficulty=1,
                    action_sequence='[1, 2]',
                    required_score=50
                ),
                GameLevel(
                    name='进阶挑战',
                    description='提高动作难度',
                    difficulty=2,
                    action_sequence='[3, 4, 5]',
                    required_score=60
                )
            ]
            for level in levels:
                db.session.add(level)

            # 添加示例动作
            actions = [
                ActionTemplate(
                    name='举手',
                    name_en='hands_up',
                    description='双手举过头顶',
                    difficulty=1,
                    target_pose='{"left_wrist": {"y": 0.2}, "right_wrist": {"y": 0.2}}',
                    score_threshold=0.75
                ),
                ActionTemplate(
                    name='叉腰',
                    name_en='hands_on_hips',
                    description='双手叉腰',
                    difficulty=1,
                    target_pose='{}',
                    score_threshold=0.75
                )
            ]
            for action in actions:
                db.session.add(action)

            db.session.commit()
            logger.info('数据库已初始化，添加了默认数据')

def init_managers():
    """初始化各个管理器"""
    global game_manager, serial_manager, squat_detector

    # 初始化游戏管理器
    game_manager = GameManager()
    logger.info('游戏管理器已初始化')

    # 初始化串口管理器
    try:
        serial_manager = SerialManager(
            port=SERIAL_PORT,
            baudrate=SERIAL_BAUDRATE,
            timeout=SERIAL_TIMEOUT
        )
        # 尝试连接
        serial_manager.connect()
        logger.info('串口管理器已初始化')
    except Exception as e:
        logger.warning(f'串口管理器初始化失败(可能未连接设备): {e}')
        serial_manager = None

    # 初始化深蹲检测器
    try:
        samples_path = os.path.join(BASE_DIR, 'detect', 'pose_samples')
        if os.path.exists(samples_path):
            squat_detector = SquatDetector(
                pose_samples_folder=samples_path,
                confidence_threshold=0.6,
                display_size=(640, 480)
            )
            logger.info('深蹲检测器已初始化')
        else:
            logger.warning(f'姿态样本文件夹不存在: {samples_path}')
    except Exception as e:
        logger.error(f'深蹲检测器初始化失败: {e}')
        squat_detector = None

# ==================== 主程序入口 ====================

if __name__ == '__main__':
    # 创建必要的目录
    os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'uploads'), exist_ok=True)

    # 初始化数据库
    init_database()

    # 初始化管理器
    init_managers()

    # 启动服务器
    logger.info(f'服务器启动在 http://localhost:5000')
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=DEBUG,
        use_reloader=False  # 防止重复初始化
    )
