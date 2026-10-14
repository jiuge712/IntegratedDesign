"""Manual PSNR and explicit-range scikit-image SSIM."""
from __future__ import annotations
import math
import cv2
import numpy as np
from skimage.metrics import structural_similarity
from lab3_filter import validate_image


def matching(a,b):
    validate_image(a)
    validate_image(b)
    if a.shape != b.shape:
        raise ValueError(f"评分输入尺寸不一致: {a.shape} vs {b.shape}")


def psnr(a: np.ndarray,b: np.ndarray) -> float:
    matching(a,b)
    mse=float(np.mean((a.astype(np.float64)-b.astype(np.float64))**2))
    return float("inf") if mse == 0 else 10*math.log10(255.0**2/mse)


def ssim(a: np.ndarray,b: np.ndarray) -> float:
    matching(a,b)
    if min(a.shape[:2]) < 7:
        raise ValueError("SSIM 默认 7×7 窗口要求宽高均至少为 7；不自动缩放")
    return float(structural_similarity(a,b,data_range=255,win_size=7,channel_axis=-1 if a.ndim==3 else None))


def quality(reference: np.ndarray,candidate: np.ndarray) -> dict:
    score=psnr(reference,candidate)
    return {"psnr_db": None if math.isinf(score) else score, "psnr_infinite":math.isinf(score),
            "ssim":ssim(reference,candidate),
            "mse":float(np.mean((reference.astype(np.float64)-candidate.astype(np.float64))**2))}


def gradient_mean(image: np.ndarray) -> float:
    validate_image(image)
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY) if image.ndim==3 else image
    dx=cv2.Sobel(gray,cv2.CV_64F,1,0,ksize=3,borderType=cv2.BORDER_REFLECT_101)
    dy=cv2.Sobel(gray,cv2.CV_64F,0,1,ksize=3,borderType=cv2.BORDER_REFLECT_101)
    return float(np.hypot(dx,dy).mean())
