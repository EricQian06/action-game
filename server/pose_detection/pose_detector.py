"""
姿势检测器
基于MediaPipe Pose实现人体关键点检测和姿势匹配
"""
import cv2
import numpy as np
import mediapipe as mp
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    MEDIAPIPE_MODEL_COMPLEXITY,
    MEDIAPIPE_MIN_DETECTION_CONFIDENCE,
    MEDIAPIPE_MIN_TRACKING_CONFIDENCE,
    POSE_SIMILARITY_THRESHOLD,
    POSE_KEYPOINT_WEIGHTS,
    GAME_SCORE_THRESHOLD
)

logger = logging.getLogger(__name__)


class PoseLandmark(Enum):
    """姿势关键点枚举 (MediaPipe格式)"""
    NOSE = 0
    LEFT_EYE_INNER = 1
    LEFT_EYE = 2
    LEFT_EYE_OUTER = 3
    RIGHT_EYE_INNER = 4
    RIGHT_EYE = 5
    RIGHT_EYE_OUTER = 6
    LEFT_EAR = 7
    RIGHT_EAR = 8
    MOUTH_LEFT = 9
    MOUTH_RIGHT = 10
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_PINKY = 17
    RIGHT_PINKY = 18
    LEFT_INDEX = 19
    RIGHT_INDEX = 20
    LEFT_THUMB = 21
    RIGHT_THUMB = 22
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_HEEL = 29
    RIGHT_HEEL = 30
    LEFT_FOOT_INDEX = 31
    RIGHT_FOOT_INDEX = 32


@dataclass
class Landmark:
    """关键点数据类"""
    x: float
    y: float
    z: float = 0.0
    visibility: float = 1.0
    presence: float = 1.0

    def to_dict(self) -> Dict:
        return {
            'x': self.x,
            'y': self.y,
            'z': self.z,
            'visibility': self.visibility,
            'presence': self.presence
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Landmark':
        return cls(
            x=data.get('x', 0),
            y=data.get('y', 0),
            z=data.get('z', 0),
            visibility=data.get('visibility', 1.0),
            presence=data.get('presence', 1.0)
        )


@dataclass
class Pose:
    """姿势数据类"""
    landmarks: List[Landmark]
    world_landmarks: Optional[List[Landmark]] = None
    segmentation_mask: Optional[np.ndarray] = None

    def get_landmark(self, landmark: PoseLandmark) -> Optional[Landmark]:
        """获取指定关键点"""
        idx = landmark.value
        if 0 <= idx < len(self.landmarks):
            return self.landmarks[idx]
        return None

    def to_dict(self) -> Dict:
        return {
            'landmarks': [lm.to_dict() for lm in self.landmarks],
            'world_landmarks': [lm.to_dict() for lm in self.world_landmarks] if self.world_landmarks else None
        }


class PoseDetector:
    """姿势检测器类"""

    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

        self.pose = None
        self._initialized = False

        try:
            self._init_mediapipe()
        except Exception as e:
            logger.error(f'MediaPipe初始化失败: {e}')
            raise

    def _init_mediapipe(self):
        """初始化MediaPipe"""
        self.pose = self.mp_pose.Pose(
            static_image_mode=True,  # 静态图像模式
            model_complexity=MEDIAPIPE_MODEL_COMPLEXITY,
            smooth_landmarks=True,
            enable_segmentation=False,  # 不需要分割
            min_detection_confidence=MEDIAPIPE_MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=MEDIAPIPE_MIN_TRACKING_CONFIDENCE
        )
        self._initialized = True
        logger.info('MediaPipe Pose已初始化')

    def is_ready(self) -> bool:
        """检查检测器是否就绪"""
        return self._initialized and self.pose is not None

    def detect_pose(self, image_data: bytes) -> Dict:
        """
        检测图像中的姿势

        Args:
            image_data: JPEG/PNG格式的图像数据

        Returns:
            包含检测结果的字典
        """
        if not self.is_ready():
            return {
                'success': False,
                'error': '检测器未就绪'
            }

        try:
            # 解码图像
            import numpy as np
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if image is None:
                return {
                    'success': False,
                    'error': '图像解码失败'
                }

            # 转换为RGB
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # 检测姿势
            results = self.pose.process(image_rgb)

            if not results.pose_landmarks:
                return {
                    'success': False,
                    'error': '未检测到人体姿势'
                }

            # 提取关键点
            landmarks = []
            for lm in results.pose_landmarks.landmark:
                landmarks.append({
                    'x': lm.x,
                    'y': lm.y,
                    'z': lm.z,
                    'visibility': lm.visibility
                })

            # 提取世界坐标关键点(如果有)
            world_landmarks = None
            if results.pose_world_landmarks:
                world_landmarks = []
                for lm in results.pose_world_landmarks.landmark:
                    world_landmarks.append({
                        'x': lm.x,
                        'y': lm.y,
                        'z': lm.z,
                        'visibility': lm.visibility
                    })

            # 绘制姿势（用于调试和预览）
            annotated_image = image_rgb.copy()
            self.mp_drawing.draw_landmarks(
                annotated_image,
                results.pose_landmarks,
                self.mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=self.mp_drawing_styles.get_default_pose_landmarks_style()
            )

            # 转换回BGR并编码
            annotated_bgr = cv2.cvtColor(annotated_image, cv2.COLOR_RGB2BGR)
            _, buffer = cv2.imencode('.jpg', annotated_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
            annotated_base64 = buffer.tobytes()

            return {
                'success': True,
                'landmarks': landmarks,
                'world_landmarks': world_landmarks,
                'annotated_image': annotated_base64
            }

        except Exception as e:
            logger.error(f'姿势检测失败: {e}')
            return {
                'success': False,
                'error': f'检测过程出错: {str(e)}'
            }

    def compare_poses(self, detected_landmarks: List[Dict], target_pose: Dict) -> Dict:
        """
        比较检测到的姿势与目标姿势

        Args:
            detected_landmarks: 检测到的关键点列表
            target_pose: 目标姿势定义

        Returns:
            匹配结果字典
        """
        try:
            # 计算关键点距离
            distances = []
            weights = []

            # 定义关键点名称到索引的映射
            keypoint_names = [
                'nose', 'left_eye_inner', 'left_eye', 'left_eye_outer',
                'right_eye_inner', 'right_eye', 'right_eye_outer',
                'left_ear', 'right_ear', 'mouth_left', 'mouth_right',
                'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
                'left_wrist', 'right_wrist', 'left_pinky', 'right_pinky',
                'left_index', 'right_index', 'left_thumb', 'right_thumb',
                'left_hip', 'right_hip', 'left_knee', 'right_knee',
                'left_ankle', 'right_ankle', 'left_heel', 'right_heel',
                'left_foot_index', 'right_foot_index'
            ]

            # 遍历目标姿势定义的关键点
            for kp_name, target_def in target_pose.items():
                if kp_name not in keypoint_names:
                    continue

                idx = keypoint_names.index(kp_name)
                if idx >= len(detected_landmarks):
                    continue

                detected = detected_landmarks[idx]

                # 检查可见性
                if detected.get('visibility', 1.0) < 0.5:
                    continue

                # 根据目标定义计算差异
                # 支持相对位置定义，如 {"relation": "above", "target": "shoulder"}
                if isinstance(target_def, dict):
                    relation = target_def.get('relation', '')
                    # 这里可以实现更复杂的相对位置检查
                    # 目前简化为计算距离
                    target_x = target_def.get('x', detected['x'])
                    target_y = target_def.get('y', detected['y'])
                else:
                    target_x = target_def.get('x', detected['x']) if isinstance(target_def, dict) else detected['x']
                    target_y = target_def.get('y', detected['y']) if isinstance(target_def, dict) else detected['y']

                # 计算欧氏距离
                dist = ((detected['x'] - target_x) ** 2 + (detected['y'] - target_y) ** 2) ** 0.5

                # 获取权重
                weight = POSE_KEYPOINT_WEIGHTS.get(kp_name, 1.0)

                distances.append(dist)
                weights.append(weight)

            if not distances:
                return {
                    'success': False,
                    'score': 0.0,
                    'message': '无法计算姿势匹配（可能是关键点不可见）'
                }

            # 计算加权平均距离
            weighted_dist = sum(d * w for d, w in zip(distances, weights)) / sum(weights)

            # 转换为相似度分数 (距离越小分数越高)
            # 使用指数衰减函数
            similarity = max(0, 1 - weighted_dist * 2)  # 缩放因子可调整

            # 判断是否成功
            success = similarity >= GAME_SCORE_THRESHOLD

            # 生成反馈信息
            if success:
                feedback = '动作完美！继续保持！'
                if similarity < 0.9:
                    feedback = '动作正确，但还可以更标准'
            else:
                feedback = '动作不够准确，请参考示例调整姿势'
                # 可以添加具体哪个部位需要调整的建议

            return {
                'success': success,
                'score': round(similarity, 3),
                'raw_distance': round(weighted_dist, 4),
                'feedback': feedback,
                'threshold': GAME_SCORE_THRESHOLD
            }

        except Exception as e:
            logger.error(f'姿势比较失败: {e}')
            return {
                'success': False,
                'score': 0.0,
                'error': str(e),
                'feedback': '姿势匹配过程出错'
            }

    def calculate_angle(self, point1: Dict, point2: Dict, point3: Dict) -> float:
        """
        计算三个点形成的角度

        Args:
            point1: 第一个点 (通常是关节点)
            point2: 第二个点 (顶角)
            point3: 第三个点

        Returns:
            角度值（度）
        """
        import math

        # 计算向量
        vec1 = {
            'x': point1['x'] - point2['x'],
            'y': point1['y'] - point2['y']
        }
        vec2 = {
            'x': point3['x'] - point2['x'],
            'y': point3['y'] - point2['y']
        }

        # 计算点积和模
        dot = vec1['x'] * vec2['x'] + vec1['y'] * vec2['y']
        mag1 = math.sqrt(vec1['x']**2 + vec1['y']**2)
        mag2 = math.sqrt(vec2['x']**2 + vec2['y']**2)

        if mag1 == 0 or mag2 == 0:
            return 0.0

        # 计算角度
        cos_angle = max(-1, min(1, dot / (mag1 * mag2)))
        angle = math.degrees(math.acos(cos_angle))

        return angle

    def get_body_angles(self, landmarks: List[Dict]) -> Dict[str, float]:
        """
        计算身体各部位的角度

        Args:
            landmarks: 关键点列表

        Returns:
            各部位角度字典
        """
        angles = {}

        # 定义要计算的角度
        angle_definitions = [
            ('left_elbow', 'left_shoulder', 'left_elbow', 'left_wrist'),
            ('right_elbow', 'right_shoulder', 'right_elbow', 'right_wrist'),
            ('left_shoulder', 'left_elbow', 'left_shoulder', 'left_hip'),
            ('right_shoulder', 'right_elbow', 'right_shoulder', 'right_hip'),
            ('left_knee', 'left_hip', 'left_knee', 'left_ankle'),
            ('right_knee', 'right_hip', 'right_knee', 'right_ankle'),
        ]

        keypoint_names = [
            'nose', 'left_eye_inner', 'left_eye', 'left_eye_outer',
            'right_eye_inner', 'right_eye', 'right_eye_outer',
            'left_ear', 'right_ear', 'mouth_left', 'mouth_right',
            'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
            'left_wrist', 'right_wrist', 'left_pinky', 'right_pinky',
            'left_index', 'right_index', 'left_thumb', 'right_thumb',
            'left_hip', 'right_hip', 'left_knee', 'right_knee',
            'left_ankle', 'right_ankle', 'left_heel', 'right_heel',
            'left_foot_index', 'right_foot_index'
        ]

        for angle_name, p1_name, p2_name, p3_name in angle_definitions:
            try:
                # 查找关键点的索引
                p1_idx = keypoint_names.index(p1_name) if p1_name in keypoint_names else -1
                p2_idx = keypoint_names.index(p2_name) if p2_name in keypoint_names else -1
                p3_idx = keypoint_names.index(p3_name) if p3_name in keypoint_names else -1

                if p1_idx >= 0 and p2_idx >= 0 and p3_idx >= 0:
                    if p1_idx < len(landmarks) and p2_idx < len(landmarks) and p3_idx < len(landmarks):
                        p1 = landmarks[p1_idx]
                        p2 = landmarks[p2_idx]
                        p3 = landmarks[p3_idx]

                        # 检查可见性
                        if (p1.get('visibility', 1) > 0.5 and
                            p2.get('visibility', 1) > 0.5 and
                            p3.get('visibility', 1) > 0.5):
                            angle = self.calculate_angle(p1, p2, p3)
                            angles[angle_name] = angle
            except Exception as e:
                logger.debug(f'计算角度 {angle_name} 失败: {e}')
                continue

        return angles


# 辅助函数
def visualize_pose(image: np.ndarray, landmarks: List[Dict],
                 connections: bool = True) -> np.ndarray:
    """
    在图像上绘制姿势关键点

    Args:
        image: 输入图像
        landmarks: 关键点列表
        connections: 是否绘制连接线

    Returns:
        绘制后的图像
    """
    annotated = image.copy()
    h, w = image.shape[:2]

    # 绘制关键点
    for i, lm in enumerate(landmarks):
        if lm.get('visibility', 1.0) > 0.5:
            x = int(lm['x'] * w)
            y = int(lm['y'] * h)
            cv2.circle(annotated, (x, y), 5, (0, 255, 0), -1)

    # 绘制连接线 (简化版骨架)
    if connections:
        connections_list = [
            (11, 13), (13, 15),  # 左臂
            (12, 14), (14, 16),  # 右臂
            (11, 12),            # 肩膀
            (11, 23), (12, 24),  # 躯干
            (23, 25), (25, 27),  # 左腿
            (24, 26), (26, 28),  # 右腿
            (23, 24),            # 髋部
        ]

        for start_idx, end_idx in connections_list:
            if (start_idx < len(landmarks) and end_idx < len(landmarks)):
                lm1 = landmarks[start_idx]
                lm2 = landmarks[end_idx]

                if (lm1.get('visibility', 1.0) > 0.5 and
                    lm2.get('visibility', 1.0) > 0.5):
                    x1 = int(lm1['x'] * w)
                    y1 = int(lm1['y'] * h)
                    x2 = int(lm2['x'] * w)
                    y2 = int(lm2['y'] * h)
                    cv2.line(annotated, (x1, y1), (x2, y2), (255, 0, 0), 2)

    return annotated


def extract_pose_features(landmarks: List[Dict]) -> Dict[str, Any]:
    """
    提取姿势特征向量

    Args:
        landmarks: 关键点列表

    Returns:
        特征向量字典
    """
    features = {
        'arm_angles': {},
        'leg_angles': {},
        'body_ratio': {},
        'symmetry': {}
    }

    keypoint_names = [
        'nose', 'left_eye_inner', 'left_eye', 'left_eye_outer',
        'right_eye_inner', 'right_eye', 'right_eye_outer',
        'left_ear', 'right_ear', 'mouth_left', 'mouth_right',
        'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
        'left_wrist', 'right_wrist', 'left_pinky', 'right_pinky',
        'left_index', 'right_index', 'left_thumb', 'right_thumb',
        'left_hip', 'right_hip', 'left_knee', 'right_knee',
        'left_ankle', 'right_ankle', 'left_heel', 'right_heel',
        'left_foot_index', 'right_foot_index'
    ]

    def get_point(name):
        idx = keypoint_names.index(name) if name in keypoint_names else -1
        if 0 <= idx < len(landmarks):
            lm = landmarks[idx]
            if lm.get('visibility', 1.0) > 0.5:
                return np.array([lm['x'], lm['y'], lm.get('z', 0)])
        return None

    def calc_angle(p1, p2, p3):
        if p1 is None or p2 is None or p3 is None:
            return None
        v1 = p1 - p2
        v2 = p3 - p2
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
        cos_angle = np.clip(cos_angle, -1, 1)
        return np.degrees(np.arccos(cos_angle))

    # 计算手臂角度
    left_shoulder = get_point('left_shoulder')
    left_elbow = get_point('left_elbow')
    left_wrist = get_point('left_wrist')

    right_shoulder = get_point('right_shoulder')
    right_elbow = get_point('right_elbow')
    right_wrist = get_point('right_wrist')

    features['arm_angles']['left_elbow'] = calc_angle(left_shoulder, left_elbow, left_wrist)
    features['arm_angles']['right_elbow'] = calc_angle(right_shoulder, right_elbow, right_wrist)

    # 计算腿部角度
    left_hip = get_point('left_hip')
    left_knee = get_point('left_knee')
    left_ankle = get_point('left_ankle')

    right_hip = get_point('right_hip')
    right_knee = get_point('right_knee')
    right_ankle = get_point('right_ankle')

    features['leg_angles']['left_knee'] = calc_angle(left_hip, left_knee, left_ankle)
    features['leg_angles']['right_knee'] = calc_angle(right_hip, right_knee, right_ankle)

    # 计算身体比例
    if left_shoulder is not None and left_hip is not None:
        torso_length = np.linalg.norm(left_shoulder - left_hip)
        features['body_ratio']['left_torso'] = float(torso_length)

    # 计算左右对称性
    if (features['arm_angles']['left_elbow'] is not None and
        features['arm_angles']['right_elbow'] is not None):
        symmetry = 1 - abs(features['arm_angles']['left_elbow'] -
                          features['arm_angles']['right_elbow']) / 180
        features['symmetry']['elbows'] = float(max(0, symmetry))

    return features
