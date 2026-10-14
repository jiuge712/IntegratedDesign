"""Linear and reciprocal-gamma grayscale transforms (experiment two)."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import numpy as np
from lab2_common import gray_input, image_panel, output_folder, require_gray, save_png


def linear_transform(image: np.ndarray, alpha=1.5, beta=30.0) -> np.ndarray:
    require_gray(image)
    if not np.isfinite([alpha, beta]).all():
        raise ValueError("alpha 与 beta 必须为有限数值")
    return np.clip(alpha * image.astype(np.float64) + beta, 0, 255).astype(np.uint8)


def gamma_transform(image: np.ndarray, gamma=2.2) -> np.ndarray:
    require_gray(image)
    if not np.isfinite(gamma) or gamma <= 0:
        raise ValueError("gamma 必须是有限正数")
    # The handout uses gamma as the denominator of the exponent.
    return np.clip(255.0 * (image.astype(np.float64) / 255.0) ** (1.0 / gamma), 0, 255).astype(np.uint8)


def transform_results(image, alpha=1.5, beta=30.0, gamma_bright=2.2, gamma_dark=0.5):
    return {"original": image, "linear": linear_transform(image, alpha, beta),
            "gamma_bright": gamma_transform(image, gamma_bright), "gamma_dark": gamma_transform(image, gamma_dark)}


def write_transform(folder, results, alpha=1.5, beta=30.0, gamma_bright=2.2, gamma_dark=0.5):
    for name, image in results.items():
        save_png(folder / f"l2_{name}.png", image)
    image_panel(folder / "l2_transform_compare.png", [("Dark input", results["original"]),
        (f"Linear: {alpha}*r + {beta}", results["linear"]),
        (f"Gamma={gamma_bright}; exponent=1/gamma", results["gamma_bright"])], 3)
    image_panel(folder / "l2_gamma_compare.png", [("Dark input", results["original"]),
        (f"Gamma={gamma_bright} (brighten)", results["gamma_bright"]),
        (f"Gamma={gamma_dark} (darken)", results["gamma_dark"])], 3)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--alpha", type=float, default=1.5)
    parser.add_argument("--beta", type=float, default=30)
    args = parser.parse_args()
    try:
        image = gray_input(args.input)
        results = transform_results(image, args.alpha, args.beta)
        output_folder(args.output_dir, [args.input])
        write_transform(args.output_dir, results, args.alpha, args.beta)
        print("SUCCESS")
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
