from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify,send_from_directory
import sqlite3
import os
from keyb_sim import start_keyboard_simulation  # 导入键盘模拟功能
import uuid
import os
import random
import uuid
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SAMPLE_DIR = os.path.join(BASE_DIR, 'sample_photos')
GAMER_DIR = os.path.join(BASE_DIR, 'gamer_photos')
os.makedirs(SAMPLE_DIR, exist_ok=True)
os.makedirs(GAMER_DIR, exist_ok=True)

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
    
    # 返回图片访问路径
    return jsonify({
        'status': 'success',
        'image_url': f'/api/sample_images/{chosen}'
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
    
    return jsonify({
        'status': 'success', 
        'message': '照片已保存', 
        'filename': new_filename
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