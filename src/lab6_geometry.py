"""Known similarity transforms and basic KNN ratios for lab six invariance checks."""
from __future__ import annotations

import cv2
import numpy as np


def positive_number(value, name, zero=False) -> float:
    if (isinstance(value, (str, bool)) or not np.isscalar(value) or not np.isfinite(value)
            or (value < 0 if zero else value <= 0)):
        raise ValueError(f'{name} 必须为有限' + ('非负数' if zero else '正数'))
    return float(value)


def transform_full_canvas(image: np.ndarray, angle: float = 30.0, scale: float = 0.6) -> tuple[np.ndarray, np.ndarray]:
    if not isinstance(image, np.ndarray):
        raise TypeError('变换图像应为数组')
    if image.size == 0 or image.dtype != np.uint8 or not (image.ndim == 2 or image.ndim == 3 and image.shape[2] in (3,4)):
        raise ValueError('变换输入应为非空 uint8 灰度/BGR/BGRA')
    if isinstance(angle, (str, bool)) or not np.isscalar(angle) or not np.isfinite(angle):
        raise ValueError('旋转角度必须有限')
    scale = positive_number(scale, 'scale')
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), float(angle), scale)
    cosine, sine = abs(matrix[0, 0]), abs(matrix[0, 1])
    new_width = max(1, int(np.ceil(width * cosine + height * sine - 1e-10)))
    new_height = max(1, int(np.ceil(height * cosine + width * sine - 1e-10)))
    matrix[:, 2] += [new_width / 2 - width / 2, new_height / 2 - height / 2]
    result = cv2.warpAffine(image, matrix, (new_width, new_height), flags=cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    return result, matrix


def project_xy(points: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    points, matrix = np.asarray(points, np.float64), np.asarray(matrix, np.float64)
    if points.ndim != 2 or points.shape[1] != 2 or matrix.shape != (2,3) or not np.isfinite(points).all() or not np.isfinite(matrix).all():
        raise ValueError('投影需要有限 N×2 坐标及 2×3 仿射矩阵')
    return points @ matrix[:, :2].T + matrix[:, 2]


def descriptor_matrix(value: np.ndarray) -> None:
    if not isinstance(value, np.ndarray) or value.ndim != 2 or value.shape[1] != 128 or value.dtype != np.float32 or not np.isfinite(value).all():
        raise ValueError('匹配描述子应为有限 float32 N×128')


def ratio_matches(query: np.ndarray, train: np.ndarray, threshold: float = 0.75) -> tuple[list, int]:
    descriptor_matrix(query)
    descriptor_matrix(train)
    threshold = positive_number(threshold, 'ratio_threshold')
    if threshold >= 1:
        raise ValueError('ratio_threshold 必须小于 1')
    if len(query) == 0 or len(train) < 2:
        return [], 0
    neighbors = cv2.BFMatcher(cv2.NORM_L2).knnMatch(query, train, k=2)
    pairs = [pair for pair in neighbors if len(pair) == 2]
    good = [pair[0] for pair in pairs if pair[0].distance < threshold * pair[1].distance]
    # All descriptors participate; only visualization is capped later.
    return sorted(good, key=lambda m: (m.distance, m.queryIdx, m.trainIdx)), len(pairs)


def match_statistics(source_points, target_points, matches, matrix, tolerance_px=3.0) -> tuple[dict, list[dict]]:
    tolerance = positive_number(tolerance_px, 'geometry_tolerance_px')
    rows = []
    if matches:
        xy = np.array([source_points[m.queryIdx].pt for m in matches])
        expected = project_xy(xy, matrix)
        actual = np.array([target_points[m.trainIdx].pt for m in matches])
        errors = np.linalg.norm(expected - actual, axis=1)
        rows = [{'query_index': int(m.queryIdx), 'train_index': int(m.trainIdx),
                 'distance_l2': float(m.distance), 'reprojection_error_px': float(error),
                 'geometry_consistent': bool(error <= tolerance)} for m, error in zip(matches, errors)]
    correct = sum(row['geometry_consistent'] for row in rows)
    return {'source_keypoints': len(source_points), 'target_keypoints': len(target_points),
            'ratio_passed': len(matches), 'ratio_passed_per_source': len(matches) / len(source_points) if source_points else 0.0,
            'geometry_consistent': correct,
            'geometry_consistent_per_source': correct / len(source_points) if source_points else 0.0,
            'geometry_consistent_per_match': correct / len(matches) if matches else None,
            'unique_train_indices': len({m.trainIdx for m in matches}),
            'median_reprojection_error_px': float(np.median([row['reprojection_error_px'] for row in rows])) if rows else None}, rows
