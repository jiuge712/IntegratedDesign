"""Read -> inspect -> grayscale -> lossless PNG, with Unicode paths."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

import cv2
import numpy as np

from common import VERSION, atomic_write, check_destination, sha256, timestamp


def read_image(path: Path) -> np.ndarray:
    if not path.is_file():
        raise FileNotFoundError(f"读取失败，文件不存在 / input file not found: {path}")
    # Read bytes through pathlib so OpenCV's filename API cannot break Chinese paths.
    encoded = np.frombuffer(path.read_bytes(), dtype=np.uint8)
    if encoded.size == 0:
        raise ValueError(f"读取失败，文件为空 / empty image: {path}")
    image = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
    if image is None or image.size == 0:
        raise ValueError(f"读取失败，文件损坏或格式不支持 / cannot decode image: {path}")
    validate_image(image)
    return image


def validate_image(image: np.ndarray) -> None:
    if image.dtype not in (np.dtype("uint8"), np.dtype("uint16")):
        raise ValueError(f"不支持的像素类型 / unsupported dtype: {image.dtype}; use uint8/uint16")
    if image.size == 0 or not (
        image.ndim == 2 or (image.ndim == 3 and image.shape[2] in (3, 4))
    ):
        raise ValueError(f"不支持的图像形状 / unsupported shape: {image.shape}")


def attributes(image: np.ndarray) -> dict:
    validate_image(image)
    channels = 1 if image.ndim == 2 else int(image.shape[2])
    return {
        "shape": list(image.shape), "dtype": str(image.dtype), "ndim": image.ndim,
        "channels": channels, "channel_order": {1: "GRAY", 3: "BGR", 4: "BGRA"}[channels],
        "min": int(image.min()), "max": int(image.max()),
    }


def to_gray(image: np.ndarray) -> tuple[np.ndarray, str]:
    validate_image(image)
    if image.ndim == 2:
        return image, "not_present"
    # Lab handout convention: ignore alpha, do not composite onto a background.
    gray = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
    return gray, "discarded_without_compositing" if image.shape[2] == 4 else "not_present"


def process(input_path: Path, output_path: Path) -> dict:
    start = perf_counter()
    destination = check_destination(output_path, input_path)
    if destination.suffix.lower() != ".png":
        raise ValueError("输出必须为 .png，保证无损且保留位深 / output must be .png")
    image = read_image(input_path)
    gray, alpha_policy = to_gray(image)
    ok, encoded = cv2.imencode(".png", gray)
    if not ok:
        raise OSError(f"保存失败，PNG编码失败 / PNG encoding failed: {output_path}")
    atomic_write(destination, encoded.tobytes(), input_path)
    elapsed_ms = (perf_counter() - start) * 1000
    # Decode the saved file as an independent check of dimensions, depth and pixels.
    saved = read_image(destination)
    if not np.array_equal(saved, gray) or saved.dtype != gray.dtype:
        raise OSError(f"保存失败，输出校验不一致 / output verification failed: {output_path}")
    return {
        "status": "SUCCESS", "time": timestamp(), "program_version": VERSION,
        "input": str(input_path.resolve()), "output": str(destination),
        "input_info": attributes(image), "output_info": attributes(saved),
        "alpha_policy": alpha_policy, "elapsed_ms": round(elapsed_ms, 3),
        "timing_scope": "read, inspect, convert, encode, write; excludes interpreter startup and verification",
        "input_sha256": sha256(input_path), "output_sha256": sha256(destination),
        "output_bytes": destination.stat().st_size,
        "versions": {"opencv": cv2.__version__, "numpy": np.__version__},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Original image (never modified)")
    parser.add_argument("--output", required=True, type=Path, help="Grayscale PNG destination")
    parser.add_argument("--record", type=Path, help="Append SUCCESS/ERROR JSON line to this log")
    args = parser.parse_args(argv)
    record_path = None
    try:
        if args.record:
            candidate = check_destination(args.record, args.input)
            if candidate == args.output.resolve() or (
                candidate.exists() and args.output.exists() and candidate.samefile(args.output)
            ):
                raise ValueError("日志路径不能与输出图片相同 / log and image paths must differ")
            record_path = candidate
        info = process(args.input, args.output)
        exit_code = 0
    except (OSError, ValueError, cv2.error) as exc:
        info = {
            "status": "ERROR", "time": timestamp(), "program_version": VERSION,
            "input": str(args.input.resolve()), "output": str(args.output.resolve()),
            "error": str(exc), "error_type": type(exc).__name__,
        }
        exit_code = 1
    if record_path is not None:
        try:
            record_path.parent.mkdir(parents=True, exist_ok=True)
            with record_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(info, ensure_ascii=False) + "\n")
        except OSError as exc:
            info["status"] = "ERROR"
            info["record_error"] = f"日志保存失败 / log write failed: {exc}"
            exit_code = 1
    print(json.dumps(info, ensure_ascii=False), file=sys.stderr if exit_code else sys.stdout)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
