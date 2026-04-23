from matplotlib import pyplot as plt
import os
import numpy as np
import csv

def show_image(img,figsize=(10,10)):
    plt.figure(figsize=figsize)
    plt.imshow(img)
    plt.show()

class FullBodyPoseEmbedder(object):
    def __init__(self, torso_size_multiplier=2.5):
        self._torso_size_multiplier = torso_size_multiplier
        self._landmark_names = [
            'nose',
            'left_eye_inner', 'left_eye', 'left_eye_outer',
            'right_eye_inner', 'right_eye', 'right_eye_outer',
            'left_ear', 'right_ear',
            'mouth_left', 'mouth_right',
            'left_shoulder', 'right_shoulder',
            'left_elbow', 'right_elbow',
            'left_wrist', 'right_wrist',
            'left_pinky_l', 'right_pinky_l',
            'left_index_l', 'right_index_1',
            'left_thumb_2', 'right_thumb_2',
            'left_hip', 'right_hip',
            'left_knee', 'right_knee',
            'left_ankle', 'right_ankle',
            'left_heel', 'right_heel',
            'left_foot_index', 'right_foot_index',
        ]

    def __call__(self, landmarks):
        assert landmarks.shape[0] == len(self._landmark_names), 'Unexpected number of landmarks: {}'.format(landmarks.shape[0])
        landmarks = np.copy(landmarks)
        landmarks = self._normalize_pose_landmarks(landmarks)
        embedding = self._get_pose_distance_embedding(landmarks)
        return embedding

    def _normalize_pose_landmarks(self, landmarks):
        landmarks = np.copy(landmarks)
        pose_center = self._get_pose_center(landmarks)
        landmarks -= pose_center
        pose_size = self._get_pose_size(landmarks, self._torso_size_multiplier)
        landmarks /= pose_size
        landmarks *= 100
        return landmarks

    def _get_pose_center(self, landmarks):
        left_hip = landmarks[self._landmark_names.index('left_hip')]
        right_hip = landmarks[self._landmark_names.index('right_hip')]
        center = (left_hip + right_hip) * 0.5
        return center

    def _get_pose_size(self, landmarks, torso_size_multiplier):
        landmarks = landmarks[:, :2]

        # Hips center.
        left_hip = landmarks[self._landmark_names.index('left_hip')]
        right_hip = landmarks[self._landmark_names.index('right_hip')]
        hips = (left_hip + right_hip) * 0.5

        # Shoulders center.
        left_shoulder = landmarks[self._landmark_names.index('left_shoulder')]
        right_shoulder = landmarks[self._landmark_names.index('right_shoulder')]
        shoulders = (left_shoulder + right_shoulder) * 0.5

        # Torso size.
        torso_size = np.linalg.norm(shoulders - hips)

        # Max distance from pose center.
        pose_center = self._get_pose_center(landmarks)
        max_dist = np.max(np.linalg.norm(landmarks - pose_center, axis=1))

        # Normalize by torso size or max distance.
        pose_size = max(torso_size * torso_size_multiplier, max_dist)

        return pose_size

    def _get_pose_distance_embedding(self, landmarks):
        embedding = np.array([
            # Same body.
            self._get_distance_by_names(landmarks, 'left_shoulder', 'left_wrist'),
            self._get_distance_by_names(landmarks, 'right_shoulder', 'right_wrist'),
            self._get_distance_by_names(landmarks, 'left_hip', 'left_ankle'),
            self._get_distance_by_names(landmarks, 'right_hip', 'right_ankle'),
            # Body pair.
            self._get_distance_by_names(landmarks, 'left_shoulder', 'right_shoulder'),
            self._get_distance_by_names(landmarks, 'left_hip', 'right_hip'),
            # Cross body.
            self._get_distance_by_names(landmarks, 'left_shoulder', 'right_hip'),
            self._get_distance_by_names(landmarks, 'right_shoulder', 'left_hip'),
            self._get_distance_by_names(landmarks, 'left_shoulder', 'left_ankle'),
            self._get_distance_by_names(landmarks, 'right_shoulder', 'right_ankle'),
            self._get_distance_by_names(landmarks, 'left_hip', 'left_wrist'),
            self._get_distance_by_names(landmarks, 'right_hip', 'right_wrist'),
            # Cross body pairs.
            self._get_distance_by_names(landmarks, 'left_elbow', 'right_elbow'),
            self._get_distance_by_names(landmarks, 'left_knee', 'right_knee'),
            self._get_distance_by_names(landmarks, 'left_wrist', 'right_wrist'),
            self._get_distance_by_names(landmarks, 'left_ankle', 'right_ankle'),
        ])

        return embedding
    
    def _get_average_by_names(self,landmarks, name_from, name_to):
        lmk_from=landmarks[self._landmark_names.index(name_from)]
        lmk_to=landmarks[self._landmark_names.index(name_to)]
        return (lmk_from + lmk_to) * 0.5

    def _get_distance_by_names(self, landmarks, name_from, name_to):
        lmk_from = landmarks[self._landmark_names.index(name_from)]
        lmk_to = landmarks[self._landmark_names.index(name_to)]
        return self._get_distance(lmk_from, lmk_to)

    def _get_distance(self, lmk_from, lmk_to):
        return np.linalg.norm(lmk_to - lmk_from)
    
class PoseSample(object):
    def __init__(self, name, landmarks, class_name, embedding):
        self.name = name
        self.landmarks = landmarks
        self.class_name = class_name
        self.embedding= embedding

class PoseSampleoutlier(object):
    def __init__(self, sample, detected_class, all_classes):
        self.sample = sample
        self.detected_class = detected_class
        self.all_classes = all_classes

class PoseClassifier(object):
    def __init__(self,
                 pose_samples_folder,
                 pose_embedder,
                 file_extension='csv',
                 file_separator=',',
                 n_landmarks=33,
                 n_dimensions=3,
                 top_n_by_max_distance=30,
                 top_n_by_mean_distance=10,
                 axes_weights=None):
        self._pose_embedder = pose_embedder
        self._n_landmarks = n_landmarks
        self._n_dimensions = n_dimensions
        self._top_n_by_max_distance = top_n_by_max_distance
        self._top_n_by_mean_distance = top_n_by_mean_distance
        # axes_weights will be set after we know the embedding size
        self._axes_weights = None
        self._default_axes_weights = axes_weights

        # Load pose samples from CSV files
        self._pose_samples = self._load_pose_samples(
            pose_samples_folder,
            file_extension,
            file_separator
        )

    def _load_pose_samples(self, pose_samples_folder, file_extension, file_separator):
        """Load pose samples from CSV files in the given folder."""
        pose_samples = []

        for file_name in os.listdir(pose_samples_folder):
            if not file_name.endswith('.' + file_extension):
                continue

            file_path = os.path.join(pose_samples_folder, file_name)
            class_name = os.path.splitext(file_name)[0]

            with open(file_path, 'r', newline='') as csvfile:
                reader = csv.reader(csvfile, delimiter=file_separator)
                for row_idx, row in enumerate(reader):
                    if len(row) == 0:
                        continue

                    landmarks = np.array(row, dtype=np.float32)
                    landmarks = landmarks.reshape(self._n_landmarks, self._n_dimensions)

                    embedding = self._pose_embedder(landmarks)

                    pose_samples.append(PoseSample(
                        name='{}_{}'.format(class_name, row_idx),
                        landmarks=landmarks,
                        class_name=class_name,
                        embedding=embedding
                    ))

        return pose_samples

    def __call__(self, pose_landmarks):
        """Classify the given pose landmarks and return a dictionary of
        class names to vote counts.
        """
        # Compute embedding for the input pose
        pose_embedding = self._pose_embedder(pose_landmarks)

        # Initialize axes_weights if not set, based on embedding size
        if self._axes_weights is None:
            embedding_size = len(pose_embedding)
            # Use uniform weights (all 1.0) for distance embeddings
            # Distance embeddings represent distances between body parts
            # which don't have x/y/z components to weight differently
            self._axes_weights = np.ones(embedding_size)
            logger = logging.getLogger(__name__)
            logger.info(f"Initialized axes_weights with size {embedding_size}")

        # Compute embedding for the flipped pose (for data augmentation)
        flipped_pose_landmarks = pose_landmarks.copy()
        flipped_pose_landmarks[:, 0] = -flipped_pose_landmarks[:, 0]
        flipped_pose_embedding = self._pose_embedder(flipped_pose_landmarks)

        # Filter by max distance to remove outliers
        max_dist_heap = []
        for sample_idx, sample in enumerate(self._pose_samples):
            max_dist = min(
                np.max(np.abs(sample.embedding - pose_embedding) * self._axes_weights),
                np.max(np.abs(sample.embedding - flipped_pose_embedding) * self._axes_weights),
            )
            max_dist_heap.append([max_dist, sample_idx])
        max_dist_heap = sorted(max_dist_heap, key=lambda x: x[0])
        max_dist_heap = max_dist_heap[:self._top_n_by_max_distance]

        # Filter by mean distance to find nearest poses
        mean_dist_heap = []
        for _, sample_idx in max_dist_heap:
            sample = self._pose_samples[sample_idx]
            mean_dist = min(
                np.mean(np.abs(sample.embedding - pose_embedding) * self._axes_weights),
                np.mean(np.abs(sample.embedding - flipped_pose_embedding) * self._axes_weights),
            )
            mean_dist_heap.append([mean_dist, sample_idx])
        mean_dist_heap = sorted(mean_dist_heap, key=lambda x: x[0])
        mean_dist_heap = mean_dist_heap[:self._top_n_by_mean_distance]

        # Collect results into map: (class_name -> n_samples)
        class_names = [self._pose_samples[sample_idx].class_name for _, sample_idx in mean_dist_heap]
        result = {class_name: class_names.count(class_name) for class_name in set(class_names)}
        return result