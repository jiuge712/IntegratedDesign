"""Histogram and independently written CDF equalization."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import cv2
import numpy as np
from lab2_common import gray_input, output_folder, require_gray, save_figure, save_png
import matplotlib.pyplot as plt


def histogram(image: np.ndarray) -> np.ndarray:
    require_gray(image)
    return cv2.calcHist([image], [0], None, [256], [0, 256]).ravel()


def manual_equalize(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    require_gray(image)
    counts = np.bincount(image.ravel(), minlength=256)
    cdf = counts.cumsum()
    first = np.flatnonzero(counts)[0]
    cdf_min = int(cdf[first])
    if cdf_min == image.size:
        # OpenCV preserves constant images; avoid division by zero.
        return image.copy(), np.arange(256, dtype=np.uint8)
    scale = np.float32(255.0 / (image.size - cdf_min))
    lut = np.clip(np.rint((cdf - cdf_min).astype(np.float32) * scale), 0, 255).astype(np.uint8)
    return lut[image], lut


def direct_cdf_equalize(image: np.ndarray) -> np.ndarray:
    require_gray(image)
    cdf = np.bincount(image.ravel(), minlength=256).cumsum() / image.size
    return np.clip(np.rint(255 * cdf), 0, 255).astype(np.uint8)[image]


def equalization(image: np.ndarray) -> dict:
    manual, lut = manual_equalize(image)
    api = cv2.equalizeHist(image)
    diff = np.abs(manual.astype(np.int16) - api.astype(np.int16)).astype(np.uint8)
    return {"original": image, "manual": manual, "api": api, "difference": diff,
            "direct_cdf": direct_cdf_equalize(image), "lut": lut,
            "metrics": {"max_difference": int(diff.max()), "different_pixels": int(np.count_nonzero(diff)),
                        "different_fraction": float(np.mean(diff != 0)), "mae": float(diff.mean())}}


def write_histograms(folder, samples: dict[str, np.ndarray]):
    figure, axes = plt.subplots(2, len(samples), figsize=(4.6 * len(samples), 6), squeeze=False, layout="constrained")
    for column, (name, image) in enumerate(samples.items()):
        axes[0, column].imshow(image, cmap="gray", vmin=0, vmax=255)
        axes[0, column].set_title(f"{name}; mean={image.mean():.1f}")
        axes[0, column].axis("off")
        axes[1, column].bar(np.arange(256), histogram(image), width=1, color="#4169a1")
        axes[1, column].set(xlim=(0, 255), xlabel="Gray level", ylabel="Pixel count")
    save_figure(folder / "l2_hist_compare.png", figure)


def write_equalization(folder, samples: dict[str, dict]):
    figure, axes = plt.subplots(2 * len(samples), 3, figsize=(14, 6 * len(samples)), squeeze=False, layout="constrained")
    for index, (name, result) in enumerate(samples.items()):
        for column, key in enumerate(("original", "manual", "api")):
            image = result[key]
            save_png(folder / f"l2_eq_{name}_{key}.png", image)
            axes[2*index, column].imshow(image, cmap="gray", vmin=0, vmax=255)
            axes[2*index, column].set_title(f"{name}: {key}; std={image.std():.1f}")
            axes[2*index, column].axis("off")
            axes[2*index+1, column].bar(np.arange(256), histogram(image), width=1, color="#4169a1")
            axes[2*index+1, column].set(xlim=(0, 255), xlabel="Gray level", ylabel="Pixel count")
        save_png(folder / f"l2_eq_{name}_difference.png", result["difference"])
        save_png(folder / f"l2_eq_{name}_direct_cdf.png", result["direct_cdf"])
    save_figure(folder / "l2_eq_compare.png", figure)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        image = gray_input(args.input)
        result = equalization(image)
        output_folder(args.output_dir, [args.input])
        write_histograms(args.output_dir, {"Input": image})
        write_equalization(args.output_dir, {"input": result})
        print(f"SUCCESS {result['metrics']}")
        return 0
    except (OSError, ValueError, cv2.error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
