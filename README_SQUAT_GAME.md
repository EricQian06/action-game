# 深蹲闯关游戏 - 完整实现

## 功能概述

已实现所有要求的功能：

1. ✅ 网页点击"开始"按钮 → 打开摄像头
2. ✅ 实时显示深蹲检测处理后的图像
3. ✅ 深蹲计数（目标5次）
4. ✅ 计数达到5自动停止
5. ✅ 显示"闯关成功"
6. ✅ 点击确认后返回开始界面

## 修改的文件详情

### 1. server/app.py
**新增内容：**
- 导入深蹲检测器：`from squat_detector import SquatDetector`
- 全局变量：`squat_detector`, `squat_target_count`
- WebSocket事件：
  - `handle_start_squat_challenge` - 开始挑战
  - `handle_video_frame` - 处理视频帧并检测深蹲
  - `handle_stop_squat_challenge` - 停止挑战
- 在`init_managers()`中初始化深蹲检测器

### 2. web/index.html
**页面结构（4个screen）：**
- `#loading-screen` - 加载动画
- `#start-screen` - 开始页面（规则+开始按钮+系统状态）
- `#squat-screen` - 深蹲挑战（摄像头+计数器+进度条+状态）
- `#success-screen` - 成功页面（闯关成功+确认按钮）

### 3. web/js/app.js
**主要模块：**
- `CONFIG` - 配置（API地址、WebSocket地址、目标计数）
- `AppState` - 应用状态管理
- `Utils` - 工具函数（Toast提示）
- `SocketManager` - WebSocket连接和事件处理
- `ScreenManager` - 页面切换管理
- `SquatUI` - 深蹲挑战UI控制（摄像头、帧发送、显示更新）
- `SystemCheck` - 系统状态检查

### 4. web/css/style.css
**样式模块：**
- CSS变量（颜色、尺寸、动画）
- 基础重置和工具类
- 通用按钮样式
- 屏幕容器样式
- 加载画面样式
- 开始页面样式（规则、状态指示器）
- 深蹲挑战页面样式（视频面板、计数器、进度条）
- 成功页面样式（动画、统计）
- Toast提示样式
- 响应式设计（移动端适配）
- 动画效果（脉冲、淡入、弹跳等）

## 启动方法

```bash
# 1. 进入服务器目录
cd server

# 2. 启动服务器
python app.py

# 3. 浏览器访问
http://localhost:5000
```

## 使用流程

1. 等待页面加载，检测器初始化（状态灯变绿）
2. 阅读游戏规则
3. 点击"开始挑战"按钮
4. 允许浏览器访问摄像头
5. 面对摄像头，保持全身在画面内
6. 完成深蹲动作，观察实时计数
7. 计数达到5次，自动显示"闯关成功"
8. 点击"确认"按钮返回开始界面

## 技术特点

- **实时视频传输**：WebSocket + Canvas 捕获和发送视频帧
- **姿态检测**：MediaPipe Pose 提取33个人体关键点
- **动作识别**：KNN分类器识别深蹲姿态
- **计数逻辑**：状态机跟踪深蹲完整循环（站立->下蹲->站起）
- **实时反馈**：服务器处理后的图像和计数实时推送到前端

## 注意事项

1. 确保 `server/detect/pose_samples/` 目录下有训练样本（`standing.csv` 和 `squat.csv`）
2. 使用Chrome或Edge浏览器获得最佳体验
3. 确保光线充足，身体在画面内清晰可见
4. 穿着便于识别身体轮廓的衣物

---

所有功能已完整实现，可以直接运行测试！🎮✅
