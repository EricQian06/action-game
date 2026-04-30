# 动作闯关游戏 - Action Game

## 项目简介

这是一个"动作模仿挑战"游戏。系统通过 STM32 开发板上的摄像头采集玩家动作照片，使用 MediaPipe Pose 模型进行姿态识别，并与目标动作进行相似度匹配。玩家在摄像头前完成指定动作，匹配成功即可得分。

## 系统架构

```
  ┌─────────────────────────────────────────────────────────────────┐
  │                        整体架构                                  │
  ├─────────────────────────────────────────────────────────────────┤
  │                                                                 │
  │   ┌──────────────┐         UART (串口)          ┌──────────────┐│
  │   │  STM32       │  <=====================>    │ Python       ││
  │   │  开发板       │         115200 bps          │ 后端服务器    ││
  │   │              │                             │ (web/app.py) ││
  │   │ • 摄像头采集   │  PC发送'C'指令触发拍照       │              ││
  │   │ • 图像压缩    │  ────────────────────────>  │ • 硬件通信   ││
  │   │ • RLE传输    │        压缩图像数据           │ • 动作识别   ││
  │   │              │  <────────────────────────  │ • Web服务    ││
  │   └──────────────┘                             └──────┬───────┘│
  │                                                      │        │
  │                                             HTTP     │        │
  │                                                      ▼        │
  │                                             ┌──────────────┐  │
  │                                             │  Web前端      │  │
  │                                             │ (game.html)  │  │
  │                                             │              │  │
  │                                             │ • 目标动作展示│  │
  │                                             │ • 评分结果   │  │
  │                                             │ • 用户交互   │  │
  │                                             └──────────────┘  │
  │                                                                 │
  └─────────────────────────────────────────────────────────────────┘
```

## 工作流程

1. 用户在网页端点击"开始游戏"，系统随机展示一个目标动作
2. 用户模仿目标动作，点击"硬件拍照并评分"
3. PC 通过串口向 STM32 发送 `'C'` 指令
4. STM32 调用摄像头拍照，通过 RLE 压缩后串口回传
5. Python 后端接收图像，解压后保存为 `server/input.jpg`
6. 调用 MediaPipe 进行姿态识别，与目标动作计算相似度（0-1）
7. 将评分结果返回前端，显示匹配度和分数

## 项目结构

```
ActionGame_Project/
├── hardware/                      # 硬件相关
│   ├── User/
│   │   ├── main.c                 # STM32 主程序（含串口接收拍照指令）
│   │   ├── ov7725/
│   │   │   └── bsp_ov7725.c       # 摄像头驱动（含 RLE 压缩传输）
│   │   └── usart/
│   │       └── bsp_usart.c        # 串口通信配置
│   └── hardware_camera.py         # PC端硬件摄像头控制模块
│
├── server/                        # 服务端（姿态识别核心）
│   ├── action_api.py              # 动作识别 API 封装
│   ├── action_matcher.py          # 动作匹配核心逻辑
│   ├── d.py                       # 姿态嵌入/分类器
│   ├── prepare_training_data.py   # 训练数据准备脚本
│   ├── pose_samples/              # 训练样本（CSV格式）
│   │   ├── squat.csv
│   │   └── standing.csv
│   └── input.jpg                  # 硬件拍照后保存的图像
│
├── web/                           # Web 服务
│   ├── app.py                     # Flask 主程序（含硬件/评分接口）
│   ├── templates/
│   │   ├── game.html              # 游戏主页面
│   │   └── login.html             # 登录页面
│   └── gamer_photos/              # 玩家照片（可选）
│
└── README.md                      # 本文件
```

## 环境准备

### 1. 克隆项目

```bash
git clone https://github.com/EricQian06/action-game.git
cd action-game
```

### 2. 安装 Python 依赖

```bash
pip install flask numpy opencv-python mediapipe pyserial
```

### 3. 硬件准备

- STM32F103VE 开发板
- OV7725 摄像头模块（接好 FIFO 和并口线）
- USB 转串口模块（连接 STM32 的 USART1：PA9-TX, PA10-RX）
- 确认串口号（如 `COM11`）

## 使用方法

### 第一步：准备训练数据

在 `server/training_data/` 下按动作类型组织照片：

```
server/training_data/
├── squat/              # 蹲下动作照片（15张以上）
├── standing/           # 站立照片（15张以上）
├── hands_up/           # 举手照片（可选）
├── stride/             # 跨步照片（可选）
└── ...                 # 其他自定义动作
```

**拍摄要求：**
- 人物在画面中央，全身可见
- 背景尽量简洁
- 每类动作角度、姿势略有变化，提高泛化能力

### 第二步：生成姿态样本

```bash
cd server
python action_matcher.py --prepare \
    --input_dir ./training_data \
    --output_dir ./pose_samples
```

执行后会在 `server/pose_samples/` 下生成 `squat.csv`、`standing.csv` 等文件。

### 第三步：烧录 STM32 固件

1. 用 Keil 打开 `hardware/stm32.uvprojx`
2. 编译并烧录到 STM32 开发板
3. 确保 OV7725 摄像头正常初始化（屏幕显示实时画面）
4. 连接 USB 转串口，确认串口号

### 第四步：启动 Web 服务

```bash
cd web
python app.py
```

服务默认运行在 `http://localhost:5000`

### 第五步：开始游戏

1. 浏览器访问 `http://localhost:5000`
2. 登录账号（首次使用会自动初始化数据库）
3. 进入游戏页面，点击"开始游戏"
4. 网页展示目标动作图片（如深蹲）
5. 玩家在摄像头前摆好姿势
6. 点击"**硬件拍照并评分**"
7. 等待 2-5 秒，系统会：
   - 通过串口触发 STM32 拍照
   - 接收压缩图像并解压
   - 调用 MediaPipe 提取姿态关键点
   - 与目标动作样本进行相似度匹配
8. 页面显示评分结果（0%-100%）和匹配等级

## API 接口说明

| 接口 | 方法 | 功能 |
|------|------|------|
| `/api/get_action_image` | GET | 随机获取目标动作图片 |
| `/api/capture_and_score` | POST | 硬件拍照 + 动作评分 |
| `/api/input_image.jpg` | GET | 查看最近一次拍摄的照片 |
| `/api/available_actions` | GET | 获取所有可用动作类型 |

### 评分等级说明

| 分数范围 | 等级 | 显示颜色 | 说明 |
|----------|------|----------|------|
| >= 70% | 高度匹配 | 绿色 | 动作非常标准 |
| 40%-70% | 基本匹配 | 橙色 | 动作基本完成，但有偏差 |
| < 40% | 匹配度低 | 红色 | 动作差异较大，建议重试 |

## 常见问题

### Q1: 串口连接失败？
- 检查 USB 转串口驱动是否安装
- 在 `hardware_camera.py` 中修改 `port='COM11'` 为实际串口号
- 确保没有别的程序占用该串口

### Q2: 动作识别分数一直很低？
- 检查训练样本数量是否充足（每类至少 15 张）
- 确保拍摄角度和训练样本类似
- 光线要充足，人物轮廓清晰
- 尝试在 `action_matcher.py` 中调整 `scale` 参数

### Q3: 如何添加新的动作类型？
1. 在 `server/training_data/` 下新建文件夹（如 `jump/`）
2. 放入 15-20 张新动作照片
3. 重新运行 `python action_matcher.py --prepare`
4. 重启 `web/app.py`

## Git 使用

```bash
# 更新代码前同步远程
git pull

# 提交修改
git add -A
git commit -m "描述本次修改"
git push -u origin master
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 硬件层 | STM32F103VE, OV7725, UART |
| 通信层 | PySerial, 自定义 RLE 压缩协议 |
| 后端 | Python 3.8+, Flask, MediaPipe Pose |
| 前端 | HTML5, CSS3, JavaScript |
| 算法 | KNN 姿态分类, 人体关键点嵌入 |

## 许可证

本项目仅供学习交流使用。
