"""
对比 model_complexity=1 和 model_complexity=2 的检测结果差异
"""
import os
import sys
import numpy as np
from pathlib import Path
import mediapipe as mp
import cv2

CURRENT_DIR = Path(__file__).parent
os.chdir(CURRENT_DIR)
sys.path.insert(0, str(CURRENT_DIR))

from d import FullBodyPoseEmbedder

def extract_with_complexity(image_path, complexity):
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(
        static_image_mode=True,
        model_complexity=complexity,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )
    image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return None
    h, w = image.shape[:2]
    min_size = 480
    if min(h, w) < min_size:
        scale = min_size / min(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = pose.process(image_rgb)
    if not results.pose_landmarks:
        return None
    landmarks = []
    for lm in results.pose_landmarks.landmark:
        landmarks.append([lm.x, lm.y, lm.z])
    return np.array(landmarks, dtype=np.float32)

def main():
    embedder = FullBodyPoseEmbedder(torso_size_multiplier=2.5)
    test_images = [
        "training_data/standing/stand_01.png",
        "training_data/big/big_01.jpg",
        "training_data/squat/squat_01.png",
    ]

    for img in test_images:
        img_path = CURRENT_DIR / img
        print(f"\n=== {img} ===")
        emb1 = None
        emb2 = None

        landmarks1 = extract_with_complexity(str(img_path), 1)
        landmarks2 = extract_with_complexity(str(img_path), 2)

        if landmarks1 is not None:
            emb1 = embedder(landmarks1)
            print(f"model_complexity=1: detected, embedding mean={emb1.mean():.2f}, max={emb1.max():.2f}")
        else:
            print(f"model_complexity=1: NOT detected")

        if landmarks2 is not None:
            emb2 = embedder(landmarks2)
            print(f"model_complexity=2: detected, embedding mean={emb2.mean():.2f}, max={emb2.max():.2f}")
        else:
            print(f"model_complexity=2: NOT detected")

        if emb1 is not None and emb2 is not None:
            dist = np.mean(np.abs(emb1 - emb2))
            print(f"L1 distance between c1 and c2 embeddings: {dist:.4f}")
            print(f"Similarity with scale=5.0: {np.exp(-dist/5.0):.4f}")

if __name__ == '__main__':
    main()
