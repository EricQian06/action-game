from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify,send_from_directory
import sqlite3
import os
import sys
import uuid
import random
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SAMPLE_DIR = os.path.join(BASE_DIR, 'sample_photos')
GAMER_DIR = os.path.join(BASE_DIR, 'gamer_photos')
os.makedirs(SAMPLE_DIR, exist_ok=True)
os.makedirs(GAMER_DIR, exist_ok=True)

# 添加server目录到Python路径以导入动作识别模块
PROJECT_DIR = os.path.dirname(BASE_DIR)
SERVER_DIR = os.path.join(PROJECT_DIR, 'server')
HARDWARE_DIR = os.path.join(PROJECT_DIR, 'hardware')
sys.path.insert(0, SERVER_DIR)
sys.path.insert(0, HARDWARE_DIR)

# 导入键盘模拟功能和动作识别API
try:
    from keyb_sim import start_keyboard_simulation
except ImportError:
    start_keyboard_simulation = lambda: None
    print("[Warning] keyb_sim module not found")

# 导入动作识别API
try:
    from action_api import ActionRecognitionAPI
    # 初始化动作识别API（全局单例）
    action_api = ActionRecognitionAPI(pose_samples_folder=os.path.join(SERVER_DIR, 'pose_samples'))
    print(f"[Info] 动作识别API初始化成功，可用动作: {action_api.get_available_actions()}")
except Exception as e:
    print(f"[Warning] 动作识别API初始化失败: {e}")
    action_api = None

# 导入硬件摄像头模块
try:
    from hardware_camera import HardwareCamera
    hardware_camera = HardwareCamera(port='COM11')
    print("[Info] 硬件摄像头模块加载成功")
except Exception as e:
    print(f"[Warning] 硬件摄像头模块加载失败: {e}")
    hardware_camera = None

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # 用于会话管理和闪存消息，生产环境请更换为复杂随机字符串

DB_NAME = 'database.db'

# --- 数据库辅助函数 ---
def get_db_connection():
    """建立数据库连接"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # 让结果可以通过列名访问
    return conn

def init_db():
    """初始化数据库表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 创建玩家表
    # username: 用户名 (唯一索引，防止重复)
    # password: 密码 (实际项目中应存储哈希值，这里为了演示简单直接存储明文，建议后续加密)
    # progress: 游戏进度 (预留字段，默认空字符串或 JSON 字符串)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            progress TEXT DEFAULT '{}'
        )
    ''')
    
    conn.commit()
    conn.close()
    print("数据库初始化完成。")


# --- 路由逻辑 ---

#game
@app.route('/game')
def game():
    """游戏主界面"""
    if 'username' not in session:
        flash('请先登录！', 'warning')
        return redirect(url_for('login'))
    # 初始化本轮游戏已抽图片记录（基于会话，用户刷新或重开会重置）
    session['used_images'] = []
    return render_template('game.html')

#login
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    
    if request.method == 'POST':
        action = request.form.get('action')
        username = request.form.get('username')
        password = request.form.get('password')
        
        db = get_db_connection()
        
        if action == 'register':
            # 注册逻辑
            try:
                db.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
                db.commit()
                return render_template('login.html', error=None, success_msg="注册成功，请登录")
            except sqlite3.IntegrityError:
                error = "用户名已存在，请换一个"
                
        elif action == 'login':
            # 登录逻辑
            user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            
            if user is None:
                error = "用户不存在"  # <--- 这个字符串会传到 HTML 的 {{ error }}
            elif user['password'] != password:
                error = "密码错误"
            else:
                session['username'] = user['username']
                return redirect(url_for('game'))
        
        db.close()

    # 如果是 GET 请求，或者 POST 但出错了，渲染页面并传入 error
    return render_template('login.html', error=error)

#home page
@app.route('/')
def index():
    # 选项1: 重定向到登录页
    return redirect(url_for('login'))

@app.route('/api/get_action_image')
def get_action_image():
    """返回一张未使用过的随机动作图片"""
    images = [f for f in os.listdir(SAMPLE_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if not images:
        return jsonify({'status': 'error', 'message': 'sample_photos 文件夹为空，请放入参考图片'})

    used = session.get('used_images', [])
    available = [f for f in images if f not in used]
    
    # 如果全部抽完，则清空记录重新开始轮询
    if not available:
        session['used_images'] = []
        available = images[:]

    chosen = random.choice(available)
    session['used_images'].append(chosen)

    # 从文件名推断目标动作类型
    # 例如: squat_01.jpg -> squat, hands_up_02.png -> hands_up
    target_action = 'squat'  # 默认动作
    filename_lower = chosen.lower()

    if 'squat' in filename_lower:
        target_action = 'squat'
    elif 'hands_up' in filename_lower or 'handsup' in filename_lower or 'hand' in filename_lower:
        target_action = 'hands_up'
    elif 'stride' in filename_lower or 'step' in filename_lower:
        target_action = 'stride'
    elif 'stand' in filename_lower:
        target_action = 'standing'

    # 保存当前目标动作到session
    session['current_action'] = target_action

    # 返回图片访问路径
    return jsonify({
        'status': 'success',
        'image_url': f'/api/sample_images/{chosen}',
        'target_action': target_action,
        'filename': chosen
    })

#serve_sample_image
@app.route('/api/sample_images/<filename>')
def serve_sample_image(filename):
    """安全地提供 sample_photos 中的图片"""
    return send_from_directory(SAMPLE_DIR, filename)

#save_gamer_photo
@app.route('/api/save_gamer_photo', methods=['POST'])
def save_gamer_photo():
    """接收前端传来的抓拍照片并保存"""
    if 'photo' not in request.files:
        return jsonify({'status': 'error', 'message': '未接收到图片文件'})
    
    file = request.files['photo']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': '文件名为空'})
        
    # 生成唯一文件名防止覆盖: 用户名_时间戳_UUID.jpg
    ext = file.filename.rsplit('.', 1)[-1] if '.' in file.filename else 'jpg'
    new_filename = f"{session['username']}_{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(GAMER_DIR, new_filename)
    
    file.save(save_path)

    # 从session中获取当前目标动作类型（如果有）
    target_action = session.get('current_action', 'squat')

    return jsonify({
        'status': 'success',
        'message': '照片已保存',
        'filename': new_filename,
        'target_action': target_action
    })

#capture_hardware
@app.route('/api/capture_hardware', methods=['POST'])
def capture_hardware():
    """
    触发硬件摄像头拍照
    通过串口发送指令给STM32，接收图像并保存到 server/input.jpg
    """
    if hardware_camera is None:
        return jsonify({
            'status': 'error',
            'message': '硬件摄像头模块未初始化，请检查串口连接和硬件模块'
        }), 500

    try:
        # 拍照并保存到 server/input.jpg
        input_path = os.path.join(SERVER_DIR, 'input.jpg')
        result = hardware_camera.capture(output_path=input_path)

        if result['success']:
            return jsonify({
                'status': 'success',
                'message': result['message'],
                'image_path': '/api/input_image.jpg',
                'saved_path': result['path']
            })
        else:
            return jsonify({
                'status': 'error',
                'message': result['message']
            }), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': f'硬件拍照出错: {str(e)}'
        }), 500


#serve_input_image
@app.route('/api/input_image.jpg')
def serve_input_image():
    """提供 server/input.jpg 图片"""
    return send_from_directory(SERVER_DIR, 'input.jpg')


#capture_and_score
@app.route('/api/capture_and_score', methods=['POST'])
def capture_and_score():
    """
    一键拍照+评分
    1. 触发硬件摄像头拍照
    2. 对拍摄的照片进行动作评分
    """
    data = request.get_json() or {}
    target_action = data.get('target_action', session.get('current_action', 'squat'))

    # 检查硬件摄像头
    if hardware_camera is None:
        return jsonify({
            'status': 'error',
            'message': '硬件摄像头模块未初始化'
        }), 500

    # 检查动作识别API
    if action_api is None:
        return jsonify({
            'status': 'error',
            'message': '动作识别API未初始化'
        }), 500

    try:
        # Step 1: 拍照
        input_path = os.path.join(SERVER_DIR, 'input.jpg')
        capture_result = hardware_camera.capture(output_path=input_path)

        if not capture_result['success']:
            return jsonify({
                'status': 'error',
                'message': f'拍照失败: {capture_result["message"]}'
            }), 500

        # Step 2: 评分
        score_result = action_api.recognize(input_path, target_action)

        if not score_result['success']:
            return jsonify({
                'status': 'error',
                'message': score_result.get('error', '评分失败'),
                'capture_success': True
            }), 500

        score = score_result['score']

        # 判断匹配等级
        if score >= 0.7:
            match_level = 'high'
            match_text = '高度匹配'
        elif score >= 0.4:
            match_level = 'medium'
            match_text = '基本匹配'
        else:
            match_level = 'low'
            match_text = '匹配度低'

        return jsonify({
            'status': 'success',
            'score': round(score, 4),
            'match_level': match_level,
            'match_text': match_text,
            'target_action': target_action,
            'image_path': '/api/input_image.jpg',
            'landmarks_detected': score_result.get('landmarks_detected', False),
            'message': capture_result['message']
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': f'拍照评分出错: {str(e)}'
        }), 500


#score_gamer_photo
@app.route('/api/score_photo', methods=['POST'])
def score_photo():
    """
    对玩家照片进行动作评分

    请求体: { filename: "用户名_UUID.jpg", target_action: "squat" }
    响应: { status: "success", score: 0.85, match_level: "high", ... }
    """
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': '请求体不能为空'}), 400

    filename = data.get('filename')
    target_action = data.get('target_action', 'squat')

    if not filename:
        return jsonify({'status': 'error', 'message': '缺少filename参数'}), 400

    # 检查文件是否存在
    photo_path = os.path.join(GAMER_DIR, filename)
    if not os.path.exists(photo_path):
        return jsonify({'status': 'error', 'message': f'照片不存在: {filename}'}), 404

    # 检查动作识别API是否可用
    if action_api is None:
        return jsonify({
            'status': 'error',
            'message': '动作识别API未初始化，请检查server/pose_samples目录是否存在训练数据'
        }), 500

    # 检查目标动作是否有效
    available_actions = action_api.get_available_actions()
    if target_action not in available_actions:
        return jsonify({
            'status': 'error',
            'message': f'未知的动作类型: {target_action}',
            'available_actions': available_actions
        }), 400

    # 执行动作识别
    try:
        result = action_api.recognize(photo_path, target_action)

        if not result['success']:
            return jsonify({
                'status': 'error',
                'message': result.get('error', '识别失败'),
                'landmarks_detected': result.get('landmarks_detected', False)
            }), 500

        score = result['score']

        # 根据分数判断匹配等级
        if score >= 0.7:
            match_level = 'high'
            match_text = '高度匹配'
        elif score >= 0.4:
            match_level = 'medium'
            match_text = '基本匹配'
        else:
            match_level = 'low'
            match_text = '匹配度低'

        return jsonify({
            'status': 'success',
            'score': round(score, 4),
            'match_level': match_level,
            'match_text': match_text,
            'target_action': target_action,
            'filename': filename,
            'landmarks_detected': result.get('landmarks_detected', False)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': f'评分过程出错: {str(e)}'
        }), 500


#get_available_actions
@app.route('/api/available_actions', methods=['GET'])
def get_available_actions():
    """获取所有可用的动作类型"""
    if action_api is None:
        return jsonify({
            'status': 'error',
            'message': '动作识别API未初始化'
        }), 500

    actions = action_api.get_available_actions()
    # 动作名称映射
    action_names = {
        'squat': '深蹲',
        'standing': '站立',
        'hands_up': '举手',
        'stride': '跨步',
        'jump': '跳跃',
        'sit': '坐下'
    }

    return jsonify({
        'status': 'success',
        'actions': actions,
        'action_names': {k: action_names.get(k, k) for k in actions}
    })


#logout
@app.route('/logout')
def logout():
    """退出登录"""
    session.clear()
    flash('已安全退出。', 'info')
    return redirect(url_for('login'))

@app.route('/api/action', methods=['POST'])
def handle_action():
    """
    处理来自键盘模拟器或硬件的动作请求
    兼容旧版模拟器的请求入口
    """
    try:
        data = request.get_json() or {}
        action_type = data.get('type', 'unknown')
        
        # 记录日志
        print(f"[API] 收到动作请求: {action_type}")
        
        # 返回成功响应，避免模拟器报错
        # 注意：这里仅做响应，实际登录/注册逻辑需调用具体接口
        # 如果模拟器需要自动触发登录，请修改模拟器代码指向 /api/k1_login
        return jsonify({
            "status": "success",
            "message": f"收到动作: {action_type}。提示：请直接调用 /api/k1_login 或 /api/k2_register 进行业务操作",
            "data": data
        }), 200
        
    except Exception as e:
        print(f"[API] 处理动作请求出错: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

#键盘模拟代码
# 在应用启动前开启键盘模拟线程
# 注意：如果不需要键盘模拟，可以注释掉下面这行
start_keyboard_simulation()

@app.route('/api/send', methods=['POST'])
def send_command():
    data = request.json
    key = data.get('key')
    print(f"[Web接口] 收到请求: {key}")
    # 这里未来可以调用 key_listener.py 中的串口发送逻辑
    return jsonify({"status": "success", "message": f"{key} command received"})




if __name__ == '__main__':
    # 启动前初始化数据库
    if not os.path.exists(DB_NAME):
        init_db()
    else:
        # 即使数据库存在，也确保表结构正确（可选）
        init_db()
        
    app.run(debug=True, port=5000)