"""
动作匹配器 - 支持多动作类型识别和相似度打分

功能:
1. 支持多种动作类型: squat(蹲下), hands_up(举手), stride(跨步)等
2. 输入一张照片和目标动作类型，输出与目标动作的相似度分数(0-1)

使用方法:
1. 准备训练数据文件夹结构:
   training_data/
   ├── squat/           # 蹲下照片
   ├── hands_up/        # 举手照片
   ├── stride/          # 跨步照片
   └── ...              # 其他动作类型

2. 运行 prepare_training_data.py 生成姿态样本

3. 使用动作匹配器:
   from action_matcher import ActionMatcher
   matcher = ActionMatcher(pose_samples_folder='./pose_samples')
   score = matcher.match(image_path='photo.jpg', target_action='squat')
"""
import os
import sys
import cv2
import numpy as np
import csv
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# 导入d.py中的姿态编码器和分类器
from d import FullBodyPoseEmbedder, PoseClassifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ActionMatcher:
    """
    动作匹配器

    支持多种动作类型，计算输入图像与目标动作的相似度
    """

    def __init__(
        self,
        pose_samples_folder: str = "./pose_samples",
        confidence_threshold: float = 0.5,
        top_n_by_max_distance: int = 30,
        top_n_by_mean_distance: int = 10
    ):
        """
        初始化动作匹配器

        Args:
            pose_samples_folder: 姿态样本CSV文件夹路径
            confidence_threshold: 分类置信度阈值
            top_n_by_max_distance: 最大距离过滤的样本数
            top_n_by_mean_distance: 平均距离过滤的样本数
        """
        self.confidence_threshold = confidence_threshold
        self.top_n_by_max_distance = top_n_by_max_distance
        self.top_n_by_mean_distance = top_n_by_mean_distance

        # 初始化姿态编码器
        logger.info("初始化姿态编码器...")
        self.pose_embedder = FullBodyPoseEmbedder(torso_size_multiplier=2.5)

        # 加载姿态样本
        self._load_samples(pose_samples_folder)

        # 初始化MediaPipe姿态检测器
        self._init_pose_detector()

        logger.info("动作匹配器初始化完成")

    def _load_samples(self, pose_samples_folder: str):
        """加载姿态样本文件"""
        self.pose_samples_folder = pose_samples_folder
        self.available_actions = []  # 可用的动作类型列表
        self.action_samples = {}  # 每个动作对应的样本列表

        if not os.path.exists(pose_samples_folder):
            logger.warning(f"样本文件夹不存在: {pose_samples_folder}")
            return

        # 遍历CSV文件
        for file_name in os.listdir(pose_samples_folder):
            if not file_name.endswith('.csv'):
                continue

            action_name = os.path.splitext(file_name)[0]
            self.available_actions.append(action_name)

            # 加载该动作的样本
            samples = self._load_action_samples(
                os.path.join(pose_samples_folder, file_name),
                action_name
            )
            self.action_samples[action_name] = samples
            logger.info(f"  - {action_name}: {len(samples)} 个样本")

        logger.info(f"可用动作类型: {self.available_actions}")

    def _load_action_samples(self, file_path: str, action_name: str) -> List[np.ndarray]:
        """加载单个动作类型的样本"""
        samples = []
        with open(file_path, 'r', newline='') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            for row in reader:
                if len(row) == 0:
                    continue
                landmarks = np.array(row, dtype=np.float32)
                landmarks = landmarks.reshape(33, 3)
                embedding = self.pose_embedder(landmarks)
                samples.append({
                    'landmarks': landmarks,
                    'embedding': embedding
                })
        return samples

    def _init_pose_detector(self):
        """初始化MediaPipe姿态检测器"""
        try:
            import mediapipe as mp
            self.mp_pose = mp.solutions.pose
            self.pose_detector = self.mp_pose.Pose(
                static_image_mode=True,
                model_complexity=2,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            self.has_mediapipe = True
        except ImportError:
            logger.warning("MediaPipe未安装，无法从图片提取姿态")
            self.has_mediapipe = False

    def extract_pose(self, image_path: str) -> Optional[np.ndarray]:
        """
        从图片提取姿态关键点

        Args:
            image_path: 图片路径

        Returns:
            landmarks: shape (33, 3) 的关键点数组，如果失败返回None
        """
        if not self.has_mediapipe:
            logger.error("MediaPipe未安装")
            return None

        image = cv2.imread(image_path)
        if image is None:
            logger.error(f"无法读取图片: {image_path}")
            return None

        # 转换为RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # 检测姿态
        results = self.pose_detector.process(image_rgb)

        if not results.pose_landmarks:
            logger.warning(f"未检测到人体姿态: {image_path}")
            return None

        # 提取33个关键点
        landmarks = []
        for lm in results.pose_landmarks.landmark:
            landmarks.append([lm.x, lm.y, lm.z])

        return np.array(landmarks, dtype=np.float32)

    def _compute_distance(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """计算两个嵌入向量之间的距离"""
        return np.mean(np.abs(embedding1 - embedding2))

    def _compute_similarity_score(
        self,
        query_embedding: np.ndarray,
        target_action: str
    ) -> float:
        """
        计算与目标动作的相似度分数

        使用KNN思想，找到最近的top_n个样本，根据平均距离计算相似度

        Returns:
            score: 0-1之间的相似度分数，1表示完全匹配
        """
        if target_action not in self.action_samples:
            logger.warning(f"未知的动作类型: {target_action}")
            return 0.0

        samples = self.action_samples[target_action]
        if len(samples) == 0:
            logger.warning(f"动作 {target_action} 没有训练样本")
            return 0.0

        # 准备翻转后的嵌入（数据增强）
        # 注意：这里无法直接翻转嵌入，因为我们只有嵌入没有原始landmarks
        # 所以我们只使用原始嵌入进行比较

        # 计算与所有样本的距离
        distances = []
        for sample in samples:
            dist = self._compute_distance(query_embedding, sample['embedding'])
            distances.append(dist)

        distances = np.array(distances)

        # 过滤掉异常值（保留距离最近的top_n_by_max_distance个）
        sorted_indices = np.argsort(distances)
        filtered_indices = sorted_indices[:self.top_n_by_max_distance]
        filtered_distances = distances[filtered_indices]

        # 从过滤后的样本中选择最近的top_n_by_mean_distance个
        n_nearest = min(self.top_n_by_mean_distance, len(filtered_distances))
        nearest_distances = filtered_distances[:n_nearest]

        # 计算平均距离
        mean_distance = np.mean(nearest_distances)

        # 将距离转换为相似度分数
        # 使用指数衰减: score = exp(-distance / scale)
        # scale参数控制衰减速率，可以根据数据调整
        scale = 5.0  # 距离为5时，相似度约为0.37
        similarity = np.exp(-mean_distance / scale)

        # 根据阈值调整分数
        # 如果平均距离超过某个值，分数会显著降低
        if mean_distance > 20:
            similarity *= 0.5
        if mean_distance > 30:
            similarity *= 0.5

        return float(np.clip(similarity, 0.0, 1.0))

    def match(
        self,
        image_path: str,
        target_action: str
    ) -> Dict:
        """
        匹配单张图片与目标动作

        Args:
            image_path: 图片路径
            target_action: 目标动作名称 (如 'squat', 'hands_up', 'stride')

        Returns:
            result: 包含以下字段的字典:
                - success: 是否成功
                - score: 相似度分数 (0-1)
                - target_action: 目标动作
                - landmarks_detected: 是否检测到姿态
                - error: 错误信息(如果有)
        """
        result = {
            'success': False,
            'score': 0.0,
            'target_action': target_action,
            'landmarks_detected': False,
            'error': None
        }

        # 检查目标动作是否有效
        if target_action not in self.available_actions:
            result['error'] = f"未知的动作类型: {target_action}"
            result['error'] += f"，可用动作: {self.available_actions}"
            return result

        # 提取姿态
        landmarks = self.extract_pose(image_path)
        if landmarks is None:
            result['error'] = "无法从图片提取姿态"
            return result

        result['landmarks_detected'] = True

        # 计算嵌入
        query_embedding = self.pose_embedder(landmarks)

        # 计算相似度分数
        score = self._compute_similarity_score(query_embedding, target_action)
        result['score'] = score
        result['success'] = True

        return result

    def match_landmarks(
        self,
        landmarks: np.ndarray,
        target_action: str
    ) -> Dict:
        """
        直接使用已提取的关键点进行匹配

        Args:
            landmarks: shape (33, 3) 的关键点数组
            target_action: 目标动作名称

        Returns:
            result: 匹配结果字典
        """
        result = {
            'success': False,
            'score': 0.0,
            'target_action': target_action,
            'landmarks_detected': True,
            'error': None
        }

        # 检查目标动作是否有效
        if target_action not in self.available_actions:
            result['error'] = f"未知的动作类型: {target_action}"
            return result

        # 计算嵌入
        query_embedding = self.pose_embedder(landmarks)

        # 计算相似度分数
        score = self._compute_similarity_score(query_embedding, target_action)
        result['score'] = score
        result['success'] = True

        return result

    def batch_match(
        self,
        image_paths: List[str],
        target_action: str
    ) -> List[Dict]:
        """
        批量匹配多张图片

        Args:
            image_paths: 图片路径列表
            target_action: 目标动作名称

        Returns:
            results: 匹配结果列表
        """
        results = []
        for image_path in image_paths:
            result = self.match(image_path, target_action)
            results.append(result)
        return results

    def get_available_actions(self) -> List[str]:
        """获取所有可用的动作类型"""
        return self.available_actions.copy()


def prepare_multi_action_data(
    training_data_folder: str,
    output_folder: str = "./pose_samples"
):
    """
    准备多动作类型的训练数据

    扫描training_data_folder下的所有子文件夹，每个子文件夹作为一个动作类型
    """
    from prepare_training_data import PoseExtractor, save_to_csv

    logger.info(f"准备多动作训练数据...")
    logger.info(f"输入文件夹: {training_data_folder}")
    logger.info(f"输出文件夹: {output_folder}")

    os.makedirs(output_folder, exist_ok=True)

    extractor = PoseExtractor()

    # 遍历所有子文件夹
    for action_name in sorted(os.listdir(training_data_folder)):
        action_dir = os.path.join(training_data_folder, action_name)

        # 跳过非文件夹项
        if not os.path.isdir(action_dir):
            continue

        logger.info(f"\n处理动作类型: {action_name}")

        # 提取该动作的所有图片
        landmarks_list = []
        image_files = [f for f in os.listdir(action_dir)
                      if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

        for img_file in sorted(image_files):
            img_path = os.path.join(action_dir, img_file)
            landmarks = extractor.extract_from_image(img_path)

            if landmarks is not None:
                landmarks_list.append(landmarks)
                logger.info(f"  ✓ {img_file}")
            else:
                logger.warning(f"  ✗ {img_file}")

        # 保存CSV
        if landmarks_list:
            output_path = os.path.join(output_folder, f"{action_name}.csv")
            save_to_csv(landmarks_list, output_path)
            logger.info(f"  保存 {len(landmarks_list)} 个样本到 {output_path}")
        else:
            logger.warning(f"  {action_name} 没有成功提取的样本")

    logger.info("\n处理完成!")


def main():
    """命令行接口"""
    import argparse

    parser = argparse.ArgumentParser(
        description='动作匹配器 - 计算图片与目标动作的相似度',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:

1. 准备多动作训练数据:
   python action_matcher.py --prepare --input_dir ./training_data --output_dir ./pose_samples
   文件夹结构示例:
   training_data/
   ├── squat/           # 15张蹲下照片
   ├── hands_up/        # 15张举手照片
   ├── stride/          # 15张跨步照片
   └── stand/           # 15张站立照片

2. 单张图片匹配:
   python action_matcher.py --samples ./pose_samples --image photo.jpg --action squat

3. 批量匹配:
   python action_matcher.py --samples ./pose_samples --image_dir ./test_photos --action hands_up
        """
    )

    # 数据准备参数
    parser.add_argument('--prepare', action='store_true',
                       help='准备训练数据模式')
    parser.add_argument('--input_dir', type=str, default='./training_data',
                       help='输入训练数据文件夹路径')
    parser.add_argument('--output_dir', type=str, default='./pose_samples',
                       help='输出样本文件夹路径')

    # 匹配参数
    parser.add_argument('--samples', type=str, default='./pose_samples',
                       help='姿态样本文件夹路径')
    parser.add_argument('--image', type=str, default=None,
                       help='要匹配的图片路径')
    parser.add_argument('--image_dir', type=str, default=None,
                       help='要匹配的测试图片文件夹')
    parser.add_argument('--action', type=str, default=None,
                       help='目标动作名称 (squat, hands_up, stride等)')
    parser.add_argument('--threshold', type=float, default=0.5,
                       help='相似度阈值 (默认: 0.5)')

    args = parser.parse_args()

    if args.prepare:
        # 准备训练数据
        if not os.path.exists(args.input_dir):
            logger.error(f"输入文件夹不存在: {args.input_dir}")
            sys.exit(1)
        prepare_multi_action_data(args.input_dir, args.output_dir)

    elif args.image and args.action:
        # 单张图片匹配
        matcher = ActionMatcher(
            pose_samples_folder=args.samples,
            confidence_threshold=args.threshold
        )

        result = matcher.match(args.image, args.action)

        print("\n" + "="*50)
        print("匹配结果")
        print("="*50)
        print(f"图片: {args.image}")
        print(f"目标动作: {args.action}")
        print(f"成功: {result['success']}")
        print(f"姿态检测: {result['landmarks_detected']}")
        if result['success']:
            print(f"相似度分数: {result['score']:.4f}")
            print(f"匹配程度: {'高' if result['score'] > 0.7 else '中' if result['score'] > 0.4 else '低'}")
        if result['error']:
            print(f"错误: {result['error']}")
        print("="*50)

    elif args.image_dir and args.action:
        # 批量匹配
        matcher = ActionMatcher(
            pose_samples_folder=args.samples,
            confidence_threshold=args.threshold
        )

        image_files = [f for f in os.listdir(args.image_dir)
                      if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        image_paths = [os.path.join(args.image_dir, f) for f in image_files]

        print(f"\n批量匹配: {len(image_paths)} 张图片")
        print(f"目标动作: {args.action}")
        print("="*60)

        results = matcher.batch_match(image_paths, args.action)

        scores = []
        for img_file, result in zip(image_files, results):
            if result['success']:
                scores.append(result['score'])
                status = "✓" if result['score'] > args.threshold else "✗"
                print(f"{status} {img_file:20s} 分数: {result['score']:.4f}")
            else:
                print(f"✗ {img_file:20s} 错误: {result['error']}")

        if scores:
            print("\n" + "="*60)
            print(f"平均分: {np.mean(scores):.4f}")
            print(f"最高分: {np.max(scores):.4f}")
            print(f"最低分: {np.min(scores):.4f}")
            print(f"超过阈值: {sum(1 for s in scores if s > args.threshold)}/{len(scores)}")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
