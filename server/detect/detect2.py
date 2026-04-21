import os
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

import cv2
import mediapipe as mp
from tqdm import tqdm
import time

mp_pose=mp.solutions.pose
mp_drawing=mp.solutions.drawing_utils
pose=mp_pose.Pose(static_image_mode=True,
                  model_complexity=2,
                  smooth_landmarks=True,
                  enable_segmentation=True,
                  min_detection_confidence=0.5,
                  min_tracking_confidence=0.5)

def process_frame(img):
    img_RGB=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)
    results=pose.process(img_RGB)
    mp_drawing.draw_landmarks(img,results.pose_landmarks,mp_pose.POSE_CONNECTIONS)
    return img

cap=cv2.VideoCapture(1)
cap.open(0)
while cap.isOpened():
    success,frame=cap.read()
    if not success:
        print('Error')
        break
    frame=process_frame(frame)
    cv2.imshow('my_window',frame)
    if cv2.waitKey(1) in [ord('q'),27]:
        break

cap.release()
cv2.destroyAllWindows()