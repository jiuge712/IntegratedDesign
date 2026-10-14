"""Record actual environment; fail if it is not a virtual environment."""
from __future__ import annotations
import argparse
import json
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
import platform
import subprocess
import sys

import cv2
import matplotlib
import numpy as np
import skimage

from common import ROOT, VERSION, timestamp, write_text


def environment() -> dict:
    try:
        pytest_version = version('pytest')
    except PackageNotFoundError:
        pytest_version = 'not installed'
    return {
        "recorded_at": timestamp(), "program_version": VERSION,
        "platform": platform.platform(), "machine": platform.machine(),
        "python": platform.python_version(), "python_executable": sys.executable,
        "in_virtual_environment": sys.prefix != sys.base_prefix,
        "opencv": cv2.__version__, "numpy": np.__version__, "matplotlib": matplotlib.__version__,
        "scikit_image": skimage.__version__,
        "pytest": pytest_version,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "environment.md")
    parser.add_argument("--freeze", type=Path, help="Write exact pip freeze dependencies")
    args = parser.parse_args()
    info = environment()
    if not info["in_virtual_environment"]:
        print("ERROR: 请使用独立虚拟环境 / use the project virtual environment", file=sys.stderr)
        return 1
    try:
        lines = ["# 实验项目环境与依赖记录", "", "由 version_check.py 自动采集当前环境。时间采用北京时间 UTC+08:00。", "", "| 项目 | 实际值 |", "| --- | --- |"]
        lines.extend(f"| {key} | {value} |" for key, value in info.items())
        lines.extend(["", "耗时仅适用于记录的平台；跨机器复现时以重新采集的记录为准。",
                      "", "安装与故障处理过程见 installation_notes.md。", ""])
        write_text(args.output, "\n".join(lines))
        if args.freeze:
            freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True, check=True)
            write_text(args.freeze, freeze.stdout)
        print(json.dumps(info, ensure_ascii=False))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"ERROR: 环境记录失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
