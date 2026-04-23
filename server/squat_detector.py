"""
深蹲检测器主程序
整合姿态分类器和计数器，提供完整的深蹲检测和计数功能

使用示例:
1. 实时摄像头检测:
   python squat_detector.py --mode realtime --camera 0

2. 处理视频文件:
   python squat_detector.py --mode video --video_path ./squat_video.mp4 --output ./output.mp4

3. 处理图片:
   python squat_detector.py --mode image --image_path ./photo.jpg
"""
import os
import sys
import cv2
import numpy as np
import argparse
import time
import json
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 导入d.py中的类
from d import FullBodyPoseEmbedder, PoseClassifier
from squat_counter import SquatCounter


class SquatDetector:
    """
    深蹲检测器

    整合姿态分类和深蹲计数，提供实时检测能力
    """

    def __init__(
        self,
        pose_samples_folder: str = "./pose_samples",
        confidence_threshold: float = 0.6,
        display_size: Tuple[int, int] = (640, 480)
    ):
        """
        初始化检测器

        Args:
            pose_samples_folder: 姿态样本CSV文件夹路径
            confidence_threshold: 分类置信度阈值
            display_size: 显示画面尺寸
        """
        self.display_size = display_size

        # 初始化姿态编码器
        logger.info("初始化姿态编码器...")
        self.pose_embedder = FullBodyPoseEmbedder(torso_size_multiplier=2.5)

        # 初始化分类器
        logger.info(f"加载姿态样本从: {pose_samples_folder}")
        if not os.path.exists(pose_samples_folder):
            logger.warning(f"样本文件夹不存在: {pose_samples_folder}")
            logger.warning("请先运行 prepare_training_data.py 准备训练数据")
            self.classifier = None
        else:
            self.classifier = PoseClassifier(
                pose_samples_folder=pose_samples_folder,
                pose_embedder=self.pose_embedder,
                top_n_by_max_distance=30,
                top_n_by_mean_distance=10
            )
            logger.info("分类器加载完成")

        # 初始化深蹲计数器
        self.squat_counter = SquatCounter(
            confidence_threshold=confidence_threshold,
            state_history_size=5,
            min_squat_frames=3,
            angle_threshold=110.0
        )

        # 初始化MediaPipe姿态检测（用于从图像提取关键点）
        logger.info("初始化MediaPipe...")
        self.mp_pose = __import__('mediapipe').solutions.pose
        self.mp_drawing = __import__('mediapipe').solutions.drawing_utils
        self.pose_detector = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        # 统计数据
        self.frame_count = 0
        self.start_time = time.time()

        logger.info("深蹲检测器初始化完成")

    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict]:
        """
        处理单帧图像

        Args:
            frame: 输入图像 (BGR格式)

        Returns:
            annotated_frame: 标注后的图像
            results: 包含检测结果的字典
        """
        self.frame_count += 1
        results = {
            'success': False,
            'classification': None,
            'squat_count': self.squat_counter.squat_count,
            'state': 'unknown',
            'fps': 0
        }

        # 调整图像大小
        frame = cv2.resize(frame, self.display_size)

        # 转换为RGB用于MediaPipe
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # 检测姿态
        pose_results = self.pose_detector.process(frame_rgb)

        if not pose_results.pose_landmarks:
            # 未检测到人体
            cv2.putText(frame, "No person detected", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            return frame, results

        # 提取33个关键点
        landmarks = []
        for lm in pose_results.pose_landmarks.landmark:
            landmarks.append([lm.x, lm.y, lm.z])
        landmarks = np.array(landmarks, dtype=np.float32)

        # 计算膝盖角度（用于辅助判断）
        knee_angles = self._calculate_knee_angles(landmarks)

        # 使用分类器分类（如果有的话）
        classification_result = None
        if self.classifier is not None:
            try:
                classification_result = self.classifier(landmarks)
                results['classification'] = classification_result
            except Exception as e:
                logger.error(f"分类失败: {e}")

        # 更新深蹲计数器
        counter_result = self.squat_counter.update(
            classification_result or {},
            knee_angles=knee_angles,
            timestamp=time.time()
        )

        # 检查是否完成深蹲
        if counter_result.get('squat_completed'):
            self.squat_counter.increment_count(time.time())
            results['squat_completed'] = True

        # 更新结果
        results['success'] = True
        results['squat_count'] = self.squat_counter.squat_count
        results['state'] = counter_result.get('state', 'unknown')
        results['knee_angles'] = knee_angles
        results['fps'] = self.frame_count / (time.time() - self.start_time + 1e-6)

        # 在图像上绘制标注
        annotated_frame = self._draw_annotations(
            frame,
            pose_results,
            results,
            counter_result
        )

        return annotated_frame, results

    def _calculate_knee_angles(self, landmarks: np.ndarray) -> Tuple[float, float]:
        """计算左右膝盖角度"""
        try:
            # 关键点索引 (MediaPipe)
            LEFT_HIP, LEFT_KNEE, LEFT_ANKLE = 23, 25, 27
            RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE = 24, 26, 28

            def calc_angle(p1, p2, p3):
                """计算三点形成的角度"""
                v1 = p1 - p2
                v2 = p3 - p2
                cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
                cos_angle = np.clip(cos_angle, -1, 1)
                return np.degrees(np.arccos(cos_angle))

            left_angle = calc_angle(
                landmarks[LEFT_HIP],
                landmarks[LEFT_KNEE],
                landmarks[LEFT_ANKLE]
            )
            right_angle = calc_angle(
                landmarks[RIGHT_HIP],
                landmarks[RIGHT_KNEE],
                landmarks[RIGHT_ANKLE]
            )

            return left_angle, right_angle

        except Exception as e:
            logger.error(f"计算膝盖角度失败: {e}")
            return 180.0, 180.0

    def _draw_annotations(
        self,
        frame: np.ndarray,
        pose_results,
        results: Dict,
        counter_result: Dict
    ) -> np.ndarray:
        """在图像上绘制标注信息"""
        # 绘制姿态关键点
        self.mp_drawing.draw_landmarks(
            frame,
            pose_results.pose_landmarks,
            self.mp_pose.POSE_CONNECTIONS,
            landmark_drawing_spec=self.mp_drawing.DrawingSpec(
                color=(0, 255, 0), thickness=2, circle_radius=3
            ),
            connection_drawing_spec=self.mp_drawing.DrawingSpec(
                color=(255, 0, 0), thickness=2
            )
        )

        # 绘制计数信息
        squat_count = results.get('squat_count', 0)
        state = results.get('state', 'unknown')
        fps = results.get('fps', 0)

        # 左上角信息面板
        info_lines = [
            f"Squat Count: {squat_count}",
            f"State: {state.upper()}",
            f"FPS: {fps:.1f}"
        ]

        # 添加膝盖角度信息
        knee_angles = results.get('knee_angles')
        if knee_angles:
            left_angle, right_angle = knee_angles
            info_lines.append(f"Knee Angles: L={left_angle:.1f} R={right_angle:.1f}")

        # 添加分类结果
        classification = results.get('classification')
        if classification:
            # 格式化分类结果
            class_str = ", ".join([f"{k}:{v}" for k, v in list(classification.items())[:3]])
            info_lines.append(f"Votes: {class_str}")

        # 绘制信息文本
        y_offset = 30
        for i, line in enumerate(info_lines):
            y = y_offset + i * 25
            # 绘制半透明背景
            overlay = frame.copy()
            cv2.rectangle(overlay, (5, y-20), (400, y+5), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
            # 绘制文字
            cv2.putText(frame, line, (10, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # 如果刚刚完成深蹲，显示提示
        if results.get('squat_completed'):
            # 在画面中央显示大文字
            text = "SQUAT COMPLETED!"
            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 2, 4)[0]
            text_x = (frame.shape[1] - text_size[0]) // 2
            text_y = (frame.shape[0] + text_size[1]) // 2

            # 绘制背景
            cv2.rectangle(frame,
                         (text_x - 20, text_y - text_size[1] - 20),
                         (text_x + text_size[0] + 20, text_y + 20),
                         (0, 255, 0), -1)
            # 绘制文字
            cv2.putText(frame, text, (text_x, text_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 4)

        return frame


def process_video(detector: SquatDetector, video_path: str, output_path: str = None):
    """处理视频文件"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"无法打开视频: {video_path}")
        return

    # 获取视频信息
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    logger.info(f"视频信息: {width}x{height} @ {fps}fps, 共{total_frames}帧")

    # 创建视频写入器（如果需要保存）
    writer = None
    if output_path:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(output_path, fourcc, fps, detector.display_size)

    frame_count = 0
    start_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 处理帧
        annotated_frame, results = detector.process_frame(frame)

        # 保存视频
        if writer:
            writer.write(annotated_frame)

        # 显示
        cv2.imshow('Squat Detection', annotated_frame)

        frame_count += 1

        # 打印进度
        if frame_count % 30 == 0:
            elapsed = time.time() - start_time
            fps_actual = frame_count / elapsed
            progress = frame_count / total_frames * 100 if total_frames > 0 else 0
            logger.info(f"进度: {progress:.1f}% ({frame_count}/{total_frames}), "
                       f"处理速度: {fps_actual:.1f}fps, 深蹲次数: {results['squat_count']}")

        # 按'q'退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # 清理
    cap.release()
    if writer:
        writer.release()
    cv2.destroyAllWindows()

    elapsed = time.time() - start_time
    logger.info(f"\n处理完成!")
    logger.info(f"总帧数: {frame_count}")
    logger.info(f"总时间: {elapsed:.1f}秒")
    logger.info(f"平均FPS: {frame_count/elapsed:.1f}")
    logger.info(f"最终深蹲次数: {detector.squat_counter.squat_count}")


def process_image(detector: SquatDetector, image_path: str, output_path: str = None):
    """处理单张图片"""
    frame = cv2.imread(image_path)
    if frame is None:
        logger.error(f"无法读取图片: {image_path}")
        return

    annotated_frame, results = detector.process_frame(frame)

    # 显示结果
    cv2.imshow('Squat Detection', annotated_frame)
    print(f"\n检测结果:")
    print(f"  状态: {results['state']}")
    print(f"  深蹲次数: {results['squat_count']}")
    print(f"  分类结果: {results.get('classification', 'N/A')}")

    # 保存
    if output_path:
        cv2.imwrite(output_path, annotated_frame)
        print(f"结果已保存: {output_path}")

    cv2.waitKey(0)
    cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(
        description='深蹲检测和计数器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:

1. 实时摄像头检测:
   python squat_detector.py --mode realtime --camera 0

2. 处理视频文件:
   python squat_detector.py --mode video --video_path ./squat_video.mp4 --output ./output.mp4

3. 处理单张图片:
   python squat_detector.py --mode image --image_path ./photo.jpg --output ./result.jpg

4. 指定训练样本文件夹:
   python squat_detector.py --mode realtime --samples ./my_pose_samples

准备工作:
1. 先运行 prepare_training_data.py 准备训练数据
2. 确保 pose_samples/ 文件夹包含 standing.csv 和 squat.csv
        """
    )

    parser.add_argument('--mode', type=str, required=True,
                       choices=['realtime', 'video', 'image'],
                       help='运行模式: realtime=实时摄像头, video=视频文件, image=单张图片')

    parser.add_argument('--samples', type=str, default='./pose_samples',
                       help='姿态样本文件夹路径 (默认: ./pose_samples)')

    parser.add_argument('--camera', type=int, default=0,
                       help='摄像头索引 (默认: 0)')

    parser.add_argument('--video_path', type=str, default=None,
                       help='输入视频文件路径 (video模式必填)')

    parser.add_argument('--image_path', type=str, default=None,
                       help='输入图片路径 (image模式必填)')

    parser.add_argument('--output', type=str, default=None,
                       help='输出文件路径 (可选)')

    parser.add_argument('--confidence', type=float, default=0.6,
                       help='分类置信度阈值 (默认: 0.6)')

    args = parser.parse_args()

    # 验证参数
    if args.mode == 'video' and not args.video_path:
        parser.error("video模式需要提供 --video_path")
    if args.mode == 'image' and not args.image_path:
        parser.error("image模式需要提供 --image_path")

    # 创建检测器
    logger.info("=" * 50)
    logger.info("深蹲检测器启动")
    logger.info("=" * 50)

    detector = SquatDetector(
        pose_samples_folder=args.samples,
        confidence_threshold=args.confidence
    )

    # 根据模式运行
    if args.mode == 'realtime':
        logger.info(f"启动实时检测 (摄像头 {args.camera})")
        logger.info("按 'q' 退出")
        process_realtime(detector, args.camera)

    elif args.mode == 'video':
        logger.info(f"处理视频: {args.video_path}")
        process_video(detector, args.video_path, args.output)

    elif args.mode == 'image':
        logger.info(f"处理图片: {args.image_path}")
        process_image(detector, args.image_path, args.output)


def process_realtime(detector: SquatDetector, camera_idx: int = 0):
    """实时摄像头处理"""
    cap = cv2.VideoCapture(camera_idx)
    if not cap.isOpened():
        logger.error(f"无法打开摄像头 {camera_idx}")
        return

    # 设置分辨率
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    logger.info("实时检测开始，按 'q' 退出，按 'r' 重置计数")

    while True:
        ret, frame = cap.read()
        if not ret:
            logger.warning("读取摄像头失败")
            break

        # 处理帧
        annotated_frame, results = detector.process_frame(frame)

        # 显示
        cv2.imshow('Squat Detection (Realtime)', annotated_frame)

        # 键盘控制
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r'):
            detector.squat_counter.reset()
            logger.info("计数器已重置")

    cap.release()
    cv2.destroyAllWindows()

    # 输出统计
    logger.info("\n" + "=" * 50)
    logger.info("检测结束")
    logger.info(f"最终深蹲次数: {detector.squat_counter.squat_count}")
    logger.info("=" * 50)


if __name__ == '__main__':
    main()
