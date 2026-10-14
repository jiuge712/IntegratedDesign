"""Compare wrapping, saturation, blending, subtraction, multiplication and division."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import cv2
import numpy as np
from lab2_common import gray_input, image_panel, output_folder, require_gray, save_png


def arithmetic(a: np.ndarray, b: np.ndarray, weight=0.6) -> dict[str, np.ndarray]:
    require_gray(a)
    require_gray(b)
    if a.shape != b.shape:
        raise ValueError(f"两图尺寸不同: {a.shape} vs {b.shape}；请先明确对齐，不自动拉伸")
    if not np.isfinite(weight) or not 0 <= weight <= 1:
        raise ValueError("混合权重必须在 [0,1] 内")
    return {"a": a, "b": b, "add_numpy": np.add(a, b), "add_opencv": cv2.add(a, b),
            "blend": cv2.addWeighted(a, weight, b, 1-weight, 0),
            "subtract_numpy": np.subtract(a, b), "subtract_opencv": cv2.subtract(a, b),
            "absdiff": cv2.absdiff(a, b), "multiply": cv2.multiply(a, b, scale=1/255),
            "divide": cv2.divide(a, b, scale=128)}


def write_arithmetic(folder, results, weight=0.6):
    for name, image in results.items():
        save_png(folder / f"l2_{name}.png", image)
    titles = {"a": "A: dark", "b": "B: normal", "add_numpy": "NumPy A+B: wrap mod 256",
              "add_opencv": "cv2.add: saturate at 255", "blend": f"Blend: {weight}*A + {1-weight:.2f}*B",
              "subtract_numpy": "NumPy A-B: wrap mod 256", "subtract_opencv": "cv2.subtract: clip at 0",
              "absdiff": "Absolute difference", "multiply": "Multiply: A*B/255", "divide": "Divide: 128*A/B; B=0 -> 0"}
    image_panel(folder / "l2_arith_compare.png", [(titles[k], results[k]) for k in ("a", "b", "add_numpy", "add_opencv", "blend", "subtract_opencv")], 3)
    image_panel(folder / "l2_arith_extra.png", [(titles[k], results[k]) for k in ("subtract_numpy", "absdiff", "multiply", "divide")], 2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a", required=True, type=Path)
    parser.add_argument("--b", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--weight", type=float, default=0.6)
    args = parser.parse_args()
    try:
        results = arithmetic(gray_input(args.a), gray_input(args.b), args.weight)
        output_folder(args.output_dir, [args.a, args.b])
        write_arithmetic(args.output_dir, results, args.weight)
        print("SUCCESS")
        return 0
    except (OSError, ValueError, cv2.error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
