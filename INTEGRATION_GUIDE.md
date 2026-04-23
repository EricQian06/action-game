# 动作识别评分系统集成指南

## 概述

已经将动作识别评分功能集成到游戏网页中。系统会自动识别玩家照片与目标动作的相似度，并显示评分结果。

## 主要修改

### 1. 后端修改 (web/app.py)

#### 新增导入和初始化
```python
# 添加server目录到Python路径
PROJECT_DIR = os.path.dirname(BASE_DIR)
SERVER_DIR = os.path.join(PROJECT_DIR, 'server')
sys.path.insert(0, SERVER_DIR)

# 导入动作识别API
from action_api import ActionRecognitionAPI

# 初始化动作识别API（全局单例）
action_api = ActionRecognitionAPI(pose_samples_folder=os.path.join(SERVER_DIR, 'pose_samples'))
```

#### 新增API端点

1. **获取目标动作图片** (`/api/get_action_image`)
   - 返回随机动作图片和目标动作类型
   - 从图片文件名推断动作类型

2. **保存玩家照片** (`/api/save_gamer_photo`)
   - 保存玩家拍摄的照片
   - 返回文件名和目标动作

3. **评分接口** (`/api/score_photo`)
   - 对玩家照片进行动作评分
   - 请求体: `{ filename: "xxx.jpg", target_action: "squat" }`
   - 响应: `{ status: "success", score: 0.85, match_level: "high", ... }`

4. **获取可用动作** (`/api/available_actions`)
   - 返回所有可用的动作类型列表

### 2. 前端修改 (web/templates/game.html)

#### 新增评分显示面板
```html
<div id="scorePanel" class="score-panel">
    <div class="score-label">动作匹配度</div>
    <div class="score-value" id="scoreValue">0%</div>
    <div class="score-bar">
        <div class="score-bar-fill" id="scoreBarFill" style="width: 0%"></div>
    </div>
    <div id="scoreMessage">正在评分...</div>
    <div id="targetActionDisplay"></div>
</div>
```

#### 新增JavaScript功能

1. **评分请求函数** (`scoreGamerPhoto`)
   - 调用后端评分接口
   - 接收并显示评分结果

2. **评分显示函数** (`displayScore`)
   - 显示动画效果的分数条
   - 根据匹配等级显示不同颜色和消息
   - 显示目标动作名称

#### 游戏流程

1. 点击"开始游戏" → 启动摄像头
2. 获取目标动作图片 → 显示在右侧
3. 玩家模仿动作 → 点击"确定/拍照提交"
4. 照片保存 → 自动调用评分接口
5. 显示评分结果 → 点击"下一个动作"继续

## 动作类型

当前支持的动作类型（可根据需要扩展）：

- `squat` - 深蹲
- `standing` - 站立
- `hands_up` - 举手
- `stride` - 跨步
- `jump` - 跳跃
- `sit` - 坐下

## 评分等级

- **高度匹配** (score >= 0.7): 动作非常标准，显示绿色
- **基本匹配** (0.4 <= score < 0.7): 动作基本完成，显示橙色
- **匹配度低** (score < 0.4): 动作需要改进，显示红色

## 文件结构

```
web/
├── app.py                    # 主应用，包含API端点
├── templates/
│   └── game.html             # 游戏页面，包含评分显示
└── ...

server/
├── action_api.py             # 动作识别API封装
├── action_matcher.py         # 动作匹配核心逻辑
├── pose_samples/             # 训练样本数据
│   ├── squat.csv
│   └── standing.csv
└── ...
```

## 注意事项

1. **依赖项**: 确保安装了所有必要的Python包（mediapipe, numpy, opencv-python等）

2. **训练数据**: 需要准备足够的训练样本（每个动作15-20张照片）放在 `server/pose_samples/` 目录

3. **路径配置**: 确保 `app.py` 中的路径配置正确，能够找到 `server` 目录

4. **错误处理**: 系统有完善的错误处理机制，包括：
   - API未初始化时的友好提示
   - 动作类型无效时的错误信息
   - 图片无法识别时的处理

5. **扩展性**: 可以轻松添加新的动作类型：
   - 在 `training_data/` 下创建新的动作文件夹
   - 放入训练照片
   - 运行数据准备脚本
   - 重启服务器即可自动识别新动作