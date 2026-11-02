"""Right-to-left RANSAC, bounded full-canvas warping and mask-based feathering."""
from __future__ import annotations
import cv2
import numpy as np
from features import extract_sift
from matching import knn_matches, symmetric_ratio, positive_integer
from lab6_geometry import positive_number


def points_array(value):
    points = np.asarray(value, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all():
        raise ValueError('点坐标需为有限 N×2 数组')
    return points


def valid_homography(value):
    H = np.array(value, dtype=np.float64, copy=True)
    if H.shape != (3, 3) or not np.isfinite(H).all():
        raise ValueError('H 必须为有限3×3矩阵')
    norm = np.linalg.norm(H)
    if norm == 0 or np.linalg.cond(H) > 1e12:
        raise ValueError('H 奇异或病态，不能可靠投影')
    return H / (H[2, 2] if abs(H[2, 2]) > 1e-12 * norm else norm)


def project_points(points, H):
    points, H = points_array(points), valid_homography(H)
    homogeneous = np.column_stack((points, np.ones(len(points)))) @ H.T
    denominator = homogeneous[:, 2]
    if np.any(np.abs(denominator) < 1e-10):
        raise ValueError('投影点落在无穷远，不能分配画布')
    result = homogeneous[:, :2] / denominator[:, None]
    if not np.isfinite(result).all():
        raise ValueError('投影产生非有限坐标')
    return result


def estimate_homography(right, left, threshold=5.0, confidence=.995, max_iters=10000, seed=8):
    """Return OpenCV's H, boolean inlier mask and forward reprojection errors."""
    right, left = points_array(right), points_array(left)
    if right.shape != left.shape or len(right) < 4:
        raise ValueError('单应估计至少需4对数量一致的点')
    for points in (right, left):
        if len(np.unique(points, axis=0)) < 4 or np.linalg.matrix_rank(points - points.mean(axis=0)) < 2:
            raise ValueError('单应估计拒绝重复或共线的退化点集')
    threshold = positive_number(threshold, 'ransac_threshold')
    confidence = positive_number(confidence, 'confidence')
    if confidence >= 1:
        raise ValueError('confidence必须小于1')
    max_iters = positive_integer(max_iters, 'max_iters')
    seed = positive_integer(seed, 'seed', 0)
    if seed > 2**31 - 1:
        raise ValueError('seed超出OpenCV整数范围')
    cv2.setRNGSeed(seed)
    H, mask = cv2.findHomography(right, left, cv2.RANSAC, threshold,
                                maxIters=max_iters, confidence=confidence)
    if H is None or mask is None or mask.size != len(right):
        raise ValueError('RANSAC未找到有效单应矩阵')
    H = valid_homography(H)
    mask = mask.ravel().astype(bool)
    if mask.sum() < 4:
        raise ValueError('RANSAC有效内点不足4对')
    errors = np.linalg.norm(project_points(right, H) - left, axis=1)
    return H, mask, errors


def match_and_estimate(image1, image2, ratio=.75, sift=None, threshold=5., confidence=.995, max_iters=10000, seed=8):
    kp1, desc1 = extract_sift(image1, sift)
    kp2, desc2 = extract_sift(image2, sift)
    forward, reverse = knn_matches(desc1, desc2), knn_matches(desc2, desc1)
    matches = symmetric_ratio(forward, reverse, ratio)
    left = np.float64([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 2)
    right = np.float64([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 2)
    H, mask, errors = estimate_homography(right, left, threshold, confidence, max_iters, seed)
    return dict(kp1=kp1, kp2=kp2, desc1=desc1, desc2=desc2, forward=forward, reverse=reverse,
                matches=matches, left=left, right=right, H=H, inliers=mask, errors=errors)


def image_shape(shape):
    if len(shape) < 2:
        raise ValueError('图像尺寸需有高和宽')
    h, w = [positive_integer(value, '图像尺寸') for value in shape[:2]]
    if max(h, w) >= 32767:
        raise ValueError('OpenCV透视变换的单边需小于32767')
    return h, w


def corners(shape):
    h, w = image_shape(shape)
    return np.float64([[0, 0], [w-1, 0], [w-1, h-1], [0, h-1]])


def canvas_geometry(shape1, shape2, H, max_pixels=20_000_000):
    H = valid_homography(H)
    first, second = corners(shape1), corners(shape2)
    denominator = np.column_stack((second, np.ones(4))) @ H[2]
    if denominator.min() <= 0 <= denominator.max() or np.min(np.abs(denominator)) < 1e-10:
        raise ValueError('投影无穷远线穿过右图，不能可靠拼接')
    projected = project_points(second, H)
    all_points = np.vstack((first, projected))
    lower = np.floor(all_points.min(axis=0))
    upper = np.ceil(all_points.max(axis=0)) + 1
    extent = upper - lower
    max_pixels = positive_integer(max_pixels, 'max_canvas_pixels')
    if np.any(extent < 1) or np.any(extent >= 32767) or np.prod(extent) > max_pixels:
        raise ValueError('完整画布超过资源上限，请减小工作尺寸或检查图片/模型')
    width, height = map(int, extent)
    T = np.array([[1., 0, -lower[0]], [0, 1., -lower[1]], [0, 0, 1.]])
    return dict(size=(width, height), origin=lower.tolist(), translation=T,
                left_corners=first, right_corners_in_left=projected)


def blend_with_alpha(left, right, alpha):
    result = np.empty_like(left)
    # Limit temporary float allocations even for a large legal canvas.
    for y in range(0, len(left), 128):
        weight = alpha[y:y+128, :, None]
        value = left[y:y+128].astype(np.float32)*weight + right[y:y+128].astype(np.float32)*(1-weight)
        result[y:y+128] = np.rint(value).clip(0, 255).astype(np.uint8)
    return result


def stitch_pair(image1, image2, H, max_pixels=20_000_000):
    for image in (image1, image2):
        if not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
            raise ValueError('拼接输入必须为uint8 BGR图像')
    geometry = canvas_geometry(image1.shape, image2.shape, H, max_pixels)
    T, size = geometry['translation'], geometry['size']
    transforms = (T, T @ valid_homography(H))
    warped, masks = [], []
    for image, transform in zip((image1, image2), transforms):
        warped.append(cv2.warpPerspective(image, transform, size, flags=cv2.INTER_LINEAR))
        # Validity comes from a warped mask; a genuine black pixel remains valid.
        masks.append(cv2.warpPerspective(np.full(image.shape[:2], 255, np.uint8), transform,
                                        size, flags=cv2.INTER_NEAREST) > 0)
        warped[-1][~masks[-1]] = 0
    left_mask, right_mask = masks
    overlap = left_mask & right_mask
    if not overlap.any():
        raise ValueError('两图没有有效重叠，不能生成本实验的拼接结果')
    distances = []
    for mask in masks:
        padded = np.pad(mask.astype(np.uint8), 1, mode='constant')
        distances.append(cv2.distanceTransform(padded, cv2.DIST_L2, 3)[1:-1, 1:-1])
    alpha = np.divide(distances[0], distances[0]+distances[1],
                      out=np.zeros_like(distances[0]), where=(distances[0]+distances[1]) > 0)
    alpha[left_mask & ~right_mask] = 1
    hard = warped[1].copy()
    hard[left_mask] = warped[0][left_mask]
    diagnostic_alpha = np.where(overlap, .5, np.where(left_mask, 1., 0.)).astype(np.float32)
    return dict(geometry=geometry, warped_right=warped[1], left_mask=left_mask, right_mask=right_mask,
                overlap=overlap, alpha=alpha, hard=hard,
                feather=blend_with_alpha(*warped, alpha),
                overlay=blend_with_alpha(*warped, diagnostic_alpha))
