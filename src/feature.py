"""Harris/Shi-Tomasi/FAST detection with a stable integer (x,y) interface."""
from __future__ import annotations

import cv2
import numpy as np


def validate_gray(image: np.ndarray) -> None:
    if not isinstance(image, np.ndarray):
        raise TypeError("图像必须为 NumPy 数组")
    if image.size == 0:
        raise ValueError("空图不能进行角点检测")
    if image.ndim != 2 or image.dtype != np.uint8:
        raise ValueError("角点接口要求单通道 uint8，不隐式转换类型或颜色")


def integer_parameter(value, name: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < minimum:
        raise ValueError(f"{name} 必须为不小于 {minimum} 的整数")
    return int(value)


def harris_parameters(block_size=2, ksize=3, k=0.04) -> tuple[int, int, float]:
    block_size = integer_parameter(block_size, "block_size", 2)
    ksize = integer_parameter(ksize, "ksize", 3)
    if ksize not in (3, 5, 7):
        raise ValueError("Sobel ksize 需为 3、5 或 7")
    if isinstance(k, (str, bool)) or not np.isfinite(k) or not 0 < k < 0.25:
        raise ValueError("Harris k 必须有限且 0<k<0.25")
    return block_size, ksize, float(k)


def harris_response(image: np.ndarray, k=0.04, block_size=2, ksize=3) -> np.ndarray:
    validate_gray(image)
    block_size, ksize, k = harris_parameters(block_size, ksize, k)
    if min(image.shape) < 3:
        return np.zeros(image.shape, np.float32)
    return cv2.cornerHarris(image, block_size, ksize, k, borderType=cv2.BORDER_REFLECT_101)


def select_points(response: np.ndarray, quality_level=0.01, min_distance=10.0, max_points=500) -> np.ndarray:
    if response.ndim != 2 or response.size == 0 or not np.isfinite(response).all():
        raise ValueError("响应图必须为有限非空二维数组")
    if isinstance(quality_level, (str, bool)) or not np.isfinite(quality_level) or not 0 < quality_level <= 1:
        raise ValueError("quality_level 必须在 (0,1] 内")
    if isinstance(min_distance, (str, bool)) or not np.isfinite(min_distance) or min_distance < 0:
        raise ValueError("min_distance 必须有限非负")
    max_points = integer_parameter(max_points, "max_points")
    peak = float(response.max())
    if peak <= 0:
        return np.empty((0, 2), np.int32)
    local_max = cv2.dilate(response.astype(np.float32), np.ones((3, 3), np.uint8))
    yy, xx = np.nonzero((response > peak * quality_level) & (response >= local_max))
    order = np.lexsort((xx, yy, -response[yy, xx]))
    selected = []
    limit = float(min_distance) ** 2
    for index in order:
        point = np.array([xx[index], yy[index]], np.int32)
        if selected and np.any(np.sum((np.asarray(selected, dtype=np.float64) - point) ** 2, axis=1) < limit):
            continue
        selected.append(point)
        if len(selected) == max_points:
            break
    return np.asarray(selected, dtype=np.int32).reshape(-1, 2)


def harris_corners(img: np.ndarray, k=0.04, block_size=2, ksize=3,
                   quality_level=0.01, min_distance=10.0, max_points=500) -> np.ndarray:
    response = harris_response(img, k, block_size, ksize)
    return select_points(response, quality_level, min_distance, max_points)


def shi_tomasi_corners(image: np.ndarray, max_corners=100, quality_level=0.01, min_distance=10.0) -> np.ndarray:
    validate_gray(image)
    max_corners = integer_parameter(max_corners, "max_corners")
    # Reuse selection validation even for a constant/tiny input.
    select_points(np.zeros((1, 1), np.float32), quality_level, min_distance, max_corners)
    if min(image.shape) < 3:
        return np.empty((0, 2), np.int32)
    corners = cv2.goodFeaturesToTrack(image, max_corners, quality_level, min_distance, useHarrisDetector=False)
    if corners is None:
        return np.empty((0, 2), np.int32)
    points = np.rint(corners.reshape(-1, 2)).astype(np.int32)
    points[:, 0] = np.clip(points[:, 0], 0, image.shape[1] - 1)
    points[:, 1] = np.clip(points[:, 1], 0, image.shape[0] - 1)
    return points


def fast_corners(image: np.ndarray, threshold=20) -> np.ndarray:
    validate_gray(image)
    threshold = integer_parameter(threshold, "FAST threshold")
    detector = cv2.FastFeatureDetector_create(threshold=threshold, nonmaxSuppression=True)
    keypoints = detector.detect(image, None)
    return np.asarray([[int(round(point.pt[0])), int(round(point.pt[1]))] for point in keypoints], dtype=np.int32).reshape(-1, 2)


def manual_harris_response(image: np.ndarray, k=0.04, block_size=2, ksize=3) -> dict:
    validate_gray(image)
    block_size, ksize, k = harris_parameters(block_size, ksize, k)
    scale = 1.0 / (255 * block_size * (2 ** (ksize - 1)))
    gx = cv2.Sobel(image, cv2.CV_32F, 1, 0, ksize=ksize, scale=scale, borderType=cv2.BORDER_REFLECT_101)
    gy = cv2.Sobel(image, cv2.CV_32F, 0, 1, ksize=ksize, scale=scale, borderType=cv2.BORDER_REFLECT_101)
    def sum_window(values):
        return cv2.boxFilter(values, cv2.CV_32F, (block_size, block_size), normalize=False, borderType=cv2.BORDER_REFLECT_101)
    a, b, c = sum_window(gx * gx), sum_window(gx * gy), sum_window(gy * gy)
    trace = a + c
    determinant = a * c - b * b
    response = determinant - k * trace * trace
    discriminant = np.sqrt(np.maximum((a - c) ** 2 + 4 * b * b, 0))
    return {"response": response.astype(np.float32), "lambda1": (trace + discriminant) / 2,
            "lambda2": (trace - discriminant) / 2, "trace": trace, "determinant": determinant}
