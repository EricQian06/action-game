# 动作识别使用指南

## 功能说明

实现了一个多动作类型识别系统，可以：
1. 支持多种动作类型：蹲下(squat)、举手(hands_up)、跨步(stride)等
2. 输入一张照片和目标动作，输出相似度分数（0-1之间）
3. 分数越接近1，表示与目标动作越匹配

## 快速开始

### 1. 准备训练数据

首先需要有训练数据，按照以下文件夹结构组织：

```
training_data/
├── squat/              # 蹲下动作照片
│   ├── squat_01.jpg
│   ├── squat_02.jpg
│   └── ... (15张)
├── hands_up/           # 举手动作照片
│   ├── hands_up_01.jpg
│   └── ... (15张)
├── stride/             # 跨步动作照片
│   ├── stride_01.jpg
│   └── ... (15张)
└── stand/              # 站立照片（可选）
    └── ...
```

### 2. 生成姿态样本文件

运行脚本将照片转换为姿态样本：

```bash
cd server
python3 action_matcher.py --prepare --input_dir ./training_data --output_dir ./pose_samples
```

这将生成 `pose_samples/` 文件夹，包含各动作的CSV文件：
- `squat.csv`
- `hands_up.csv`
- `stride.csv`

### 3. 使用API进行识别

```python
from action_api import ActionRecognitionAPI

# 初始化API
api = ActionRecognitionAPI()

# 识别图片与目标动作的相似度
result = api.recognize(
    image_path='path/to/test_photo.jpg',
    target_action='squat'  # 或其他动作: 'hands_up', 'stride'
)

# 获取相似度分数 (0-1)
if result['success']:
    score = result['score']
    print(f"相似度: {score:.2%}")

    if score > 0.7:
        print("动作匹配度高！")
    elif score > 0.4:
        print("动作匹配度中等")
    else:
        print("动作不匹配")
else:
    print(f"识别失败: {result['error']}")
```

## 命令行使用

### 单张图片匹配

```bash
python3 action_matcher.py --samples ./pose_samples --image photo.jpg --action squat
```

输出示例：
```
==================================================
匹配结果
==================================================
图片: photo.jpg
目标动作: squat
成功: True
姿态检测: True
相似度分数: 0.8532
匹配程度: 高
==================================================
```

### 批量图片匹配

```bash
python action_matcher.py --samples ./pose_samples --image_dir ./test_photos --action hands_up
```

### 准备训练数据

```bash
python action_matcher.py --prepare --input_dir ./training_data --output_dir ./pose_samples
```

## API详细说明

### ActionRecognitionAPI 类

#### 初始化

```python
api = ActionRecognitionAPI(pose_samples_folder='./pose_samples')
```

- `pose_samples_folder`: 姿态样本文件夹路径，默认为'./pose_samples'

#### recognize 方法

```python
result = api.recognize(image_path='photo.jpg', target_action='squat')
```

参数：
- `image_path`: 图片文件路径
- `target_action`: 目标动作名称（如 'squat', 'hands_up', 'stride'）

返回值（Dict）：
- `success` (bool): 是否成功
- `score` (float): 相似度分数，0-1之间
- `target_action` (str): 目标动作名称
- `landmarks_detected` (bool): 是否检测到人体姿态
- `error` (str): 错误信息（如果有）

#### get_available_actions 方法

```python
actions = api.get_available_actions()
# 返回: ['squat', 'hands_up', 'stride', ...]
```

#### get_score 方法（简化接口）

```python
score = api.get_score('photo.jpg', 'squat')
# 返回: 0.85 或 None（失败时）
```

## 相似度分数说明

- **0.8-1.0**: 高度匹配，动作完成得很好
- **0.6-0.8**: 较匹配，动作基本完成但可能有些偏差
- **0.4-0.6**: 中等匹配，动作有些相似但不完全
- **0.2-0.4**: 低匹配，动作差异较大
- **0.0-0.2**: 几乎不匹配

## 添加新的动作类型

1. 在 `training_data/` 下创建新的文件夹，如 `jump/`
2. 放入15-20张该动作的照片
3. 运行数据准备脚本：
   ```bash
   python action_matcher.py --prepare
   ```
4. 新动作类型会自动添加到 `pose_samples/jump.csv`

## 完整示例代码

```python
# 示例：游戏动作检测
from action_api import ActionRecognitionAPI
import time

def game_action_detection():
    api = ActionRecognitionAPI()

    # 游戏指令队列
    commands = ['squat', 'hands_up', 'squat', 'stride']
    current_idx = 0

    while current_idx < len(commands):
        current_action = commands[current_idx]
        print(f"\n请执行动作: {current_action}")

        # 模拟从摄像头获取图片
        # photo = capture_from_camera()
        # cv2.imwrite('current_frame.jpg', photo)

        # 识别当前动作
        result = api.recognize('current_frame.jpg', current_action)

        if result['success']:
            score = result['score']
            print(f"动作相似度: {score:.2%}")

            if score > 0.7:
                print("✓ 动作正确！")
                current_idx += 1
            else:
                print("✗ 动作不匹配，请再试一次")
        else:
            print(f"检测失败: {result['error']}")

        time.sleep(1)

    print("\n恭喜！所有动作完成！")

if __name__ == '__main__':
    game_action_detection()
```

## 注意事项

1. 训练照片质量要好，背景不要太杂乱
2. 每个动作至少10-15张训练照片
3. 照片中人物要完整，不要太远或太近
4. 动作要标准且一致
5. 测试时拍照角度最好与训练照片类似
