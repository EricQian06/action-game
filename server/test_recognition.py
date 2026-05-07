"""
动作识别模块测试脚本

功能：
1. 测试 training_data 中各动作照片与所有动作类型的匹配相似度
2. 测试 server/input.jpg 与所有动作类型的匹配相似度
"""
import os
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).parent
os.chdir(CURRENT_DIR)
sys.path.insert(0, str(CURRENT_DIR))

from action_api import ActionRecognitionAPI
import numpy as np

def print_table_header(actions):
    """打印表头"""
    print(f"{'图片':<30}", end="")
    for action in actions:
        print(f"{action:>12}", end="")
    print()
    print("-" * (30 + 12 * len(actions)))

def print_table_row(image_name, scores, actions):
    """打印一行结果"""
    print(f"{image_name:<30}", end="")
    for action in actions:
        score = scores.get(action, 0.0)
        print(f"{score:>11.2%}", end="")
    print()

def test_training_data(api, actions, max_images_per_folder=5):
    """测试 training_data 中各动作照片与所有动作的匹配相似度"""
    training_dir = CURRENT_DIR / "training_data"
    if not training_dir.exists():
        print(f"[错误] training_data 目录不存在: {training_dir}")
        return

    for action_folder in sorted(training_dir.iterdir()):
        if not action_folder.is_dir():
            continue

        action_name = action_folder.name
        image_files = sorted([f for f in action_folder.iterdir()
                              if f.suffix.lower() in ('.jpg', '.jpeg', '.png')])

        if not image_files:
            continue

        print(f"\n{'='*80}")
        print(f"动作类别: {action_name} (共 {len(image_files)} 张，测试前 {min(max_images_per_folder, len(image_files))} 张)")
        print(f"{'='*80}")
        print_table_header(actions)

        for img_path in image_files[:max_images_per_folder]:
            scores = {}
            for target_action in actions:
                result = api.recognize(str(img_path), target_action)
                scores[target_action] = result['score'] if result['success'] else 0.0
            print_table_row(img_path.name, scores, actions)

def test_input_jpg(api, actions):
    """测试 server/input.jpg 与所有动作的匹配相似度"""
    input_path = CURRENT_DIR / "input.jpg"
    if not input_path.exists():
        print(f"\n[错误] input.jpg 不存在: {input_path}")
        return

    print(f"\n{'='*80}")
    print(f"测试图片: server/input.jpg")
    print(f"{'='*80}")
    print(f"{'目标动作':<20} {'相似度':>10} {'匹配等级':>10}")
    print("-" * 50)

    scores = []
    for target_action in actions:
        result = api.recognize(str(input_path), target_action)
        score = result['score'] if result['success'] else 0.0
        scores.append((target_action, score))

        if score >= 0.7:
            level = "高度匹配"
        elif score >= 0.4:
            level = "基本匹配"
        else:
            level = "匹配度低"

        print(f"{target_action:<20} {score:>9.2%} {level:>10}")

    # 找出最匹配的动作
    best_action, best_score = max(scores, key=lambda x: x[1])
    print("-" * 50)
    print(f"最匹配动作: {best_action} (相似度: {best_score:.2%})")

def main():
    print("="*80)
    print("动作识别模块测试")
    print("="*80)

    # 初始化 API
    print("\n正在初始化动作识别 API...")
    api = ActionRecognitionAPI(pose_samples_folder=str(CURRENT_DIR / "pose_samples"))
    actions = api.get_available_actions()

    if not actions:
        print("[错误] 没有找到任何动作样本，请检查 pose_samples 目录")
        sys.exit(1)

    print(f"可用动作类型: {actions}")

    # 测试1: training_data 中的照片
    test_training_data(api, actions, max_images_per_folder=5)

    # 测试2: server/input.jpg
    test_input_jpg(api, actions)

    print(f"\n{'='*80}")
    print("测试完成")
    print("="*80)

if __name__ == '__main__':
    main()
