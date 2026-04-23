"""
深蹲计数器
基于姿态分类器的深蹲动作检测和计数
"""
import numpy as np
from enum import Enum
from typing import Dict, List, Tuple, Optional
from collections import deque
import logging

logger = logging.getLogger(__name__)


class SquatState(Enum):
    """深蹲状态"""
    STANDING = "standing"      # 站立
    SQUATTING = "squatting"    # 蹲下中
    DEEP_SQUAT = "deep_squat"  # 深蹲到底
    RISING = "rising"          # 站起中
    UNKNOWN = "unknown"        # 未知


class SquatCounter:
    """
    深蹲计数器

    使用状态机跟踪深蹲动作，当完成一次完整的
    站立 -> 蹲下 -> 站起 循环时计数+1
    """

    def __init__(
        self,
        confidence_threshold: float = 0.6,
        state_history_size: int = 5,
        min_squat_frames: int = 3,
        angle_threshold: float = 110.0
    ):
        """
        初始化计数器

        Args:
            confidence_threshold: 分类置信度阈值
            state_history_size: 状态历史队列大小（用于平滑）
            min_squat_frames: 最小深蹲帧数（防止抖动）
            angle_threshold: 膝盖角度阈值（小于此角度认为是蹲下）
        """
        self.confidence_threshold = confidence_threshold
        self.min_squat_frames = min_squat_frames
        self.angle_threshold = angle_threshold

        # 状态历史（用于平滑）
        self.state_history = deque(maxlen=state_history_size)

        # 当前状态
        self.current_state = SquatState.UNKNOWN
        self.state_frame_count = 0

        # 计数
        self.squat_count = 0
        self.last_squat_time = None

        # 状态转换记录（用于调试）
        self.state_transitions = []

        logger.info(f"深蹲计数器初始化完成 (threshold={confidence_threshold})")

    def update(
        self,
        classification_result: Dict[str, int],
        knee_angles: Optional[Tuple[float, float]] = None,
        timestamp: Optional[float] = None
    ) -> Dict:
        """
        更新计数器状态

        Args:
            classification_result: 分类器输出，如 {'standing': 8, 'squat': 2}
            knee_angles: 膝盖角度 (左膝, 右膝)
            timestamp: 当前时间戳

        Returns:
            包含当前状态和计数的字典
        """
        # 确定当前帧的状态
        new_state = self._determine_state(classification_result, knee_angles)

        # 添加到历史队列
        self.state_history.append(new_state)

        # 获取平滑后的状态（多数投票）
        smoothed_state = self._get_smoothed_state()

        # 状态转换检测
        if smoothed_state != self.current_state:
            self._handle_state_transition(self.current_state, smoothed_state, timestamp)
            self.current_state = smoothed_state
            self.state_frame_count = 1
        else:
            self.state_frame_count += 1

        # 检查是否完成一次深蹲
        squat_completed = self._check_squat_completion()

        return {
            'state': self.current_state.value,
            'squat_count': self.squat_count,
            'squat_completed': squat_completed,
            'state_frame_count': self.state_frame_count,
            'raw_classification': classification_result,
            'knee_angles': knee_angles
        }

    def _determine_state(
        self,
        classification_result: Dict[str, int],
        knee_angles: Optional[Tuple[float, float]]
    ) -> SquatState:
        """根据分类结果和角度确定状态"""

        # 获取票数最多的类别
        if not classification_result:
            return SquatState.UNKNOWN

        total_votes = sum(classification_result.values())
        if total_votes == 0:
            return SquatState.UNKNOWN

        # 找出最高票数的类别
        max_class = max(classification_result, key=classification_result.get)
        max_votes = classification_result[max_class]
        confidence = max_votes / total_votes

        # 置信度太低则返回未知
        if confidence < self.confidence_threshold:
            return SquatState.UNKNOWN

        # 根据类别名确定状态
        max_class_lower = max_class.lower()

        if 'stand' in max_class_lower:
            # 结合膝盖角度判断是否真正站立
            if knee_angles:
                avg_knee_angle = sum(knee_angles) / 2
                if avg_knee_angle > self.angle_threshold:
                    return SquatState.STANDING
                else:
                    return SquatState.SQUATTING
            return SquatState.STANDING

        elif 'squat' in max_class_lower or 'down' in max_class_lower:
            # 检查膝盖角度判断深蹲深度
            if knee_angles:
                avg_knee_angle = sum(knee_angles) / 2
                if avg_knee_angle < 90:
                    return SquatState.DEEP_SQUAT
            return SquatState.SQUATTING

        elif 'rise' in max_class_lower or 'up' in max_class_lower:
            return SquatState.RISING

        return SquatState.UNKNOWN

    def _get_smoothed_state(self) -> SquatState:
        """从状态历史中获取平滑后的状态（多数投票）"""
        if not self.state_history:
            return self.current_state if self.current_state else SquatState.UNKNOWN

        # 统计每个状态的出现次数
        state_counts = {}
        for state in self.state_history:
            state_counts[state] = state_counts.get(state, 0) + 1

        # 返回出现最多的状态
        return max(state_counts, key=state_counts.get)

    def _handle_state_transition(
        self,
        old_state: SquatState,
        new_state: SquatState,
        timestamp: Optional[float]
    ):
        """处理状态转换"""
        transition = {
            'from': old_state.value,
            'to': new_state.value,
            'timestamp': timestamp
        }
        self.state_transitions.append(transition)

        # 限制历史记录长度
        if len(self.state_transitions) > 100:
            self.state_transitions = self.state_transitions[-100:]

        logger.debug(f"状态转换: {old_state.value} -> {new_state.value}")

    def _check_squat_completion(self) -> bool:
        """
        检查是否完成一次深蹲
        完成条件：经历过 站立 -> 蹲下 -> 站立 的完整循环
        """
        if len(self.state_transitions) < 2:
            return False

        # 检查最近的转换中是否有完整的深蹲循环
        # 简化检查：如果当前是站立状态，且之前是蹲下状态，且持续足够帧数
        if self.current_state == SquatState.STANDING:
            # 查找最近的非站立状态
            for transition in reversed(self.state_transitions):
                if transition['to'] in [SquatState.SQUATTING.value, SquatState.DEEP_SQUAT.value]:
                    # 检查是否已经完成过计数（避免重复计数）
                    if self.last_squat_time is None or transition['timestamp'] is None:
                        return True
                    elif transition['timestamp'] > self.last_squat_time:
                        return True

        return False

    def increment_count(self, timestamp: Optional[float] = None):
        """增加深蹲计数"""
        self.squat_count += 1
        self.last_squat_time = timestamp
        logger.info(f"深蹲计数: {self.squat_count}")
        return self.squat_count

    def reset(self):
        """重置计数器"""
        self.squat_count = 0
        self.current_state = SquatState.UNKNOWN
        self.state_frame_count = 0
        self.state_history.clear()
        self.state_transitions.clear()
        self.last_squat_time = None
        logger.info("深蹲计数器已重置")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            'squat_count': self.squat_count,
            'current_state': self.current_state.value,
            'state_frame_count': self.state_frame_count,
            'total_transitions': len(self.state_transitions),
            'recent_transitions': self.state_transitions[-5:] if self.state_transitions else []
        }
