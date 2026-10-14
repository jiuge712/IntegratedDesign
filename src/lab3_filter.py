"""Spatial denoising and a strict uint8 BGR preprocessing interface."""
from __future__ import annotations

import cv2
import numpy as np


def validate_image(image: np.ndarray) -> None:
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.size == 0:
        raise ValueError("实验三需要非空 uint8 NumPy 图像")
    if not (image.ndim == 2 or (image.ndim == 3 and image.shape[2] == 3)):
        raise ValueError(f"实验三仅接受灰度或三通道 BGR: {image.shape}")


def positive(value, name: str, allow_zero=False) -> float:
    if isinstance(value, (bool, str)):
        raise ValueError(f"{name} 必须为有限数值")
    number = float(value)
    if not np.isfinite(number) or number < 0 or (not allow_zero and number == 0):
        raise ValueError(f"{name} 必须为有限{'非负' if allow_zero else '正'}数")
    return number


def odd_kernel(value, name="kernel_size") -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < 3 or value % 2 == 0:
        raise ValueError(f"{name} 必须为不小于 3 的奇整数")
    return int(value)


def gaussian_noise(image: np.ndarray, sigma=25.0, seed=0) -> np.ndarray:
    validate_image(image)
    sigma = positive(sigma, "gaussian_noise_sigma", allow_zero=True)
    rng = np.random.default_rng(seed)
    return np.clip(image.astype(np.float64) + rng.normal(0, sigma, image.shape), 0, 255).astype(np.uint8)


def salt_pepper_noise(image: np.ndarray, probability=0.1, seed=1) -> tuple[np.ndarray, dict]:
    validate_image(image)
    probability = positive(probability, "salt_pepper_probability", allow_zero=True)
    if probability > 1:
        raise ValueError("salt_pepper_probability 不能超过 1")
    mask = np.random.default_rng(seed).random(image.shape[:2])
    pepper = mask < probability/2
    salt = mask > 1-probability/2
    result = image.copy()
    result[pepper] = 0
    result[salt] = 255
    return result, {"pepper_selected": int(pepper.sum()), "salt_selected": int(salt.sum()),
                    "selected_fraction": float(np.mean(pepper | salt))}


def filter_image(image: np.ndarray, method="gaussian", kernel_size=5, gaussian_sigma=1.5,
                 bilateral_d=7, sigma_color=50.0, sigma_space=5.0) -> np.ndarray:
    validate_image(image)
    k = odd_kernel(kernel_size)
    if method == "none":
        return image.copy()
    if method == "mean":
        return cv2.blur(image, (k, k), borderType=cv2.BORDER_REFLECT_101)
    if method == "gaussian":
        sigma = positive(gaussian_sigma, "gaussian_sigma")
        # Match the handout: auto-selected Gaussian support at sigma=1.5.
        return cv2.GaussianBlur(image, (0, 0), sigmaX=sigma, sigmaY=sigma, borderType=cv2.BORDER_REFLECT_101)
    if method == "median":
        return cv2.medianBlur(image, k)
    if method == "bilateral":
        d = odd_kernel(bilateral_d, "bilateral_d")
        return cv2.bilateralFilter(image, d, positive(sigma_color,"sigma_color"),
                                  positive(sigma_space,"sigma_space"), borderType=cv2.BORDER_REFLECT_101)
    raise ValueError(f"未知滤波方法: {method}")


def sharpen_image(image: np.ndarray, method="usm", laplacian_amount=0.8, usm_amount=0.6, usm_sigma=2.0) -> np.ndarray:
    validate_image(image)
    if method == "none":
        return image.copy()
    if method == "laplacian":
        amount = positive(laplacian_amount,"laplacian_amount",allow_zero=True)
        lap = cv2.Laplacian(image,cv2.CV_64F,ksize=1,borderType=cv2.BORDER_REFLECT_101)
        return np.clip(image.astype(np.float64)-amount*lap,0,255).astype(np.uint8)
    if method == "usm":
        amount = positive(usm_amount,"usm_amount",allow_zero=True)
        sigma = positive(usm_sigma,"usm_sigma")
        blurred = cv2.GaussianBlur(image,(0,0),sigma,borderType=cv2.BORDER_REFLECT_101)
        return cv2.addWeighted(image,1+amount,blurred,-amount,0)
    raise ValueError(f"未知锐化方法: {method}")


def preprocess(img_bgr: np.ndarray, cfg: dict) -> np.ndarray:
    """Return a fresh, same-size uint8 BGR array; do not mutate or write inputs."""
    validate_image(img_bgr)
    if img_bgr.ndim != 3 or img_bgr.shape[2] != 3:
        raise ValueError("preprocess 接口要求 shape=(H,W,3) 的 BGR 输入")
    if not isinstance(cfg,dict):
        raise ValueError("cfg 必须为字典")
    allowed={"filter","kernel_size","gaussian_sigma","bilateral_d","sigma_color","sigma_space",
             "sharpen","laplacian_amount","usm_amount","usm_sigma"}
    if set(cfg)-allowed:
        raise ValueError(f"未知配置项: {sorted(set(cfg)-allowed)}")
    filtered = filter_image(img_bgr,**{key:cfg[key] for key in ("kernel_size","gaussian_sigma","bilateral_d","sigma_color","sigma_space") if key in cfg}, method=cfg.get("filter","gaussian"))
    result = sharpen_image(filtered,**{key:cfg[key] for key in ("laplacian_amount","usm_amount","usm_sigma") if key in cfg},method=cfg.get("sharpen","usm"))
    if result.shape != img_bgr.shape or result.dtype != np.uint8:
        raise ValueError("预处理输出不符合接口约定")
    return result
