import cv2
import mediapipe as mp
from tqdm import tqdm
import time
import matplotlib.pyplot as plt
# %matplotlib inline

def look_img(img):
    img_RGB=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)
    plt.imshow(img_RGB)
    plt.show()

mp_pose=mp.solutions.pose
mp_drawing=mp.solutions.drawing_utils
pose=mp_pose.Pose(static_image_mode=True,
                  model_complexity=2,
                  smooth_landmarks=True,
                  enable_segmentation=True,
                  min_detection_confidence=0.5,
                  min_tracking_confidence=0.5)
img=cv2.imread('1.jpg')
look_img(img)
img_RGB=cv2.cvtColor(img,cv2.COLOR_BGR2RGB) 
results=pose.process(img_RGB)
mp_drawing.draw_landmarks(img,results.pose_landmarks,mp_pose.POSE_CONNECTIONS)
look_img(img)
mp_drawing.plot_landmarks(results.pose_world_landmarks,mp_pose.POSE_CONNECTIONS)