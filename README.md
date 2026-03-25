# 动作闯关游戏 - Action Game

## 项目简介

这是一个基于STM32F103VE开发板、MediaPipe姿势识别和Web技术的"动作闯关"游戏。玩家通过摄像头完成各种体感动作，与系统随机生成的目标动作进行匹配，获得分数并解锁更多关卡。

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              系统架构图                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────────┐         USB/UART         ┌──────────────────────┐   │
│   │  STM32F103   │ ◄──────────────────────► │     Python服务器      │   │
│   │  + OV7670   │      图像数据(串口)       │    (Flask+SocketIO)   │   │
│   └──────────────┘                            └──────────┬───────────┘   │
│                                                          │               │
│   硬件层(成员A)                                          │ WebSocket    │
│                                                          ▼               │
│                                               ┌──────────────────────┐   │
│                                               │      Web前端         │   │
│                                               │  (HTML+CSS+JS)       │   │
│                                               └──────────────────────┘   │
│                                                                         │
│   上位机层(成员B)         算法层(成员C)            展示层(成员D)        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 技术栈

### 硬件层
- **MCU**: STM32F103VE (ARM Cortex-M3)
- **摄像头**: OV7670 / OV7725
- **通信**: USB转串口 (115200/921600 bps)

### 上位机层
- **语言**: Python 3.8+
- **Web框架**: Flask 2.3.3
- **实时通信**: Flask-SocketIO 5.3.6
- **串口通信**: PySerial 3.5

### 算法层
- **姿势检测**: MediaPipe Pose 0.10.8
- **图像处理**: OpenCV 4.8.1
- **数学计算**: NumPy 1.24.3

### 展示层
- **前端**: HTML5 + CSS3 + JavaScript (ES6+)
- **实时通信**: Socket.IO Client 4.5.4
- **UI组件**: 原生组件 + 自定义样式

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/EricQian06/action-game.git
cd action-game
```

### 2. 安装依赖

```bash
cd server
pip install -r requirements.txt
```

### 3. 初始化数据库

```bash
cd tools
python setup_db.py
```

### 4. 启动服务器

```bash
cd server
python app.py
```

服务器将在 `http://localhost:5000` 启动

### 5. 启动前端

直接使用浏览器打开 `web/index.html` 或使用Live Server:

```bash
cd web
live-server --port=3000
```

### 6. 连接硬件

1. 将STM32开发板通过USB连接到电脑
2. 确认串口号(COM3或类似)
3. 在配置文件中修改串口设置
4. 复位STM32开发板

## 项目结构说明

```
ActionGame_Project/
├── docs/                   # 项目文档
│   ├── api_protocol.md    # API通信协议详细说明
│   ├── 任务分工.md         # 五人任务分工
│   └── hardware_setup.md  # 硬件接线和配置指南
│
├── hardware/              # 硬件相关代码
│   └── STM32/
│       ├── camera_driver.c    # 摄像头驱动实现
│       ├── camera_driver.h    # 驱动头文件
│       ├── main.c             # 主程序入口
│       └── stm32f10x_conf.h   # 配置文件
│
├── server/                # Python服务器
│   ├── app.py             # Flask主应用
│   ├── config.py          # 配置文件
│   ├── requirements.txt     # Python依赖
│   │
│   ├── game_logic/        # 游戏逻辑模块
│   │   ├── __init__.py
│   │   └── game_manager.py
│   │
│   ├── pose_detection/    # 姿势检测模块
│   │   ├── __init__.py
│   │   └── pose_detector.py
│   │
│   ├── hardware/          # 硬件通信模块
│   │   ├── __init__.py
│   │   └── serial_manager.py
│   │
│   └── utils/             # 工具模块
│       ├── __init__.py
│       └── logger.py
│
├── web/                   # Web前端
│   ├── index.html         # 主页面
│   │
│   ├── css/               # 样式
│   │   └── style.css
│   │
│   ├── js/                # JavaScript
│   │   └── app.js
│   │
│   └── assets/            # 静态资源
│       ├── poses/         # 姿势示例图
│       └── icons/         # 图标
│
├── tools/                 # 工具脚本
│   ├── setup_db.py       # 数据库初始化
│   ├── test_serial.py    # 串口测试工具
│   └── test_camera.py    # 摄像头测试工具
│
├── tests/                 # 测试代码
│   ├── test_game_logic.py
│   ├── test_pose_detection.py
│   └── test_serial_comm.py
│
├── .gitignore            # Git忽略文件
├── README.md             # 项目说明
└── LICENSE               # 许可证

```

## 开发规范

### 代码风格
- **Python**: 遵循 PEP 8 规范
- **C**: 使用 K&R 风格
- **JavaScript**: 使用 ESLint 推荐配置

### 提交规范
```
<type>(<scope>): <subject>

<body>

<footer>
```

类型包括:
- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档更新
- `style`: 代码格式(不影响代码运行的变动)
- `refactor`: 重构
- `test`: 增加测试
- `chore`: 构建过程或辅助工具的变动

### 分支管理
- `main`: 主分支，稳定版本
- `develop`: 开发分支，日常开发
- `feature/xxx`: 特性分支
- `bugfix/xxx`: 修复分支

## 常见问题

### Q1: 串口连接失败怎么办?
A: 检查以下几点:
1. 确认USB转串口驱动已安装
2. 检查串口号是否正确(COM3/COM4等)
3. 确认波特率设置为115200
4. 检查STM32是否正确烧录程序

### Q2: MediaPipe检测不到姿势?
A: 可能的原因:
1. 图像太暗或太亮，调整光照
2. 人距离摄像头太远或太近(建议2-3米)
3. 穿着衣服与背景颜色相近，建议穿深色衣服
4. 动作太快，放慢动作

### Q3: 图像传输太慢?
A: 优化方法:
1. 提高串口波特率到921600
2. 降低图像分辨率到QVGA(320x240)
3. 提高JPEG压缩质量到60-70
4. 使用DMA传输

### Q4: WebSocket连接失败?
A: 检查以下几点:
1. Flask服务器是否已启动
2. Socket.IO版本是否匹配(客户端4.x与服务器5.x)
3. 浏览器控制台是否有CORS错误
4. 防火墙是否拦截了5000端口

## 联系方式

如有问题或建议，请联系项目团队:

- **项目主页**: https://github.com/EricQian06/action-game
- **问题反馈**: https://github.com/EricQian06/action-game/issues

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 致谢

感谢以下开源项目:
- [MediaPipe](https://mediapipe.dev/) by Google
- [Flask](https://flask.palletsprojects.com/) by Pallets Projects
- [Socket.IO](https://socket.io/) by Socket.IO Team
- [STM32 Standard Peripheral Library](https://www.st.com/) by STMicroelectronics

---

**动作闯关游戏团队**

*让运动更有趣，让游戏更健康*
