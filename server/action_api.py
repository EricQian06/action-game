"""
动作识别API接口

提供简洁的API用于动作相似度匹配

使用示例:
    from action_api import ActionRecognitionAPI

    # 初始化API (只需初始化一次)
    api = ActionRecognitionAPI()

    # 匹配单张图片
    result = api.recognize(image_path='photo.jpg', target_action='squat')
    # result: {'success': True, 'score': 0.85, 'target_action': 'squat', ...}

    # 获取可用的动作类型
    actions = api.get_available_actions()
    # ['squat', 'hands_up', 'stride', 'stand', ...]
"""
import os
import sys
from typing import Dict, List, Optional
from pathlib import Path

# 确保可以导入当前目录的模块
CURRENT_DIR = Path(__file__).parent
sys.path.insert(0, str(CURRENT_DIR))

from action_matcher import ActionMatcher


class ActionRecognitionAPI:
    """
    动作识别API类

    提供简洁的接口用于动作相似度匹配
    """

    def __init__(self, pose_samples_folder: str = None):
        """
        初始化动作识别API

        Args:
            pose_samples_folder: 姿态样本文件夹路径
                默认为当前目录下的 'pose_samples' 文件夹
        """
        if pose_samples_folder is None:
            # 默认使用当前文件所在目录下的 pose_samples
            pose_samples_folder = str(CURRENT_DIR / 'pose_samples')

        self.matcher = ActionMatcher(pose_samples_folder=pose_samples_folder)
        self.available_actions = self.matcher.get_available_actions()

    def recognize(self, image_path: str, target_action: str) -> Dict:
        """
        识别图片与目标动作的相似度

        Args:
            image_path: 图片文件路径
            target_action: 目标动作名称，如 'squat', 'hands_up', 'stride'

        Returns:
            Dict: 包含以下字段:
                - success (bool): 是否成功识别
                - score (float): 相似度分数，范围0-1，越接近1表示越匹配
                - target_action (str): 目标动作名称
                - landmarks_detected (bool): 是否检测到人体姿态
                - error (str): 错误信息（如果有）

        示例:
            >>> api = ActionRecognitionAPI()
            >>> result = api.recognize('photo.jpg', 'squat')
            >>> print(f"相似度: {result['score']:.2%}")
            相似度: 85.23%
        """
        return self.matcher.match(image_path, target_action)

    def get_available_actions(self) -> List[str]:
        """
        获取所有可用的动作类型

        Returns:
            List[str]: 动作类型名称列表

        示例:
            >>> api = ActionRecognitionAPI()
            >>> actions = api.get_available_actions()
            >>> print(actions)
            ['squat', 'hands_up', 'stride', 'stand']
        """
        return self.matcher.get_available_actions()

    def get_score(self, image_path: str, target_action: str) -> Optional[float]:
        """
        获取相似度分数（简化接口）

        Args:
            image_path: 图片文件路径
            target_action: 目标动作名称

        Returns:
            float: 相似度分数（0-1），失败返回 None

        示例:
            >>> api = ActionRecognitionAPI()
            >>> score = api.get_score('photo.jpg', 'squat')
            >>> if score and score > 0.7:
            ...     print("动作匹配成功！")
        """
        result = self.matcher.match(image_path, target_action)
        return result['score'] if result['success'] else None


def quick_test():
    """快速测试示例"""
    print("=" * 60)
    print("动作识别API - 快速测试")
    print("=" * 60)

    # 初始化API
    api = ActionRecognitionAPI()

    # 查看可用动作
    actions = api.get_available_actions()
    print(f"\n可用动作类型: {actions}")

    if not actions:
        print("\n错误: 没有找到任何动作样本")
        print("请先准备训练数据（见 prepare_training_data.py）")
        return

    # 检查测试图片是否存在
    test_image = None
    test_dirs = ['training_data/squat', 'training_data/hands_up', 'training_data/stride']
    for d in test_dirs:
        if os.path.exists(d):
            images = [f for f in os.listdir(d) if f.lower().endswith(('.jpg', '.png'))]
            if images:
                test_image = os.path.join(d, images[0])
                break

    if test_image is None:
        print("\n提示: 没有找到测试图片")
        print("请将图片放入 training_data/<动作类型>/ 文件夹")
        return

    # 测试每种动作
    print(f"\n测试图片: {test_image}")
    print("-" * 40)

    for action in actions:
        result = api.recognize(test_image, action)
        score = result['score'] if result['success'] else 0.0
        bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
        print(f"{action:15s} [{bar}] {score:.2%}")

    print("-" * 40)


def simple_example():
    """简单使用示例"""
    print("\n" + "=" * 60)
    print("简单使用示例")
    print("=" * 60)
    code = '''
from action_api import ActionRecognitionAPI

# 1. 初始化API (只初始化一次)
api = ActionRecognitionAPI()

# 2. 识别图片与目标动作的相似度
result = api.recognize(
    image_path='path/to/photo.jpg',
    target_action='squat'  # 或其他动作: 'hands_up', 'stride'
)

# 3. 获取相似度分数 (0-1之间)
if result['success']:
    score = result['score']
    print(f"相似度: {score:.2%}")

    # 4. 判断是否匹配
    if score > 0.7:
        print("动作匹配成功！")
    else:
        print("动作不匹配")
else:
    print(f"识别失败: {result['error']}")
'''
    print(code)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='动作识别API测试')
    parser.add_argument('--test', action='store_true', help='运行快速测试')
    parser.add_argument('--example', action='store_true', help='显示使用示例')

    args = parser.parse_args()

    if args.test:
        quick_test()
    elif args.example:
        simple_example()
    else:
        quick_test()
        simple_example()
