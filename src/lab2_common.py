"""Shared uint8 grayscale IO and figures for experiment two."""
from __future__ import annotations

import io
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from baseline_pipeline import read_image, to_gray
from common import INPUT_ROOT, atomic_write


def require_gray(image: np.ndarray) -> None:
    if image.dtype != np.uint8 or image.ndim != 2 or image.size == 0:
        raise ValueError("实验二要求非空单通道 uint8；uint16/float32 不隐式缩放")


def gray_input(path: Path) -> np.ndarray:
    image = read_image(path)
    if image.dtype != np.uint8:
        raise ValueError(f"实验二不支持该位深: {image.dtype}: {path}")
    gray, _ = to_gray(image)
    require_gray(gray)
    return gray


def output_folder(folder: Path, sources=()) -> None:
    resolved = folder.resolve()
    if resolved.is_relative_to(INPUT_ROOT.resolve()):
        raise ValueError("实验输出目录不能在原始输入目录内")
    if any(path.resolve().is_relative_to(resolved) for path in sources):
        raise ValueError("输出目录不能包含源图片")
    folder.mkdir(parents=True, exist_ok=True)


def save_png(path: Path, image: np.ndarray) -> None:
    require_gray(image)
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise OSError(f"编码失败: {path}")
    atomic_write(path, encoded.tobytes())
    saved = read_image(path)
    if saved.dtype != image.dtype or not np.array_equal(saved, image):
        raise OSError(f"保存后校验失败: {path}")


def save_figure(path: Path, figure) -> None:
    try:
        buffer = io.BytesIO()
        figure.savefig(buffer, format="png", dpi=150, bbox_inches="tight", facecolor="white")
        atomic_write(path, buffer.getvalue())
    finally:
        plt.close(figure)


def image_panel(path: Path, items: list[tuple[str, np.ndarray]], columns=3) -> None:
    rows = (len(items) + columns - 1) // columns
    figure, axes = plt.subplots(rows, columns, figsize=(4.5 * columns, 3.1 * rows), squeeze=False, layout="constrained")
    for axis, (title, image) in zip(axes.flat, items):
        axis.imshow(image, cmap="gray", vmin=0, vmax=255)
        axis.set_title(title, fontsize=11)
        axis.axis("off")
    for axis in list(axes.flat)[len(items):]:
        axis.axis("off")
    save_figure(path, figure)


def statistics(image: np.ndarray) -> dict:
    require_gray(image)
    counts = np.bincount(image.ravel(), minlength=256)
    p = counts[counts > 0] / image.size
    return {"shape": list(image.shape), "dtype": str(image.dtype), "min": int(image.min()), "max": int(image.max()),
            "mean": round(float(image.mean()), 4), "std": round(float(image.std()), 4),
            "entropy_bits": round(float(-np.sum(p * np.log2(p))), 4),
            "black_fraction": round(float(np.mean(image == 0)), 6),
            "white_fraction": round(float(np.mean(image == 255)), 6)}
