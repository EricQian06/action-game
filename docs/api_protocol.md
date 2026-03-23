# 动作闯关游戏 - 通信协议文档

## 1. 系统架构

```
┌─────────────┐      USB/UART      ┌─────────────┐      HTTP/WebSocket     ┌─────────────┐
│  STM32F103  │ ◄──────────────────► │ Python服务器 │ ◄──────────────────────► │   Web前端   │
│  + 摄像头    │    图像数据(串口)    │  (电脑端)    │    JSON数据/实时通信     │  (浏览器)    │
└─────────────┘                    └─────────────┘                         └─────────────┘
```

## 2. 串口通信协议 (STM32 ↔ Python服务器)

### 2.1 物理层配置
- 波特率: 115200 bps (可根据摄像头分辨率调整)
- 数据位: 8
- 停止位: 1
- 校验位: 无
- 流控制: 无

### 2.2 数据帧格式

| 字段 | 长度(字节) | 说明 |
|------|-----------|------|
| 帧头 | 2 | 0xAA 0x55 |
| 命令字 | 1 | 见命令定义 |
| 数据长度 | 2 | 后续数据长度(小端序) |
| 数据 | N | 实际数据 |
| 校验和 | 1 | 累加和校验(从帧头到数据) |
| 帧尾 | 2 | 0x0D 0x0A (\r\n) |

### 2.3 命令定义

| 命令字 | 名称 | 方向 | 说明 |
|--------|------|------|------|
| 0x01 | CMD_HANDSHAKE | 双向 | 握手/心跳 |
| 0x02 | CMD_START_CAPTURE | PC→STM32 | 开始拍照 |
| 0x03 | CMD_STOP_CAPTURE | PC→STM32 | 停止拍照 |
| 0x04 | CMD_IMAGE_DATA | STM32→PC | 图像数据包 |
| 0x05 | CMD_CONFIG_CAMERA | PC→STM32 | 配置摄像头参数 |
| 0x06 | CMD_STATUS_REQ | PC→STM32 | 请求状态 |
| 0x07 | CMD_STATUS_RSP | STM32→PC | 状态响应 |
| 0x08 | CMD_ERROR | 双向 | 错误报告 |

### 2.4 图像数据传输流程

```
Python服务器                          STM32开发板
    │                                    │
    │────── CMD_START_CAPTURE ──────────►│
    │                                    │
    │◄──────── CMD_STATUS_RSP ───────────│  (确认准备就绪)
    │                                    │
    │◄───────── CMD_IMAGE_DATA ──────────│  (分包发送图像)
    │                                    │
    │◄───────── CMD_IMAGE_DATA ──────────│
    │         ...                        │
    │                                    │
    │─────── CMD_STOP_CAPTURE ──────────►│
```

### 2.5 图像数据包格式

```c
typedef struct {
    uint16_t packet_seq;      // 包序号(从1开始)
    uint16_t total_packets;   // 总包数
    uint16_t data_len;        // 本包数据长度
    uint8_t  image_data[...]; // 图像数据(JPEG格式)
} ImageDataPacket;
```

## 3. HTTP/WebSocket通信协议 (Python服务器 ↔ Web前端)

### 3.1 REST API

#### 3.1.1 基础信息
- 基础URL: `http://localhost:5000/api/v1`
- 数据格式: JSON
- 字符编码: UTF-8

#### 3.1.2 API端点

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | /auth/register | 用户注册 | {username, password} | {user_id, token} |
| POST | /auth/login | 用户登录 | {username, password} | {user_id, token} |
| GET | /user/profile | 获取用户信息 | - | {user_id, username, progress} |
| GET | /game/levels | 获取关卡列表 | - | [{level_id, name, difficulty}] |
| GET | /game/level/{id} | 获取关卡详情 | - | {level_id, actions[], requirements} |
| POST | /game/start | 开始游戏 | {level_id} | {session_id, first_action} |
| POST | /game/action/result | 提交动作结果 | {session_id, action_id, success} | {score, next_action} |
| GET | /game/result/{session_id} | 获取游戏结果 | - | {total_score, passed, rewards} |
| GET | /system/status | 系统状态 | - | {stm32_connected, camera_ready} |

### 3.2 WebSocket实时通信

#### 3.2.1 连接信息
- URL: `ws://localhost:5000/ws`
- 支持事件: 游戏状态更新、倒计时、图像预览

#### 3.2.2 消息格式

```json
{
    "type": "message_type",
    "timestamp": 1234567890,
    "data": {}
}
```

#### 3.2.3 消息类型

**客户端 → 服务器:**

| 类型 | 说明 | 数据 |
|------|------|------|
| join_game | 加入游戏会话 | {session_id} |
| ready_action | 准备完成 | {action_id} |
| request_preview | 请求预览图像 | - |
| leave_game | 离开游戏 | - |

**服务器 → 客户端:**

| 类型 | 说明 | 数据 |
|------|------|------|
| game_started | 游戏开始 | {session_id, level_info} |
| action_assigned | 分配新动作 | {action_id, action_name, target_pose} |
| countdown_start | 倒计时开始 | {seconds: 3} |
| capture_triggered | 触发拍照 | {timestamp} |
| preview_image | 预览图像 | {image_base64, pose_overlay} |
| pose_detected | 检测到姿势 | {detected_pose, confidence} |
| action_result | 动作结果 | {success, score, feedback} |
| game_ended | 游戏结束 | {final_score, passed} |
| error | 错误信息 | {code, message} |

### 3.3 游戏流程时序图

```
    玩家          Web前端         Python服务器       STM32开发板      MediaPipe
     │              │                  │                  │              │
     │  选择关卡     │                  │                  │              │
     │─────────────►│                  │                  │              │
     │              │  POST /start     │                  │              │
     │              │─────────────────►│                  │              │
     │              │                  │  连接串口        │              │
     │              │                  │◄════════════════►│              │
     │              │  session_id      │                  │              │
     │              │◄─────────────────│                  │              │
     │  游戏开始界面  │                  │                  │              │
     │◄─────────────│                  │                  │              │
     │              │                  │                  │              │
     │  点击准备     │                  │                  │              │
     │─────────────►│  WebSocket: ready │                  │              │
     │              │─────────────────►│                  │              │
     │              │  倒计时3秒         │                  │              │
     │◄─────────────│◄─────────────────│                  │              │
     │              │                  │                  │              │
     │              │ 倒计时结束       │                  │              │
     │              │─────────────────►│                  │              │
     │              │                  │  串口:拍照命令    │              │
     │              │                  │─────────────────►│              │
     │              │                  │◄─────────────────│  采集图像     │
     │              │                  │  图像数据(分包)   │              │
     │              │                  │◄─────────────────│              │
     │              │                  │                  │              │
     │              │                  │  拼接图像        │              │
     │              │                  │─────────────────►│              │
     │              │                  │◄─────────────────│  关键点检测   │
     │              │                  │  姿势关键点数据   │              │
     │              │                  │                  │              │
     │              │                  │  姿势匹配算法     │              │
     │              │                  │  (对比目标姿势)   │              │
     │              │                  │                  │              │
     │              │  WebSocket: 结果  │                  │              │
     │◄─────────────│◄─────────────────│                  │              │
     │  显示结果     │                  │                  │              │
     │              │                  │                  │              │
```

## 4. 数据结构定义

### 4.1 姿势关键点数据 (MediaPipe格式)

```json
{
    "pose_landmarks": [
        {
            "x": 0.5,
            "y": 0.3,
            "z": 0.1,
            "visibility": 0.95,
            "presence": 0.99
        }
    ],
    "pose_world_landmarks": [...],
    "segmentation_mask": [...]
}
```

### 4.2 目标动作定义

```json
{
    "action_id": "action_001",
    "name": "举手",
    "name_en": "hands_up",
    "description": "双手举过头顶",
    "difficulty": 1,
    "target_pose": {
        "keypoints": [
            {"part": "left_wrist", "relation": "above", "target": "left_shoulder", "tolerance": 0.1},
            {"part": "right_wrist", "relation": "above", "target": "right_shoulder", "tolerance": 0.1}
        ]
    },
    "score_threshold": 0.75,
    "duration_seconds": 3
}
```

## 5. 错误码定义

| 错误码 | 说明 | 解决方案 |
|--------|------|----------|
| E001 | STM32连接失败 | 检查USB连接和串口配置 |
| E002 | 摄像头初始化失败 | 检查摄像头模块连接 |
| E003 | 图像传输超时 | 检查串口通信质量 |
| E004 | MediaPipe初始化失败 | 检查Python环境 |
| E005 | 姿势检测失败 | 检查图像质量和光照条件 |
| E006 | WebSocket连接失败 | 检查网络连接 |
| E007 | 游戏会话过期 | 重新开始游戏 |

## 6. 开发环境要求

### 6.1 硬件环境
- STM32F103VE开发板
- OV7670/OV7725摄像头模块
- USB转串口模块
- 笔记本电脑 (Windows/Linux/macOS)

### 6.2 软件环境
- **STM32开发**: STM32CubeIDE, HAL库
- **Python环境**: Python 3.8+, 依赖包见requirements.txt
- **前端环境**: 现代浏览器 (Chrome/Firefox/Edge)

### 6.3 Python依赖

```txt
flask==2.3.3
flask-socketio==5.3.6
flask-cors==4.0.0
mediapipe==0.10.8
opencv-python==4.8.1.78
pyserial==3.5
numpy==1.24.3
pillow==10.0.1
websockets==11.0.3
```
