"""Prepare lab-one variants from an explicitly supplied image; preserve originals."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import uuid

import cv2
import numpy as np

from baseline_pipeline import attributes, read_image
from common import INPUT_ROOT, ROOT, sha256, timestamp, write_text


def project_path(path: Path) -> str:
    resolved = path.resolve()
    return resolved.relative_to(ROOT).as_posix() if resolved.is_relative_to(ROOT) else resolved.as_posix()


def prepare(source: Path, black: Path, white: Path) -> dict:
    original_paths = {"source": source.resolve(), "black": black.resolve(), "white": white.resolve()}
    images = {key: read_image(path) for key, path in original_paths.items()}
    image = images["source"]
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
        raise ValueError("源图需要 uint8 三通道彩色 PNG/JPEG")
    if not np.all(images["black"] == 0):
        raise ValueError("用户提供的 black 图片不是纯黑")
    if not np.all(images["white"] == np.iinfo(images["white"].dtype).max):
        raise ValueError("用户提供的 white 图片不是纯白")
    before = {key: sha256(path) for key, path in original_paths.items()}
    batch = "prepared_" + timestamp().replace(":", "-") + "_" + uuid.uuid4().hex[:6]
    destination = INPUT_ROOT / batch
    destination.mkdir(parents=True, exist_ok=False)

    def save(name: str, pixels: np.ndarray) -> Path:
        path = destination / name
        if path.resolve().parent != destination.resolve() or path.resolve() in original_paths.values():
            raise ValueError("派生图片路径超出本次新建目录")
        ok, encoded = cv2.imencode(".png", pixels)
        if not ok:
            raise OSError(f"PNG 编码失败: {path}")
        # Preparation is a separate explicitly requested operation. It creates new
        # files only, while the experiment pipeline's input protection stays intact.
        with path.open("xb") as stream:
            stream.write(encoded.tobytes())
        decoded = read_image(path)
        if decoded.dtype != pixels.dtype or not np.array_equal(decoded, pixels):
            raise OSError(f"派生图片回读校验失败: {path}")
        return path

    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    alpha = np.full((h, w), 255, dtype=np.uint8)
    transparent_end = max(1, w // 8)
    half_end = max(transparent_end + 1, w // 4)
    alpha[:, :transparent_end] = 0
    alpha[:, transparent_end:half_end] = 128
    rgba = np.dstack((image, alpha))
    small_w = 320 if w != 320 else 160
    small_h = max(1, round(h * small_w / w))
    small = cv2.resize(image, (small_w, small_h), interpolation=cv2.INTER_AREA if small_w < w else cv2.INTER_CUBIC)
    scale = min(1920 / w, 1080 / h)
    resized_w, resized_h = min(1920, max(1, round(w * scale))), min(1080, max(1, round(h * scale)))
    resized = cv2.resize(image, (resized_w, resized_h), interpolation=cv2.INTER_CUBIC if scale >= 1 else cv2.INTER_AREA)
    large = np.zeros((1080, 1920, 3), dtype=np.uint8)
    top, left = (1080 - resized_h) // 2, (1920 - resized_w) // 2
    large[top:top + resized_h, left:left + resized_w] = resized
    variants = {
        "color": save("color.png", image),
        "gray": save("gray.png", gray),
        "rgba": save("rgba.png", rgba),
        "different_size": save("different_size.png", small),
        "large": save("large.png", large),
    }
    if source.suffix.lower() in (".jpg", ".jpeg") and source.read_bytes()[:2] == b"\xff\xd8":
        jpeg = destination / "photo.jpg"
        with jpeg.open("xb") as stream:
            stream.write(source.read_bytes())
        if sha256(jpeg) != before["source"]:
            raise OSError("JPEG 原字节复制校验失败")
        jpeg_method = "JPEG 原文件逐字节复制，未重新压缩"
    else:
        jpeg = destination / "photo.jpg"
        ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not ok:
            raise OSError("JPEG 编码失败")
        with jpeg.open("xb") as stream:
            stream.write(encoded.tobytes())
        jpeg_method = "源图不是 JPEG，以质量 95 导出 JPEG；此格式有损"
    variants["jpeg"] = jpeg
    variants["black"] = original_paths["black"]
    variants["white"] = original_paths["white"]
    after = {key: sha256(path) for key, path in original_paths.items()}
    if before != after:
        raise OSError("原始文件哈希发生变化，停止更新配置")
    manifest = {key: project_path(path) for key, path in variants.items()}
    info = {
        "time": timestamp(), "source": project_path(source), "source_info": attributes(image),
        "original_hashes_before": before, "original_hashes_after": after, "originals_unchanged": True,
        "prepared_directory": project_path(destination), "manifest": manifest,
        "variants": {key: {"path": project_path(path), **attributes(read_image(path)), "sha256": sha256(path)} for key, path in variants.items()},
        "methods": {
            "color": "原 JPEG 解码像素无损保存为三通道 PNG",
            "jpeg": jpeg_method,
            "gray": "OpenCV COLOR_BGR2GRAY，真正的单通道 PNG",
            "rgba": f"保留原 RGB；左侧 {transparent_end} 列 Alpha=0，随后 {half_end-transparent_end} 列 Alpha=128，其余 Alpha=255；为透明度测试遮罩",
            "different_size": f"按比例缩放至 {small_w}×{small_h}",
            "large": f"等比例调整至 {resized_w}×{resized_h}，居中置于 1920×1080 黑色画布；缩放图片用于尺寸及性能测试，不增加原始细节",
            "black": "沿用用户提供的原文件", "white": "沿用用户提供的原文件",
        },
    }
    write_text(ROOT / "config/images.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    evidence = ROOT / "evidence" / batch
    write_text(evidence / "preparation.json", json.dumps(info, ensure_ascii=False, indent=2) + "\n")
    lines = ["# 实验一素材准备记录", "", f"准备时间：{info['time']}。", "",
             f"源图：`{info['source']}`，{w}×{h}，三通道 uint8。源图及用户黑白图前后 SHA-256 均一致。", "",
             "本次根据用户指示由其提供的原图导出实验素材。派生文件位于独立的新建目录，正式测试仍禁止向输入目录写入。", "",
             "| 角色 | 文件 | 宽×高 | 通道 | 转换与来源 |", "| --- | --- | --- | --- | --- |"]
    for key, item in info["variants"].items():
        ih, iw = item["shape"][:2]
        lines.append(f"| {key} | `{item['path']}` | {iw}×{ih} | {item['channels']} | {info['methods'][key]} |")
    lines += ["", f"详细哈希和属性：`{project_path(evidence / 'preparation.json')}`。", "",
              "配置文件 config/images.json 已更新，运行 run_tests.py 即采用本批素材。", "",
              "更换原图后重新运行 prepare_inputs.py，再运行 run_tests.py；之前的派生素材和证据保留。", ""]
    report = "\n".join(lines)
    write_text(ROOT / "docs/input_preparation.md", report)
    write_text(evidence / "input_preparation.md", report)
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--black", type=Path, default=INPUT_ROOT / "black.png")
    parser.add_argument("--white", type=Path, default=INPUT_ROOT / "white.png")
    args = parser.parse_args()
    try:
        if sys.prefix == sys.base_prefix:
            raise ValueError("请使用项目虚拟环境")
        info = prepare(args.source, args.black, args.white)
        print(json.dumps({"status": "SUCCESS", "prepared_directory": info["prepared_directory"],
                          "originals_unchanged": info["originals_unchanged"], "manifest": info["manifest"]}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, cv2.error) as exc:
        print(f"ERROR: 素材准备失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
