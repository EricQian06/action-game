"""
游戏管理器
负责管理游戏会话、动作序列和游戏状态
"""
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class GameSession:
    """游戏会话类"""

    def __init__(self, session_id: int, level_id: int, action_ids: List[int]):
        self.session_id = session_id
        self.level_id = level_id
        self.action_ids = action_ids
        self.current_action_index = 0
        self.scores = []  # 每个动作的得分
        self.started_at = datetime.utcnow()
        self.ended_at = None
        self.status = 'active'  # active, completed, abandoned

        # 加载动作详情
        self.actions = self._load_actions()

    def _load_actions(self) -> List[Dict]:
        """从数据库加载动作详情"""
        # 这里会在app.py中从数据库查询
        # 暂时返回空列表，实际数据由调用方填充
        return []

    def set_actions(self, actions: List[Dict]):
        """设置动作详情"""
        self.actions = actions

    def get_current_action(self) -> Optional[Dict]:
        """获取当前动作"""
        if 0 <= self.current_action_index < len(self.actions):
            return self.actions[self.current_action_index]
        return None

    def move_to_next_action(self) -> Optional[Dict]:
        """移动到下一个动作"""
        self.current_action_index += 1
        return self.get_current_action()

    def record_action_result(self, action_index: int, score: float, success: bool):
        """记录动作结果"""
        self.scores.append({
            'action_index': action_index,
            'score': score,
            'success': success,
            'timestamp': datetime.utcnow().isoformat()
        })

    def get_total_score(self) -> int:
        """计算总得分"""
        return sum(int(s['score'] * 100) for s in self.scores)

    def get_completion_rate(self) -> float:
        """计算完成率"""
        if not self.scores:
            return 0.0
        successful = sum(1 for s in self.scores if s['success'])
        return successful / len(self.scores)

    def end_session(self, status: str = 'completed'):
        """结束游戏会话"""
        self.status = status
        self.ended_at = datetime.utcnow()

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'session_id': self.session_id,
            'level_id': self.level_id,
            'current_action_index': self.current_action_index,
            'total_actions': len(self.actions),
            'scores': self.scores,
            'total_score': self.get_total_score(),
            'completion_rate': self.get_completion_rate(),
            'status': self.status,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None
        }


class GameManager:
    """游戏管理器"""

    def __init__(self):
        self.sessions: Dict[int, GameSession] = {}
        logger.info('游戏管理器已初始化')

    def start_session(self, session_id: int, level_id: int, action_ids: List[int] = None) -> GameSession:
        """开始新的游戏会话"""
        session = GameSession(session_id, level_id, action_ids or [])
        self.sessions[session_id] = session
        logger.info(f'游戏会话已启动: session_id={session_id}, level_id={level_id}')
        return session

    def get_session(self, session_id: int) -> Optional[GameSession]:
        """获取游戏会话"""
        return self.sessions.get(session_id)

    def end_session(self, session_id: int, status: str = 'completed') -> Optional[Dict]:
        """结束游戏会话"""
        session = self.sessions.get(session_id)
        if session:
            session.end_session(status)
            result = session.to_dict()
            # 保存到数据库
            self._save_session_to_db(session)
            logger.info(f'游戏会话已结束: session_id={session_id}, status={status}')
            return result
        return None

    def _save_session_to_db(self, session: GameSession):
        """保存会话结果到数据库"""
        # 这里会在app.py中通过SQLAlchemy更新数据库
        # 暂时留空，实际逻辑在app.py中处理
        pass

    def get_current_action(self, session_id: int) -> Optional[Dict]:
        """获取当前动作"""
        session = self.sessions.get(session_id)
        if session:
            return session.get_current_action()
        return None

    def get_next_action(self, session_id: int) -> Optional[Dict]:
        """获取下一个动作"""
        session = self.sessions.get(session_id)
        if session:
            return session.move_to_next_action()
        return None

    def update_action_result(self, session_id: int, action_index: int, result: Dict):
        """更新动作结果"""
        session = self.sessions.get(session_id)
        if session:
            session.record_action_result(
                action_index,
                result.get('score', 0),
                result.get('success', False)
            )
            logger.info(f'动作结果已记录: session_id={session_id}, action_index={action_index}')

    def get_all_sessions(self) -> Dict[int, GameSession]:
        """获取所有会话"""
        return self.sessions.copy()

    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """清理旧会话"""
        from datetime import timedelta

        now = datetime.utcnow()
        to_remove = []

        for session_id, session in self.sessions.items():
            if session.started_at and (now - session.started_at) > timedelta(hours=max_age_hours):
                to_remove.append(session_id)

        for session_id in to_remove:
            self.end_session(session_id, 'abandoned')
            del self.sessions[session_id]

        if to_remove:
            logger.info(f'已清理 {len(to_remove)} 个过期会话')
