"""Reusable uint8 SIFT extraction; descriptors always have shape (N,128)."""
from __future__ import annotations

import cv2
import numpy as np

SIFT_DEFAULTS = {
    'nfeatures': 0, 'nOctaveLayers': 3, 'contrastThreshold': 0.04,
    'edgeThreshold': 10.0, 'sigma': 1.6, 'enable_precise_upscale': False,
}


def sift_config(cfg: dict | None = None) -> dict:
    if cfg is not None and not isinstance(cfg, dict):
        raise TypeError('SIFT cfg 必须为字典或 None')
    cfg = {} if cfg is None else cfg
    if set(cfg) - set(SIFT_DEFAULTS):
        raise ValueError('SIFT 配置包含未知字段')
    result = {**SIFT_DEFAULTS, **cfg}
    for key, minimum in (('nfeatures', 0), ('nOctaveLayers', 1)):
        value = result[key]
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < minimum:
            raise ValueError(f'{key} 必须为不小于 {minimum} 的整数')
        result[key] = int(value)
    for key in ('contrastThreshold', 'edgeThreshold', 'sigma'):
        value = result[key]
        if isinstance(value, (str, bool)) or not np.isscalar(value) or not np.isfinite(value) or value <= 0:
            raise ValueError(f'{key} 必须为有限正数')
        result[key] = float(value)
    if not isinstance(result['enable_precise_upscale'], bool):
        raise ValueError('enable_precise_upscale 必须为 bool')
    return result


def extract_sift(img: np.ndarray, cfg: dict | None = None) -> tuple[list, np.ndarray]:
    """Accept gray/BGR/BGRA uint8, ignore alpha, return keypoints and float32 rows."""
    if not isinstance(img, np.ndarray):
        raise TypeError('SIFT 图像必须为 NumPy 数组')
    if img.size == 0 or img.dtype != np.uint8:
        raise ValueError('SIFT 图像必须非空且为 uint8')
    if img.ndim == 2:
        gray = img
    elif img.ndim == 3 and img.shape[2] in (3, 4):
        gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
    else:
        raise ValueError('SIFT 只支持灰度/BGR/BGRA 图像')
    parameters = sift_config(cfg)
    if not hasattr(cv2, 'SIFT_create'):
        raise RuntimeError('当前 OpenCV 未提供 SIFT_create，请使用支持 SIFT 的主包')
    if min(gray.shape) < 8:
        return [], np.empty((0, 128), np.float32)
    points, descriptors = cv2.SIFT_create(**parameters).detectAndCompute(gray, None)
    points = list(points)
    if descriptors is None:
        descriptors = np.empty((0, 128), np.float32)
    if descriptors.shape != (len(points), 128) or descriptors.dtype != np.float32 or not np.isfinite(descriptors).all():
        raise RuntimeError('SIFT 描述子类型、维度或有限性异常')
    return points, descriptors


def keypoint_records(points: list) -> list[dict]:
    return [{'x': float(p.pt[0]), 'y': float(p.pt[1]), 'size': float(p.size),
             'angle': float(p.angle), 'response': float(p.response),
             'octave_packed': int(p.octave), 'class_id': int(p.class_id)} for p in points]
