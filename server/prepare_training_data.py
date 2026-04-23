"""
训练数据准备脚本
从深蹲照片提取姿态关键点并保存为CSV训练文件

使用方法:
1. 准备照片文件夹结构:
   training_data/
   ├── standing/          # 站立状态照片
   │   ├── stand_01.jpg
   │   ├── stand_02.jpg
   │   └── ...
   └── squat/             # 蹲下状态照片
       ├── squat_01.jpg
       ├── squat_02.jpg
       └── ...

2. 运行脚本:
   python prepare_training_data.py --input_dir training_data --output_dir pose_samples

3. 生成的CSV文件将保存在 pose_samples/ 目录:
   pose_samples/
   ├── standing.csv
   └── squat.csv
"""
import os
import cv2
import numpy as np
import mediapipe as mp
import csv
import argparse
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PoseExtractor:
    """姿态关键点提取器"""

    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=True,
            model_complexity=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.num_landmarks = 33
        self.num_dimensions = 3

    def extract_from_image(self, image_path: str) -> np.ndarray:
        """
        从图片提取33个关键点

        Returns:
            landmarks: shape (33, 3) 的数组，包含 x, y, z 坐标
        """
        image = cv2.imread(image_path)
        if image is None:
            logger.error(f"无法读取图片: {image_path}")
            return None

        # 转换为RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # 检测姿态
        results = self.pose.process(image_rgb)

        if not results.pose_landmarks:
            logger.warning(f"未检测到人体姿态: {image_path}")
            return None

        # 提取33个关键点
        landmarks = []
        for lm in results.pose_landmarks.landmark:
            landmarks.append([lm.x, lm.y, lm.z])

        return np.array(landmarks, dtype=np.float32)

    def extract_from_video(self, video_path: str, sample_interval: int = 5) -> list:
        """
        从视频中提取姿态样本

        Args:
            video_path: 视频文件路径
            sample_interval: 采样间隔（每N帧提取一帧）

        Returns:
            姿态列表，每个元素是 (frame_idx, landmarks)
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"无法打开视频: {video_path}")
            return []

        samples = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 按间隔采样
            if frame_idx % sample_interval == 0:
                # 临时保存帧并提取姿态
                temp_path = f"/tmp/temp_frame_{frame_idx}.jpg"
                cv2.imwrite(temp_path, frame)
                landmarks = self.extract_from_image(temp_path)

                if os.path.exists(temp_path):
                    os.remove(temp_path)

                if landmarks is not None:
                    samples.append((frame_idx, landmarks))

            frame_idx += 1

        cap.release()
        logger.info(f"从视频提取了 {len(samples)} 个姿态样本")
        return samples


def save_to_csv(landmarks_list: list, output_path: str):
    """
    将姿态关键点保存为CSV文件

    CSV格式: 每行代表一个样本，33*3=99个数值
    x1,y1,z1,x2,y2,z2,...,x33,y33,z33
    """
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        for landmarks in landmarks_list:
            # 展平为1D数组
            row = landmarks.flatten().tolist()
            writer.writerow(row)

    logger.info(f"保存了 {len(landmarks_list)} 个样本到 {output_path}")


def process_training_folder(input_dir: str, output_dir: str):
    """
    处理训练数据文件夹

    期望的输入结构:
    input_dir/
    ├── standing/
    │   ├── img1.jpg
    │   └── img2.jpg
    └── squat/
        ├── img1.jpg
        └── img2.jpg

    生成的输出:
    output_dir/
    ├── standing.csv
    └── squat.csv
    """
    extractor = PoseExtractor()

    os.makedirs(output_dir, exist_ok=True)

    # 处理每个类别文件夹
    for class_name in ['standing', 'squat']:
        class_dir = os.path.join(input_dir, class_name)

        if not os.path.exists(class_dir):
            logger.warning(f"类别文件夹不存在: {class_dir}")
            continue

        # 提取所有图片的姿态
        landmarks_list = []
        image_files = [f for f in os.listdir(class_dir)
                      if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

        for img_file in sorted(image_files):
            img_path = os.path.join(class_dir, img_file)
            landmarks = extractor.extract_from_image(img_path)

            if landmarks is not None:
                landmarks_list.append(landmarks)
                logger.info(f"✓ 提取成功: {img_file}")
            else:
                logger.warning(f"✗ 提取失败: {img_file}")

        # 保存为CSV
        if landmarks_list:
            output_path = os.path.join(output_dir, f"{class_name}.csv")
            save_to_csv(landmarks_list, output_path)
        else:
            logger.error(f"类别 {class_name} 没有成功提取的样本")


def main():
    parser = argparse.ArgumentParser(
        description='从深蹲照片准备训练数据',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 从照片文件夹生成训练数据
  python prepare_training_data.py --input_dir ./training_data --output_dir ./pose_samples

  # 从单个视频提取样本
  python prepare_training_data.py --video ./squat_video.mp4 --output_dir ./pose_samples --class_name squat

期望的输入文件夹结构:
  training_data/
  ├── standing/          # 站立状态照片
  │   ├── stand_01.jpg
  │   └── ...
  └── squat/             # 蹲下状态照片
      ├── squat_01.jpg
      └── ...
        """
    )
    parser.add_argument('--input_dir', type=str, default='./training_data',
                       help='输入照片文件夹路径 (默认: ./training_data)')
    parser.add_argument('--output_dir', type=str, default='./pose_samples',
                       help='输出CSV文件夹路径 (默认: ./pose_samples)')
    parser.add_argument('--video', type=str, default=None,
                       help='从视频提取样本 (可选)')
    parser.add_argument('--class_name', type=str, default='squat',
                       help='视频样本的类别名称 (默认: squat)')

    args = parser.parse_args()

    # 如果从视频提取
    if args.video:
        if not os.path.exists(args.video):
            logger.error(f"视频文件不存在: {args.video}")
            return

        os.makedirs(args.output_dir, exist_ok=True)
        extractor = PoseExtractor()
        samples = extractor.extract_from_video(args.video)

        if samples:
            landmarks_list = [landmarks for _, landmarks in samples]
            output_path = os.path.join(args.output_dir, f"{args.class_name}.csv")
            save_to_csv(landmarks_list, output_path)
            logger.info(f"从视频提取了 {len(samples)} 个样本")
        else:
            logger.error("未能从视频提取到任何样本")

    else:
        # 从照片文件夹处理
        if not os.path.exists(args.input_dir):
            logger.error(f"输入文件夹不存在: {args.input_dir}")
            logger.info("请创建文件夹结构:")
            logger.info(f"  {args.input_dir}/standing/")
            logger.info(f"  {args.input_dir}/squat/")
            return

        process_training_folder(args.input_dir, args.output_dir)
        logger.info("\n处理完成！")
        logger.info(f"生成的训练文件保存在: {args.output_dir}")


if __name__ == '__main__':
    main()
