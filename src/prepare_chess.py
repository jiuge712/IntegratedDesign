"""Draw the chessboard explicitly authorized by the user for experiment five."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import cv2
import numpy as np

from common import ROOT, INPUT_ROOT, sha256, timestamp, write_text


def chessboard(rows: int = 8, columns: int = 8, square_size: int = 40) -> np.ndarray:
    if any(isinstance(x, bool) or not isinstance(x, int) or x < 2 for x in (rows, columns, square_size)):
        raise ValueError("行数、列数、格子尺寸必须为不小于 2 的整数")
    yy, xx = np.indices((rows * square_size, columns * square_size))
    return (((yy // square_size + xx // square_size) % 2) * 255).astype(np.uint8)


def prepare(rows: int = 8, columns: int = 8, square_size: int = 40) -> dict:
    image = chessboard(rows, columns, square_size)
    path = INPUT_ROOT / "chess.png"
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise OSError("棋盘格编码失败")
    content = encoded.tobytes()
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError("chess.png 已存在且内容不同；保留你的图片，不自动覆盖")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(content)
    decoded = cv2.imdecode(np.frombuffer(path.read_bytes(), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if decoded is None or not np.array_equal(decoded, image):
        raise OSError("棋盘格回读校验失败")
    info = {"time": timestamp(), "source": "user_authorized_programmatic_chessboard",
            "authorization": "用户明确授权程序绘制标准棋盘格作为本次正式素材",
            "path": "data/input/chess.png", "rows": rows, "columns": columns,
            "square_size": square_size, "shape": list(image.shape), "dtype": str(image.dtype),
            "expected_internal_intersections": (rows - 1) * (columns - 1), "sha256": sha256(path)}
    write_text(ROOT / "evidence/chess_source.json", json.dumps(info, ensure_ascii=False, indent=2) + "\n")
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=8)
    parser.add_argument("--columns", type=int, default=8)
    parser.add_argument("--square-size", type=int, default=40)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.rows, args.columns, args.square_size), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, cv2.error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
