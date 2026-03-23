"""
动作闯关游戏 - Flask主应用
整合所有模块，提供Web服务、WebSocket通信和游戏逻辑处理
"""
import os
import sys
import json
import logging
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
from pose_detection.pose_detector import PoseDetector
from hardware.serial_manager import SerialManager

# 初始化Flask应用
app = Flask(__name__,
            static_folder='static',
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
pose_detector = None
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

    # 检查串口连接
    if serial_manager and not serial_manager.is_connected():
        return jsonify({'success': False, 'error': 'STM32未连接', 'code': 'E001'}), 503

    # 创建游戏会话
    session = GameSession(
        user_id=user_id,
        level_id=level_id,
        actions_total=len(GameLevel.query.get(level_id).action_sequence or [])
    )
    db.session.add(session)
    db.session.commit()

    # 初始化游戏管理器
    game_manager.start_session(session.id, level_id)

    return jsonify({
        'success': True,
        'data': {
            'session_id': session.id,
            'level_id': level_id
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
            'mediapipe_ready': pose_detector is not None and pose_detector.is_ready(),
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
    # 清理该客户端相关的游戏会话
    for session_id, session_data in list(active_sessions.items()):
        if session_data.get('sid') == request.sid:
            game_manager.end_session(session_id)
            del active_sessions[session_id]

@socketio.on('join_game')
def handle_join_game(data):
    """加入游戏"""
    session_id = data.get('session_id')
    if not session_id:
        emit('error', {'code': 'E007', 'message': '缺少session_id'})
        return

    # 加入房间
    room = f'game_{session_id}'
    join_room(room)

    # 记录会话信息
    active_sessions[session_id] = {
        'sid': request.sid,
        'room': room,
        'joined_at': datetime.utcnow()
    }

    logger.info(f'玩家加入游戏会话: {session_id}')
    emit('joined', {'session_id': session_id, 'status': 'ok'})

@socketio.on('leave_game')
def handle_leave_game(data):
    """离开游戏"""
    session_id = data.get('session_id')
    if session_id and session_id in active_sessions:
        room = active_sessions[session_id].get('room')
        if room:
            leave_room(room)
        del active_sessions[session_id]
        game_manager.end_session(session_id)
        logger.info(f'玩家离开游戏会话: {session_id}')

    emit('left', {'status': 'ok'})

@socketio.on('player_ready')
def handle_player_ready(data):
    """玩家准备就绪，开始倒计时"""
    session_id = data.get('session_id')
    action_index = data.get('action_index', 0)

    if not session_id:
        emit('error', {'code': 'E007', 'message': '会话无效'})
        return

    room = active_sessions.get(session_id, {}).get('room')
    if not room:
        emit('error', {'code': 'E007', 'message': '未加入游戏房间'})
        return

    logger.info(f'开始动作 {action_index} 的倒计时')

    # 发送倒计时开始事件
    socketio.emit('countdown_start', {
        'seconds': GAME_COUNTDOWN_SECONDS,
        'action_index': action_index
    }, room=room)

    # 使用后台任务执行倒计时
    socketio.start_background_task(
        countdown_and_capture,
        session_id, room, action_index
    )

def countdown_and_capture(session_id, room, action_index):
    """倒计时并触发拍照的后台任务"""
    import time

    # 倒计时
    for i in range(GAME_COUNTDOWN_SECONDS, 0, -1):
        time.sleep(1)
        socketio.emit('countdown_tick', {
            'seconds_remaining': i
        }, room=room)

    # 倒计时结束，触发拍照
    time.sleep(0.5)  # 短暂延迟确保稳定性

    socketio.emit('capture_triggered', {
        'timestamp': datetime.utcnow().isoformat(),
        'action_index': action_index
    }, room=room)

    # 触发实际的拍照流程
    capture_and_process(session_id, room, action_index)

def capture_and_process(session_id, room, action_index):
    """拍照并处理图像"""
    try:
        # 1. 通过串口命令STM32拍照
        if serial_manager and serial_manager.is_connected():
            image_data = serial_manager.capture_image()

            if not image_data:
                socketio.emit('error', {
                    'code': 'E003',
                    'message': '图像获取失败'
                }, room=room)
                return

            # 2. 保存图像并发送预览
            import base64
            image_b64 = base64.b64encode(image_data).decode('utf-8')

            socketio.emit('preview_image', {
                'image_base64': image_b64,
                'action_index': action_index
            }, room=room)

            # 3. 使用MediaPipe进行姿势检测
            if pose_detector and pose_detector.is_ready():
                result = pose_detector.detect_pose(image_data)

                if result['success']:
                    # 4. 姿势匹配
                    session = game_manager.get_session(session_id)
                    if session:
                        action = session.get_current_action()
                        match_result = pose_detector.compare_poses(
                            result['landmarks'],
                            action['target_pose']
                        )

                        # 5. 发送结果
                        socketio.emit('action_result', {
                            'action_index': action_index,
                            'success': match_result['success'],
                            'score': match_result['score'],
                            'feedback': match_result['feedback'],
                            'detected_pose': result['landmarks']
                        }, room=room)

                        # 6. 更新游戏状态
                        game_manager.update_action_result(
                            session_id, action_index, match_result
                        )

                        # 7. 检查是否需要进入下一个动作
                        next_action = game_manager.get_next_action(session_id)
                        if next_action:
                            socketio.emit('action_assigned', {
                                'action_index': action_index + 1,
                                'action': next_action,
                                'ready_to_start': True
                            }, room=room)
                        else:
                            # 游戏结束
                            final_result = game_manager.end_session(session_id)
                            socketio.emit('game_ended', final_result, room=room)
                    else:
                        socketio.emit('error', {
                            'code': 'E007',
                            'message': '游戏会话不存在'
                        }, room=room)
                else:
                    socketio.emit('error', {
                        'code': 'E005',
                        'message': f'姿势检测失败: {result.get("error", "未知错误")}'
                    }, room=room)
            else:
                socketio.emit('error', {
                    'code': 'E004',
                    'message': 'MediaPipe未就绪'
                }, room=room)
        else:
            socketio.emit('error', {
                'code': 'E001',
                'message': 'STM32未连接'
            }, room=room)

    except Exception as e:
        logger.error(f"拍照处理失败: {str(e)}")
        socketio.emit('error', {
            'code': 'E999',
            'message': f'处理异常: {str(e)}'
        }, room=room)

# ==================== REST API路由 ====================

@app.route('/api/v1/system/status', methods=['GET'])
def system_status():
    """获取系统状态"""
    return jsonify({
        'success': True,
        'data': {
            'stm32_connected': serial_manager.is_connected() if serial_manager else False,
            'camera_ready': serial_manager.camera_ready if serial_manager else False,
            'mediapipe_ready': pose_detector.is_ready() if pose_detector else False,
            'active_sessions': len(active_sessions),
            'server_time': datetime.utcnow().isoformat()
        }
    })

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

@app.route('/api/v1/game/levels', methods=['GET'])
def get_levels():
    """获取关卡列表"""
    levels = GameLevel.query.all()
    return jsonify({
        'success': True,
        'data': [level.to_dict() for level in levels]
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
    global game_manager, pose_detector, serial_manager

    # 初始化游戏管理器
    game_manager = GameManager()
    logger.info('游戏管理器已初始化')

    # 初始化姿势检测器
    try:
        pose_detector = PoseDetector()
        logger.info('姿势检测器已初始化')
    except Exception as e:
        logger.error(f'姿势检测器初始化失败: {e}')
        pose_detector = None

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
