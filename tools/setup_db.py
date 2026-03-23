"""
数据库初始化脚本
用于创建数据库表和填充初始数据
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

from app import app, db, User, GameLevel, ActionTemplate, GameSession
import json
from datetime import datetime

def init_database():
    """初始化数据库"""
    with app.app_context():
        print("=" * 60)
        print("动作闯关游戏 - 数据库初始化")
        print("=" * 60)

        # 删除所有表
        print("\n[1/5] 清理现有数据库...")
        db.drop_all()
        print("✓ 数据库已清理")

        # 创建所有表
        print("\n[2/5] 创建数据库表...")
        db.create_all()
        print("✓ 数据库表已创建")

        # 添加示例用户
        print("\n[3/5] 添加示例用户...")
        import hashlib

        users = [
            {
                'username': 'admin',
                'password': hashlib.sha256('admin123'.encode()).hexdigest(),
                'current_level': 5,
                'total_score': 2500
            },
            {
                'username': 'player1',
                'password': hashlib.sha256('123456'.encode()).hexdigest(),
                'current_level': 1,
                'total_score': 0
            },
            {
                'username': 'testuser',
                'password': hashlib.sha256('test123'.encode()).hexdigest(),
                'current_level': 3,
                'total_score': 1200
            }
        ]

        for user_data in users:
            user = User(**user_data)
            db.session.add(user)

        db.session.commit()
        print(f"✓ 已添加 {len(users)} 个示例用户")

        # 添加动作模板
        print("\n[4/5] 添加动作模板...")

        actions = [
            {
                'name': '举手',
                'name_en': 'hands_up',
                'description': '双手举过头顶，保持3秒',
                'difficulty': 1,
                'target_pose': json.dumps({
                    'left_wrist': {'y': 0.2, 'relation': 'above', 'target': 'nose'},
                    'right_wrist': {'y': 0.2, 'relation': 'above', 'target': 'nose'}
                }),
                'score_threshold': 0.75,
                'duration_seconds': 3
            },
            {
                'name': '叉腰',
                'name_en': 'hands_on_hips',
                'description': '双手叉腰，手肘向外展开',
                'difficulty': 1,
                'target_pose': json.dumps({
                    'left_wrist': {'x': 0.3, 'relation': 'near', 'target': 'left_hip'},
                    'right_wrist': {'x': 0.7, 'relation': 'near', 'target': 'right_hip'}
                }),
                'score_threshold': 0.75,
                'duration_seconds': 3
            },
            {
                'name': '踢腿',
                'name_en': 'kick',
                'description': '单腿向前踢出，膝盖伸直',
                'difficulty': 2,
                'target_pose': json.dumps({
                    'left_knee': {'angle': 160, 'relation': 'greater_than'},
                    'left_ankle': {'y': 0.6, 'relation': 'above', 'target': 'right_ankle'}
                }),
                'score_threshold': 0.70,
                'duration_seconds': 2
            },
            {
                'name': '侧身',
                'name_en': 'side_stretch',
                'description': '身体向一侧倾斜，一只手向上伸展',
                'difficulty': 2,
                'target_pose': json.dumps({
                    'nose': {'x': 0.4, 'relation': 'less_than'},
                    'left_wrist': {'y': 0.2, 'relation': 'above', 'target': 'nose'}
                }),
                'score_threshold': 0.70,
                'duration_seconds': 3
            },
            {
                'name': '深蹲',
                'name_en': 'squat',
                'description': '双腿弯曲下蹲，大腿与地面平行',
                'difficulty': 3,
                'target_pose': json.dumps({
                    'left_knee': {'angle': 90, 'relation': 'near'},
                    'right_knee': {'angle': 90, 'relation': 'near'},
                    'left_hip': {'y': 0.5, 'relation': 'below', 'target': 'left_knee'}
                }),
                'score_threshold': 0.65,
                'duration_seconds': 3
            }
        ]

        for action_data in actions:
            action = ActionTemplate(**action_data)
            db.session.add(action)

        db.session.commit()
        print(f"✓ 已添加 {len(actions)} 个动作模板")

        # 添加游戏关卡
        print("\n[5/5] 添加游戏关卡...")

        levels = [
            {
                'name': '入门训练',
                'description': '学习基本动作，掌握游戏操作。适合初学者的简单动作练习。',
                'difficulty': 1,
                'action_sequence': json.dumps([1, 2]),  # 举手、叉腰
                'required_score': 50,
                'time_limit': 60
            },
            {
                'name': '进阶挑战',
                'description': '难度提升，考验身体协调性。需要完成侧身伸展等动作。',
                'difficulty': 2,
                'action_sequence': json.dumps([4, 1, 2]),  # 侧身、举手、叉腰
                'required_score': 60,
                'time_limit': 90
            },
            {
                'name': '力量训练',
                'description': '锻炼腿部力量，完成深蹲和踢腿动作。',
                'difficulty': 3,
                'action_sequence': json.dumps([5, 3, 5]),  # 深蹲、踢腿、深蹲
                'required_score': 65,
                'time_limit': 120
            },
            {
                'name': '综合挑战',
                'description': '综合运用所有动作，考验全面能力。',
                'difficulty': 3,
                'action_sequence': json.dumps([1, 4, 5, 3, 2]),  # 全套动作
                'required_score': 70,
                'time_limit': 150
            },
            {
                'name': '大师试炼',
                'description': '最高难度挑战，需要完美的动作执行。',
                'difficulty': 4,
                'action_sequence': json.dumps([5, 4, 3, 5, 1, 2]),
                'required_score': 75,
                'time_limit': 180
            }
        ]

        for level_data in levels:
            level = GameLevel(**level_data)
            db.session.add(level)

        db.session.commit()
        print(f"✓ 已添加 {len(levels)} 个游戏关卡")

        print("\n" + "=" * 60)
        print("数据库初始化完成!")
        print("=" * 60)
        print(f"\n数据库统计:")
        print(f"  - 用户数量: {User.query.count()}")
        print(f"  - 动作模板: {ActionTemplate.query.count()}")
        print(f"  - 游戏关卡: {GameLevel.query.count()}")
        print(f"\n默认登录账号:")
        print(f"  - 用户名: admin, 密码: admin123")
        print(f"  - 用户名: player1, 密码: 123456")
        print("=" * 60)

if __name__ == '__main__':
    init_database()
