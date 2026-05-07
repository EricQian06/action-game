"""
诊断脚本：分析为什么相似度几乎为0
"""
import os
import sys
import numpy as np
from pathlib import Path

CURRENT_DIR = Path(__file__).parent
os.chdir(CURRENT_DIR)
sys.path.insert(0, str(CURRENT_DIR))

from action_matcher import ActionMatcher

def diagnose():
    matcher = ActionMatcher(pose_samples_folder=str(CURRENT_DIR / "pose_samples"))
    actions = matcher.get_available_actions()
    print(f"可用动作: {actions}")
    print()

    # 选几张有代表性的照片进行诊断
    test_cases = [
        ("training_data/standing/stand_01.png", "standing"),
        ("training_data/standing/stand_02.png", "standing"),
        ("training_data/big/big_01.jpg", "big"),
        ("training_data/hands_up/hands_up_02.jpg", "hands_up"),
        ("training_data/squat/squat_01.png", "squat"),
        ("training_data/stride/stride_01.jpg", "stride"),
        ("input.jpg", "standing"),
    ]

    for img_rel, target_action in test_cases:
        img_path = CURRENT_DIR / img_rel
        print(f"=== {img_rel} -> {target_action} ===")

        if not img_path.exists():
            print(f"  图片不存在")
            continue

        landmarks = matcher.extract_pose(str(img_path))
        if landmarks is None:
            print(f"  姿态提取失败")
            continue

        query_embedding = matcher.pose_embedder(landmarks)
        print(f"  提取到 {len(landmarks)} 个关键点")
        print(f"  Query embedding shape: {query_embedding.shape}")
        print(f"  Query embedding range: [{query_embedding.min():.4f}, {query_embedding.max():.4f}]")
        print(f"  Query embedding mean: {query_embedding.mean():.4f}")

        if target_action not in matcher.action_samples:
            print(f"  动作 {target_action} 没有样本")
            continue

        samples = matcher.action_samples[target_action]
        print(f"  样本数量: {len(samples)}")

        if len(samples) == 0:
            continue

        # 计算与所有样本的距离
        distances = []
        for i, sample in enumerate(samples):
            dist = matcher._compute_distance(query_embedding, sample['embedding'])
            distances.append(dist)

        distances = np.array(distances)
        print(f"  距离范围: [{distances.min():.4f}, {distances.max():.4f}]")
        print(f"  平均距离: {distances.mean():.4f}")
        print(f"  中位距离: {np.median(distances):.4f}")

        # 前10个最近距离
        sorted_d = np.sort(distances)[:10]
        print(f"  最近10个距离: {', '.join([f'{d:.4f}' for d in sorted_d])}")

        # 计算分数（模拟 _compute_similarity_score）
        sorted_indices = np.argsort(distances)
        filtered_indices = sorted_indices[:matcher.top_n_by_max_distance]
        filtered_distances = distances[filtered_indices]
        n_nearest = min(matcher.top_n_by_mean_distance, len(filtered_distances))
        nearest_distances = filtered_distances[:n_nearest]
        mean_distance = np.mean(nearest_distances)
        scale = 5.0
        similarity = np.exp(-mean_distance / scale)
        if mean_distance > 20:
            similarity *= 0.5
        if mean_distance > 30:
            similarity *= 0.5
        print(f"  Top-{n_nearest} 平均距离: {mean_distance:.4f}")
        print(f"  计算相似度: {similarity:.4f} ({similarity:.2%})")

        # 对比第一个样本的embedding
        sample_emb = samples[0]['embedding']
        print(f"  样本[0] embedding range: [{sample_emb.min():.4f}, {sample_emb.max():.4f}]")
        print(f"  样本[0] embedding mean: {sample_emb.mean():.4f}")
        print()

if __name__ == '__main__':
    diagnose()
