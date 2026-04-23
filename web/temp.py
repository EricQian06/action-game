# 在 app.py 顶部补充导入
import os
import random
import uuid
from flask import send_from_directory
from werkzeug.utils import secure_filename

# 路径配置（放在 if __name__ == '__main__': 之前即可）
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SAMPLE_DIR = os.path.join(BASE_DIR, 'sample_photos')
GAMER_DIR = os.path.join(BASE_DIR, 'gamer_photos')
os.makedirs(SAMPLE_DIR, exist_ok=True)
os.makedirs(GAMER_DIR, exist_ok=True)

# ================= 替换/新增以下路由 =================

@app.route('/game')
def game():
    """游戏主界面"""
    if 'username' not in session:
        flash('请先登录！', 'warning')
        return redirect(url_for('login'))
    # 初始化本轮游戏已抽图片记录（基于会话，用户刷新或重开会重置）
    session['used_images'] = []
    return render_template('game.html')

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

@app.route('/api/sample_images/<filename>')
def serve_sample_image(filename):
    """安全地提供 sample_photos 中的图片"""
    return send_from_directory(SAMPLE_DIR, filename)

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
    # 这里可以预留后续调用大模型打分的接口
    # score = call_ai_model(save_path)
    
    return jsonify({
        'status': 'success', 
        'message': '照片已保存', 
        'filename': new_filename
    })