"""Run real CLI tests and regenerate evidence for replaceable personal images."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

import cv2
import numpy as np

from baseline_pipeline import read_image, validate_image
from common import ROOT, atomic_write, sha256, timestamp, write_text
from version_check import environment
from latest_runs import LatestRun

ROLES = ("color", "jpeg", "gray", "rgba", "different_size", "large", "black", "white")


def save_fixture(path: Path, image: np.ndarray) -> None:
    ok, encoded = cv2.imencode(path.suffix, image)
    if not ok:
        raise ValueError(f"Cannot create test fixture: {path}")
    atomic_write(path, encoded.tobytes())


def make_fixtures(folder: Path) -> dict[str, Path]:
    """Synthetic verification fixtures only; never write into personal data/input."""
    rng = np.random.default_rng(20261013)
    images = {
        "color": rng.integers(0, 256, (240, 320, 3), dtype=np.uint8),
        "jpeg": rng.integers(0, 256, (240, 320, 3), dtype=np.uint8),
        "gray": rng.integers(0, 256, (180, 260), dtype=np.uint8),
        "rgba": rng.integers(0, 256, (120, 200, 4), dtype=np.uint8),
        "different_size": rng.integers(0, 256, (79, 113, 3), dtype=np.uint8),
        "large": rng.integers(0, 256, (1080, 1920, 3), dtype=np.uint8),
        "black": np.zeros((40, 60), dtype=np.uint8),
        "white": np.full((40, 60), 255, dtype=np.uint8),
        "uint16": rng.integers(0, 65536, (50, 70, 3), dtype=np.uint16),
        "golden": np.array([[[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 255], [0, 0, 0]]], dtype=np.uint8),
    }
    paths = {}
    for key, image in images.items():
        path = folder / (key + (".jpg" if key == "jpeg" else ".png"))
        save_fixture(path, image)
        paths[key] = path
    return paths


def load_personal_images(manifest: Path) -> dict[str, Path]:
    config = json.loads(manifest.read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict):
        raise ValueError("图片配置必须是 JSON 对象")
    paths = {}
    errors = []
    for role in ROLES:
        value = config.get(role)
        if not isinstance(value, str) or not value:
            errors.append(f"{role}: 请在 config/images.json 中填写图片路径")
            continue
        path = Path(value)
        paths[role] = (path if path.is_absolute() else ROOT / path).resolve()
        if not paths[role].is_file():
            errors.append(f"{role}: 文件不存在: {paths[role]}")
    if errors:
        raise ValueError("个人图片尚未准备齐全：\n" + "\n".join(errors) + "\n请参照 docs/image_requirements.md。")
    for role, path in paths.items():
        if any(path.is_relative_to((ROOT / name).resolve()) for name in ("evidence", "docs", "data/output")):
            raise ValueError(f"{role}: 原图不能放入结果或文档目录: {path}")
    images = {key: read_image(path) for key, path in paths.items()}
    for key in ("color", "gray", "rgba"):
        if paths[key].suffix.lower() != ".png" or paths[key].read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"{key}: 该测试需要真实 PNG 文件，不能只更改扩展名")
    if paths["jpeg"].suffix.lower() not in (".jpg", ".jpeg") or paths["jpeg"].read_bytes()[:2] != b"\xff\xd8":
        raise ValueError("jpeg: 请提供真实 JPEG 文件")
    for key, channels in (("color", 3), ("jpeg", 3), ("rgba", 4)):
        if images[key].ndim != 3 or images[key].shape[2] != channels:
            raise ValueError(f"{key}: 需要 {channels} 通道图像，实际为 {images[key].shape}")
    if images["gray"].ndim != 2:
        raise ValueError("gray: 需要实际单通道灰度图；外观看似黑白的 RGB 图不符合此用例")
    if images["different_size"].shape[:2] == images["color"].shape[:2]:
        raise ValueError("different_size: 高或宽至少一项应与 color 不同")
    h, w = images["large"].shape[:2]
    if h * w < 1920 * 1080:
        raise ValueError("large: 至少需要 2073600 像素，例如 1920×1080")
    if not np.all(images["black"] == 0):
        raise ValueError("black: 需要像素全为 0 的图像")
    if not np.all(images["white"] == np.iinfo(images["white"].dtype).max):
        raise ValueError("white: 需要像素全为该位深最大值的图像（8 位为 255）")
    return paths


def execute_case(case_id: str, name: str, source: Path, output: Path,
                 evidence: Path, expected_success: bool = True,
                 extra: list[str] | None = None) -> dict:
    command = [sys.executable, "-X", "utf8", str(ROOT / "src/baseline_pipeline.py"),
               "--input", str(source), "--output", str(output)]
    if extra:
        command.extend(extra)
    reasons = []
    info = {}
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=90)
        code, stdout, stderr = result.returncode, result.stdout, result.stderr
        # Interpreter warnings may precede JSON; parse only the structured status line.
        for line in (stdout + "\n" + stderr).splitlines():
            if line.startswith("{"):
                info = json.loads(line)
        if not info:
            reasons.append("没有可解析的程序状态证据")
        if expected_success:
            if code != 0 or info.get("status") != "SUCCESS":
                reasons.append("预期成功，但程序失败")
            else:
                original = read_image(source)
                if original.ndim == 2:
                    expected = original
                else:
                    conversion = cv2.COLOR_BGRA2GRAY if original.shape[2] == 4 else cv2.COLOR_BGR2GRAY
                    expected = cv2.cvtColor(original, conversion)
                saved = read_image(output)
                if saved.ndim != 2 or saved.dtype != original.dtype or saved.shape != original.shape[:2]:
                    reasons.append("输出形状、通道或位深错误")
                if not np.array_equal(saved, expected):
                    reasons.append("输出像素与约定的灰度转换不符")
        elif code == 0 or info.get("status") != "ERROR":
            reasons.append("预期明确报错和非零退出码")
    except (OSError, ValueError, subprocess.TimeoutExpired, cv2.error) as exc:
        code, stdout, stderr = -1, "", str(exc)
        reasons.append(f"测试执行异常: {exc}")
    entry = {
        "id": case_id, "name": name, "expected": "SUCCESS" if expected_success else "ERROR",
        "actual": info.get("status", "NO_STATUS"), "passed": not reasons,
        "exit_code": code, "command": command, "info": info, "failures": reasons,
    }
    log = f"COMMAND: {subprocess.list2cmdline(command)}\nEXIT_CODE: {code}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}\nVERDICT: {'PASS' if not reasons else 'FAIL'}\n"
    write_text(evidence / f"{case_id}.log", log)
    print(f"{case_id} {'PASS' if not reasons else 'FAIL'} expected={entry['expected']} actual={entry['actual']} exit={code}")
    return entry


def report_text(result: dict, evidence: Path, output: Path) -> str:
    personal = result["source_kind"] == "personal_images"
    title = "实验一个人图片测试报告" if personal else "实验一程序自检报告"
    source_note = "输入为用户提供的图片及按其授权导出的实验版本，本次已执行正式测试。素材来源和导出方法见 docs/input_preparation.md（如使用素材准备脚本）。" if personal else (
        "输入为程序生成的临时测试数组，用于验证代码；这些数据没有放入 data/input，也不代表用户个人图片实验结果。个人素材的正式结果另见 docs/test_report.md。")
    lines = [f"# {title}", "", source_note, "", f"运行时间：{result['time']}。", "",
             f"执行 {len(result['tests'])} 个测试，通过 {result['passed']} 个，失败 {result['failed']} 个。",
             f"原始输入 SHA-256 校验：{'全部保持不变' if result['inputs_unchanged'] else '失败'}。", "",
             "| 用例 | 输入条件 | 预期状态 | 实际状态 | 退出码 | 结论 | 处理耗时 ms |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for case in result["tests"]:
        elapsed = case["info"].get("elapsed_ms", "—")
        lines.append(f"| {case['id']} | {case['name']} | {case['expected']} | {case['actual']} | {case['exit_code']} | {'PASS' if case['passed'] else 'FAIL'} | {elapsed} |")
    lines.extend(["", "## 运行证据", "", f"日志与结构化数据：`{evidence.relative_to(ROOT).as_posix()}`。",
                  f"灰度结果：`{output.relative_to(ROOT).as_posix()}`。", "",
                  "命令行用例的 .log 包含实际命令、退出码、标准输出和错误输出；数组校验用例记录函数、输入属性和异常。results.json 保存全部输出属性、版本、输入输出哈希和耗时。",
                  "异常用例预期 ERROR；明确报错且退出码为非零时，测试结论为 PASS。", "",
                  "## 性能记录", ""])
    large = next(case for case in result["tests"] if case["id"] == "T10")
    info = large["info"]
    if info.get("status") == "SUCCESS":
        lines.append(f"T10 输入 {info['input_info']['shape']}，处理耗时 {info['elapsed_ms']} ms。")
        meets = info["elapsed_ms"] <= 2000
        lines.append(f"≤ 2 s 的性能参考：{'满足' if meets else '未满足，需分析平台与图片压缩内容'}。该项为平台相关参考指标，不改变功能测试结论。")
    else:
        lines.append("T10 处理失败，无有效性能结论。")
    lines.extend(["计时覆盖读取、检查、转换、编码和保存，不包含 Python 启动、保存后回读或哈希计算。", "",
                  "## 结果分析与限制", "",
                  "通过项说明正常输入、灰度分支、透明通道策略、中文路径、异常反馈及输入保护满足接口约定。"
                  if result["failed"] == 0 else "存在失败项，请查看对应日志，不应据此宣布实验通过。",
                  "预期异常来自不存在路径、损坏文件或无效输出条件；它们不是已通过测试中的程序缺陷。",
                  "范围为单张静态图像的基线处理；不执行实验二至五的算法。下一实验可继承命令行路径、BGR/BGRA/GRAY、uint8/uint16、PNG输出及状态证据约定。", "",
                  "如需截图，请真实截取运行终端与输出文件属性；截图方法见 reproduction.md。", "",
                  "## 失败详情", ""])
    failed = [case for case in result["tests"] if not case["passed"]]
    lines.extend([f"- {case['id']}: {'; '.join(case['failures'])}" for case in failed] or ["本次没有非预期失败。"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "config/images.json")
    parser.add_argument("--self-test", action="store_true", help="Synthetic fixtures for code verification only")
    args = parser.parse_args()
    latest = None
    try:
        if sys.prefix == sys.base_prefix:
            raise ValueError("请使用 project_i/.venv 中的 Python")
        run_id = ("self_test_" if args.self_test else "personal_") + timestamp().replace(":", "-") + "_" + uuid.uuid4().hex[:6]
        evidence = ROOT / "evidence" / run_id
        output = ROOT / "data/output" / run_id
        if args.self_test:
            paths = make_fixtures(evidence / "fixtures")
        else:
            paths = load_personal_images(args.manifest)
            latest = LatestRun("lab1").__enter__()
            evidence, output = latest.evidence, latest.output
        evidence.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        before = {str(path): sha256(path) for path in paths.values()}
        cases = []

        def run(case_id, name, source, destination=None, success=True, extra=None):
            cases.append(execute_case(case_id, name, source, destination or output / f"{case_id}.png", evidence, success, extra))

        run("T01", "彩色 PNG", paths["color"], extra=["--record", str(evidence / "pipeline_records.jsonl")])
        run("T02", "彩色 JPEG", paths["jpeg"])
        run("T03", "不存在路径", evidence / "not_exists.png", success=False)
        run("T04", "单通道灰度 PNG", paths["gray"])
        run("T05", "四通道 RGBA PNG，舍弃 Alpha", paths["rgba"])
        chinese = evidence / "中文路径" / "个人图片.png"
        chinese.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(paths["color"], chinese)
        run("T06", "中文输入和输出路径", chinese, output / "中文结果" / "灰度.png")
        corrupt = evidence / "corrupt.png"
        write_text(corrupt, "This file is deliberately invalid image data.")
        run("T07", "损坏图片", corrupt, success=False)
        run("T08", "输出目录不存在", paths["color"], output / "new/nested/gray.png")
        run("T09a", "全黑图", paths["black"])
        run("T09b", "全白图", paths["white"])
        run("T10", "较大图像及耗时", paths["large"])
        run("T11", "不同尺寸图像", paths["different_size"])
        directory = output / "directory.png"
        directory.mkdir()
        run("T12", "输出路径为目录", paths["color"], directory, success=False)
        run("T13", "输出与输入相同", paths["color"], paths["color"], success=False)
        run("T14", "不支持的输出扩展名", paths["color"], output / "bad.jpg", success=False)
        protected = ROOT / "data/input" / f"must_not_write_{uuid.uuid4().hex}.png"
        run("T15", "写入原始输入目录", paths["color"], protected, success=False)
        if protected.exists():
            cases[-1]["passed"] = False
            cases[-1]["failures"].append("输入目录被写入")
        record_image = output / "T17.png"
        run("T17", "日志与图片路径冲突", paths["color"], record_image, success=False,
            extra=["--record", str(record_image)])
        if record_image.exists():
            cases[-1]["passed"] = False
            cases[-1]["failures"].append("冲突路径被写入")
        if args.self_test:
            run("T16", "16 位彩色 PNG 保留位深", paths["uint16"])
            run("T20", "已知蓝绿红白黑像素的灰度权重", paths["golden"])
            if cases[-1]["passed"]:
                actual = read_image(output / "T20.png")
                if actual.tolist() != [[29, 150, 76, 255, 0]]:
                    cases[-1]["passed"] = False
                    cases[-1]["failures"].append("已知颜色的独立期望值不符")
            for case_id, name, image in (
                ("T18", "拒绝 float32 数组", np.zeros((2, 2), np.float32)),
                ("T19", "拒绝两通道数组", np.zeros((2, 2, 2), np.uint8)),
            ):
                try:
                    validate_image(image)
                    passed, message = False, "未拒绝不支持的数据"
                except ValueError as exc:
                    passed, message = True, str(exc)
                entry = {"id": case_id, "name": name, "expected": "ERROR", "actual": "ERROR" if passed else "SUCCESS",
                         "passed": passed, "exit_code": "函数检查", "info": {"error": message}, "failures": [] if passed else [message]}
                cases.append(entry)
                write_text(evidence / f"{case_id}.log", f"FUNCTION: validate_image\nINPUT: shape={image.shape}, dtype={image.dtype}\nRESULT: {message}\nVERDICT: {'PASS' if passed else 'FAIL'}\n")
                print(f"{case_id} {'PASS' if passed else 'FAIL'}")
        after = {str(path): sha256(path) for path in paths.values()}
        result = {"time": timestamp(), "source_kind": "synthetic_verification" if args.self_test else "personal_images",
                  "environment": environment(), "tests": cases, "input_hashes_before": before, "input_hashes_after": after,
                  "inputs_unchanged": before == after,
                  "passed": sum(case["passed"] for case in cases), "failed": sum(not case["passed"] for case in cases)}
        if latest:
            for case in cases:
                info = case["info"]
                runtime = {}
                for key in ("input", "output"):
                    value = info.get(key)
                    if value:
                        final = value.replace(str(latest.output),str(latest.final_output)).replace(str(latest.evidence),str(latest.final_evidence))
                        if final != value:
                            runtime[key] = value
                            info[key] = final
                if runtime:
                    info["runtime_paths_before_publication"] = runtime
        write_text(evidence / "results.json", json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        summary = "\n".join(json.dumps(case, ensure_ascii=False) for case in cases) + "\n"
        write_text(evidence / "output_info.txt", summary)
        report = report_text(result, latest.final_evidence if latest else evidence, latest.final_output if latest else output)
        write_text(evidence / "test_report.md", report)
        report_path = ROOT / "docs" / ("self_test_report.md" if args.self_test else "test_report.md")
        if latest:
            if result["failed"] or not result["inputs_unchanged"]:
                write_text(ROOT / "evidence/lab1_last_failure.log",summary)
                print("ERROR: 本次未通过校验，保留上次完整结果",file=sys.stderr)
                return 1
            latest.commit()
            evidence, output = latest.final_evidence, latest.final_output
        write_text(report_path, report)
        if not args.self_test:
            write_text(ROOT / "evidence/output_info.txt", summary)
        print(f"SUMMARY: {result['passed']}/{len(cases)} passed; original_inputs_unchanged={result['inputs_unchanged']}")
        print(f"REPORT: {report_path}\nEVIDENCE: {evidence}\nOUTPUT: {output}")
        return 0 if result["failed"] == 0 and result["inputs_unchanged"] else 1
    except (OSError, ValueError, KeyError, cv2.error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if latest:
            latest.__exit__(None,None,None)


if __name__ == "__main__":
    raise SystemExit(main())
