"""Shared path, version and evidence conventions for completed experiments."""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "5.0.0"
INPUT_ROOT = ROOT / "data" / "input"


def timestamp() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256")
    return digest.hexdigest()


def check_destination(path: Path, source: Path | None = None) -> Path:
    resolved = path.resolve()
    if resolved.is_relative_to(INPUT_ROOT.resolve()):
        raise ValueError(f"原始数据目录禁止写入 / input directory is read-only: {path}")
    if source is not None:
        if resolved == source.resolve() or (
            resolved.exists() and source.exists() and resolved.samefile(source)
        ):
            raise ValueError(f"输出不能覆盖输入 / output would overwrite input: {path}")
    if resolved.exists() and not resolved.is_file():
        raise ValueError(f"输出路径不是文件 / destination is not a file: {path}")
    return resolved


def atomic_write(path: Path, content: bytes, source: Path | None = None) -> None:
    target = check_destination(path, source)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Encode first, then replace the destination only after the write succeeds.
    fd, temporary = tempfile.mkstemp(prefix=".lab1_", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_text(path: Path, content: str) -> None:
    atomic_write(path, content.encode("utf-8"))
