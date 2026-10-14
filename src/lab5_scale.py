"""PyrDown scale pyramid, signed adjacent-level approximation and Gaussian DoG."""
from __future__ import annotations

import cv2
import numpy as np

from feature import validate_gray, integer_parameter, select_points


def gaussian_pyramid(image: np.ndarray, levels=4) -> list[np.ndarray]:
    validate_gray(image)
    levels = integer_parameter(levels, "levels")
    if levels > 8:
        raise ValueError("本实现最多支持 8 层，避免无意义的重复 1×1 层")
    result = [image.copy()]
    for _ in range(levels - 1):
        result.append(cv2.pyrDown(result[-1], borderType=cv2.BORDER_REFLECT_101))
    return result


def adjacent_dog(fine: np.ndarray, coarse: np.ndarray) -> np.ndarray:
    validate_gray(fine)
    validate_gray(coarse)
    upsampled = cv2.resize(coarse.astype(np.float32), fine.shape[::-1], interpolation=cv2.INTER_LINEAR)
    return upsampled - fine.astype(np.float32)


def dog_displays(dog: np.ndarray) -> dict:
    if dog.ndim != 2 or dog.size == 0 or not np.isfinite(dog).all():
        raise ValueError("DoG 应为有限非空二维数组")
    peak = float(np.abs(dog).max())
    if peak == 0:
        return {"absolute": np.zeros(dog.shape, np.uint8), "signed": np.full(dog.shape, 128, np.uint8)}
    return {"absolute": np.clip(np.abs(dog) / peak * 255, 0, 255).astype(np.uint8),
            "signed": np.clip(128 + dog / peak * 127, 0, 255).astype(np.uint8)}


def dog_candidates(dog: np.ndarray, quality_level=0.1, min_distance=6.0, max_points=150) -> np.ndarray:
    return select_points(np.abs(dog).astype(np.float32), quality_level, min_distance, max_points)


def gaussian_dogs(image: np.ndarray, sigma=1.6, scale_ratio=2 ** (1 / 3)) -> tuple[list[np.ndarray], list[float]]:
    validate_gray(image)
    if isinstance(sigma, (str, bool)) or not np.isfinite(sigma) or sigma <= 0:
        raise ValueError("DoG sigma 必须为有限正数")
    if isinstance(scale_ratio, (str, bool)) or not np.isfinite(scale_ratio) or scale_ratio <= 1:
        raise ValueError("DoG scale_ratio 必须有限且大于 1")
    sigmas = [float(sigma * scale_ratio ** i) for i in range(6)]
    blurred = [cv2.GaussianBlur(image.astype(np.float32), (0, 0), value, borderType=cv2.BORDER_REFLECT_101) for value in sigmas]
    return [blurred[i + 1] - blurred[i] for i in range(5)], sigmas


def scale_extrema(dogs: list[np.ndarray], contrast_threshold=2.0) -> np.ndarray:
    if len(dogs) < 3 or any(d.shape != dogs[0].shape or d.ndim != 2 or not np.isfinite(d).all() for d in dogs):
        raise ValueError("尺度极值需要至少三张同尺寸有限二维 DoG")
    if isinstance(contrast_threshold, (str, bool)) or not np.isfinite(contrast_threshold) or contrast_threshold < 0:
        raise ValueError("contrast_threshold 必须有限非负")
    h, w = dogs[0].shape
    if min(h, w) < 3:
        return np.empty((0, 4), np.float64)
    rows = []
    for index in range(1, len(dogs) - 1):
        center = dogs[index][1:-1, 1:-1]
        maximum = np.ones(center.shape, bool)
        minimum = np.ones(center.shape, bool)
        for ds in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if ds == dy == dx == 0:
                        continue
                    neighbor = dogs[index + ds][1 + dy:h - 1 + dy, 1 + dx:w - 1 + dx]
                    maximum &= center > neighbor
                    minimum &= center < neighbor
        yy, xx = np.nonzero((maximum | minimum) & (np.abs(center) > contrast_threshold))
        rows.extend((int(x + 1), int(y + 1), index, float(center[y, x])) for y, x in zip(yy, xx))
    return np.asarray(rows, np.float64).reshape(-1, 4)
