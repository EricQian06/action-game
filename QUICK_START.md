# 深蹲闯关游戏 - 快速启动指南

## 环境要求
- Python 3.8+
- OpenCV
- MediaPipe
- Flask
- Flask-SocketIO
- NumPy

## 安装依赖
```bash
pip install flask flask-socketio flask-sqlalchemy flask-cors opencv-python mediapipe numpy eventlet
```

## 目录结构
```
ActionGame_Project/
├── server/
│   ├── app.py              # 主服务器 (已修改)
│   ├── config.py           # 配置文件
│   └── detect/             # 检测模块
│       ├── d.py            # 姿态分类器
│       ├── squat_counter.py    # 深蹲计数器
│       ├── squat_detector.py   # 深蹲检测器
│       └── pose_samples/       # 训练样本目录
└── web/
    ├── index.html          # 主页面 (已修改)
    ├── css/
    │   └── style.css       # 样式 (已修改)
    └── js/
        └── app.js          # 前端逻辑 (已修改)
```

## 启动步骤

### 1. 准备训练数据
确保 `server/detect/pose_samples/` 目录下有以下文件：
- `standing.csv` - 站立姿势样本
- `squat.csv` - 深蹲姿势样本

如果没有，需要先运行训练数据准备脚本采集样本。

### 2. 启动服务器
```bash
cd server
python app.py
```

服务器启动后会显示：
- 数据库初始化信息
- 检测器初始化状态
- 服务器地址 (http://localhost:5000)

### 3. 打开浏览器访问
```
http://localhost:5000
```

### 4. 使用流程
1. 等待页面加载完成（显示"检测器就绪"）
2. 点击"开始挑战"按钮
3. 允许浏览器访问摄像头
4. 面对摄像头，保持全身在画面内
5. 完成深蹲动作，观察计数变化
6. 计数达到5次后，显示"闯关成功"
7. 点击"确认"按钮返回开始界面

## 常见问题

### Q: 摄像头无法启动
A: 检查浏览器权限设置，确保允许访问摄像头。使用HTTPS或localhost访问。

### Q: 深蹲检测不准确
A: 确保：
- 光线充足
- 全身在画面内
- 动作标准（下蹲到位）
- 穿着便于识别身体轮廓的衣物

### Q: 检测器未就绪
A: 检查：
- 训练样本是否存在 (`pose_samples/` 目录)
- 服务器控制台是否有错误信息
- 依赖库是否安装完整

## 技术说明

### 实现原理
1. **前端**：使用 WebRTC 获取摄像头视频流，通过 Canvas 捕获帧，WebSocket 发送到服务器
2. **后端**：接收视频帧，使用 MediaPipe 提取人体姿态关键点，KNN分类器识别深蹲动作
3. **计数逻辑**：状态机跟踪深蹲动作（站立->下蹲->站起），完成一个循环计数+1
4. **实时反馈**：处理后的图像和计数通过 WebSocket 实时推送到前端显示

### 关键技术栈
- Flask + Flask-SocketIO：Web服务器和实时通信
- MediaPipe Pose：人体姿态检测
- OpenCV：图像处理
- KNN分类器：姿态分类
- WebRTC + Canvas：摄像头访问和帧捕获
