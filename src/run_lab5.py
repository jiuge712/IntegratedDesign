"""Run corner and scale experiments; publish only the latest verified results."""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter
import xml.etree.ElementTree as ET

import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from baseline_pipeline import read_image, to_gray
from common import ROOT, VERSION, atomic_write, write_text, sha256, timestamp
from feature import (harris_response, select_points, shi_tomasi_corners,
                     fast_corners, manual_harris_response)
from lab5_scale import (gaussian_pyramid, adjacent_dog, dog_displays,
                        dog_candidates, gaussian_dogs, scale_extrema)
from latest_runs import LatestRun
from version_check import environment


DEFAULTS = {
    'chess': 'data/input/chess.png', 'texture': 'data/input/photo.jpg',
    'harris_k_values': [0.04, 0.06, 0.1], 'block_size': 2, 'sobel_ksize': 3,
    'quality_level': 0.01, 'min_distance': 10.0, 'max_harris_corners': 500,
    'max_shi_corners': 100, 'fast_threshold': 20, 'pyramid_levels': 4,
    'dog_sigma': 1.6, 'dog_scale_ratio': 2 ** (1 / 3),
    'dog_contrast_threshold': 2.0, 'max_dog_candidates': 150,
}


def source_path(value) -> Path:
    path = Path(value)
    path = (path if path.is_absolute() else ROOT / path).resolve()
    if any(path.is_relative_to((ROOT / name).resolve()) for name in ('data/output', 'evidence', 'docs')):
        raise ValueError(f'原图不能位于结果、证据或文档目录: {path}')
    return path


def load_gray(path: Path) -> np.ndarray:
    original = read_image(path)
    if original.dtype != np.uint8:
        raise ValueError('实验五要求 uint8 输入')
    gray, _ = to_gray(original)
    if min(gray.shape) < 16:
        raise ValueError('正式实验图片宽高至少为 16；建议每格至少 20 像素')
    return gray


def save_png(path: Path, image: np.ndarray) -> None:
    success, encoded = cv2.imencode('.png', image)
    if not success:
        raise OSError(f'PNG 编码失败: {path}')
    atomic_write(path, encoded.tobytes())
    decoded = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_UNCHANGED)
    if decoded is None or not np.array_equal(decoded, image):
        raise OSError(f'PNG 回读不一致: {path}')


def overlay(image: np.ndarray, points: np.ndarray, color=(0, 0, 255)) -> np.ndarray:
    result = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    for x, y in points:
        cv2.circle(result, (int(x), int(y)), 3, color, 1, cv2.LINE_AA)
    return result


def figure(path: Path, panels: list, columns=3) -> None:
    rows = (len(panels) + columns - 1) // columns
    fig, axes = plt.subplots(rows, columns, figsize=(4 * columns, 3.7 * rows), squeeze=False)
    for axis, (title, image) in zip(axes.flat, panels):
        if image.ndim == 3:
            axis.imshow(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        else:
            axis.imshow(image, cmap='gray', vmin=0, vmax=255)
        axis.set_title(title)
        axis.axis('off')
    for axis in list(axes.flat)[len(panels):]:
        axis.axis('off')
    fig.tight_layout()
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=140)
    plt.close(fig)
    atomic_write(path, buffer.getvalue())


def measure_detectors(image, cfg):
    responses, points, rows = {}, {}, []
    for k in cfg['harris_k_values']:
        start = perf_counter()
        response = harris_response(image, k, cfg['block_size'], cfg['sobel_ksize'])
        found = select_points(response, cfg['quality_level'], cfg['min_distance'], cfg['max_harris_corners'])
        key = f'harris_{k:g}'
        responses[key], points[key] = response, found
        rows.append({'detector': key, 'count': len(found), 'elapsed_ms': round((perf_counter() - start) * 1000, 4),
                     'min_response': float(response.min()), 'max_response': float(response.max()),
                     'positive_threshold_pixels': int(np.count_nonzero(response > cfg['quality_level'] * max(float(response.max()), 0)))})
    for name, callback in (
        ('shi_tomasi', lambda: shi_tomasi_corners(image, cfg['max_shi_corners'], cfg['quality_level'], cfg['min_distance'])),
        ('fast', lambda: fast_corners(image, cfg['fast_threshold'])),
    ):
        start = perf_counter()
        points[name] = callback()
        rows.append({'detector': name, 'count': len(points[name]), 'elapsed_ms': round((perf_counter() - start) * 1000, 4)})
    return responses, points, rows


def verify_points(points: np.ndarray, shape) -> bool:
    return (points.ndim == 2 and points.shape[1] == 2 and np.issubdtype(points.dtype, np.integer)
            and bool(np.all((points[:, 0] >= 0) & (points[:, 0] < shape[1])))
            and bool(np.all((points[:, 1] >= 0) & (points[:, 1] < shape[0]))))


def test_suite(directory: Path) -> dict:
    command = [sys.executable, '-X', 'utf8', '-m', 'pytest', '-v',
               '--junitxml=' + str(directory / 'pytest.xml')]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=180)
    write_text(directory / 'pytest.log', '$ ' + subprocess.list2cmdline(command) + '\n' + result.stdout + result.stderr)
    if result.returncode != 0:
        # The staged run is discarded on failure; retain failure evidence separately.
        write_text(ROOT / 'evidence/lab5_test_failure.log', result.stdout + result.stderr)
        raise RuntimeError('pytest 未全部通过；见 evidence/lab5_test_failure.log')
    suites = ET.parse(directory / 'pytest.xml').getroot().findall('testsuite')
    summary = {key: sum(int(suite.attrib.get(key, 0)) for suite in suites)
               for key in ('tests', 'failures', 'errors', 'skipped')}
    # pytest 9 includes successful unittest subTests in the JUnit tests count.
    summary['total_checks'] = summary['tests']
    summary['tests'] = sum(len(suite.findall('testcase')) for suite in suites)
    summary['subtests'] = summary['total_checks'] - summary['tests']
    summary['returncode'] = result.returncode
    summary['command'] = command
    return summary


def report_text(info) -> str:
    lines = ['# 实验五：角点检测与尺度空间', '',
             f"运行时间：{info['time']}；程序版本 {info['program_version']}。", '',
             '指导书：实验五_角点检测与尺度空间.docx。完成 Harris 三组 k、Shi-Tomasi、FAST 补充对比、四层 pyrDown 金字塔、相邻层浮点差分及候选区域、pytest 与手写 Harris 加分对比。', '',
             f"本次 pytest 共 {info['pytest']['tests']} 项用例及 {info['pytest']['subtests']} 项子用例，失败 {info['pytest']['failures']}、错误 {info['pytest']['errors']}、跳过 {info['pytest']['skipped']}；正式检查 {len(info['checks'])} 项全部通过。测试日志/JUnit 为 evidence/lab5_latest/pytest.log、pytest.xml。", '',
             '## 素材与参数', '', f"棋盘来源：{info['chess_provenance']}。", '',
             info['chess_description'], '',
             '| 输入角色 | 实际路径 | SHA-256 |', '| --- | --- | --- |']
    lines += [f"| {role} | {path} | {info['input_sha256'][path]} |" for role, path in info['input_sources'].items()]
    lines += ['', '| 参数 | 值 |', '| --- | --- |']
    lines += [f'| {key} | {value} |' for key, value in info['parameters'].items()]
    lines += ['', '## Harris 参数实验', '',
              'M 为局部梯度二阶矩阵，R=det(M)−k·trace(M)²。响应先按相对最大正响应阈值筛选，再做 3×3 局部最大值和最小距离抑制，返回 int32 的 (x,y) 坐标；阈值像素数不等于角点个数。', '',
              '| k | 角点数 | 原始最大 R | 原始最小 R | 阈值像素数 | 检测及选点 ms |', '| --- | --- | --- | --- | --- | --- |']
    for row in info['detectors'][:3]:
        lines.append(f"| {row['detector'].removeprefix('harris_')} | {row['count']} | {row['max_response']:.8f} | {row['min_response']:.8f} | {row['positive_threshold_pixels']} | {row['elapsed_ms']} |")
    lines += ['', '![Harris三组参数](../data/output/lab5_latest/l5_harris_compare.png)', '',
              '固定 M 时 k 增大会降低 R。但每组阈值是各自最大 R 的 1%，不是相同绝对阈值；规则棋盘的交点相似，所以三组角点数量可以相同。不能将本例概括为“k 越大角点必然越少”。', '',
              '## Shi-Tomasi 与 FAST', '',
              'Shi-Tomasi 以 min(λ1,λ2) 选择局部强角点，maxCorners=100 是上限；若只有49个合适交点，结果不需凑满100。FAST 使用圆周亮暗比较，threshold=20、非极大值抑制开启。', '',
              '| 检测器 | 棋盘角点数 | 单次耗时 ms |', '| --- | --- | --- |']
    lines += [f"| {r['detector']} | {r['count']} | {r['elapsed_ms']} |" for r in info['detectors']]
    lines += ['', '![检测器对比](../data/output/lab5_latest/l5_detector_compare.png)', '',
              '精确二值棋盘的交点可能不满足 FAST 连续圆周条件，结果为0也如实保留。配置提供纹理图时另做对照，避免把理想棋盘上的结果推广到所有图。计时包含 Python 包装/选点，单次测量受缓存和调度影响，不构成性能排名。', '']
    if info['texture_detectors']:
        lines += ['| 检测器 | 插画角点数 |', '| --- | --- |']
        lines += [f"| {r['detector']} | {r['count']} |" for r in info['texture_detectors']]
        lines += ['', '![个人插画检测器对照](../data/output/lab5_latest/l5_texture_compare.png)', '']
    lines += ['## λ1–λ2 平面与手写 Harris', '',
              '两个特征值都小对应平坦区域；一大一小对应边缘；两个都大对应角点。散点按本次二阶矩阵取样，不把显示位置作为检测阈值。', '',
              '![特征值平面](../data/output/lab5_latest/l5_lambda_plane.png)', '',
              f"手写分支使用 Sobel、非归一化 boxFilter 构造 M，R=ac−b²−k(a+c)²，不调用 cornerHarris。与 API 原始 R 的相关系数为 {info['manual_comparison']['correlation']}，最大绝对差为 {info['manual_comparison']['max_abs_difference']:.10g}。恒定响应时相关系数无定义，JSON 用 null 表示，改用绝对差验证。", '',
              '![手写与API响应](../data/output/lab5_latest/l5_manual_compare.png)', '',
              '已按 uint8 的255及 Sobel/窗口尺度归一化；浮点运算顺序可导致微小差异。本次数值一致性通过，不是对任意OpenCV版本逐位一致的保证。', '',
              '## 四层高斯金字塔', '', '| 层 | 宽×高 | Harris角点数 |', '| --- | --- | --- |']
    lines += [f"| {r['level']} | {r['width']}×{r['height']} | {r['harris_count']} |" for r in info['pyramid']]
    lines += ['', '![金字塔](../data/output/lab5_latest/l5_pyramid_compare.png)', '',
              '第0层为原图，后续层 pyrDown：先低通再约2倍降采样；奇数尺寸取 ceil(n/2)。对子层使用同样的 blockSize、Sobel核和 minDistance（单位为当前层像素），会影响可保留的角点数。图板各层缩放到自己的面板显示，真实尺寸见表和单层文件。不能由四层都出现角点直接宣称尺度不变。', '',
              '## 相邻层 DoG 近似与候选区域', '',
              '先将粗层 float32 resize 到细层尺寸，再计算 coarse_up−fine，保留正负响应。绝对值图显示强度，signed图用128表示零、亮/暗分别表示正/负；原始差分保存在 raw_arrays.npz。直接对uint8做cv2.subtract会饱和负值，本实现避免该问题。', '',
              '| 相邻层 | 最小值 | 最大值 | 空间候选数 |', '| --- | --- | --- | --- |']
    lines += [f"| {r['fine_level']}→{r['fine_level']+1} | {r['min']:.3f} | {r['max']:.3f} | {r['candidate_count']} |" for r in info['adjacent_dog']]
    lines += ['', '![相邻层差分及候选](../data/output/lab5_latest/l5_dog_compare.png)', '',
              '黄色圈为 |DoG| 的空间局部峰值区域（质量阈值0.1、间距6像素），不是完整SIFT关键点。候选数受 max_dog_candidates 上限限制，达到上限时不能由数量比较真实极值总量；等值峰按行列次序取舍。随着降采样，交界逐渐模糊、细节合并，候选区域位置/数量可能变化。坐标记录含当前层坐标和按2^level映射的原图坐标。', '',
              '另外在原图同尺寸计算六个 Gaussian σ、五张真正 Gaussian DoG，对中间三层与26邻点做严格正/负极值及对比度阈值筛选；等值平台不算严格极值，首尾尺度和最外像素边界不参与。', '',
              f"σ={info['gaussian_dog']['sigmas']}；三维候选共 {info['gaussian_dog']['extrema_count']} 个。", '',
              '![同尺寸Gaussian DoG](../data/output/lab5_latest/l5_gaussian_dog_compare.png)', '',
              '这里未实现多octave、亚像素定位、边缘响应剔除、方向/描述子和匹配，因此只能称尺度空间候选演示，不报告SIFT准确率或尺度不变性。', '',
              '## 自动检查与证据', '', '| 检查 | 结果 |', '| --- | --- |']
    lines += [f"| {row['name']} | PASS |" for row in info['checks']]
    lines += ['',
              'results.json 保存参数、输入哈希和统计；coordinates.json 保存角点/候选坐标；metrics.csv 为检测器数据；raw_arrays.npz 为原始响应、特征值和DoG。所有PNG均通过回读；manifest.json记录输出哈希。pytest.log是真实运行文本，不冒充终端截图。', '',
              '## Git、复现与提交', '',
              '按 feature/l5-corner 分支开发、提交并合并main；远程目标为用户指定仓库，实际提交及推送状态见 lab5_git_workflow.md 和 evidence/lab5_git.log。复现时用git log、git remote -v及git ls-remote检查当前状态，不将本地合并当作远程推送证据。', '',
              '统一 reproduction.md / image_requirements.md 已覆盖实验一至五。最新结果位于 data/output/lab5_latest 与 evidence/lab5_latest；失败保留前次完整结果，原图不变。源码包为 deliverables/lab5_source.zip，图片/输出/证据另交。', '',
              '你本人需复现、截取真实pytest通过画面、填写个人信息并提交；若老师要求实拍棋盘则补实拍素材。user_tasks.md中的既有及新增事项默认未完成，仅在你明确告知后更新。', '']
    return '\n'.join(lines)


def run(config_path: Path, chess_override: Path | None, texture_override: Path | None):
    start = perf_counter()
    provided = json.loads(config_path.read_text(encoding='utf-8-sig'))
    if not isinstance(provided, dict) or set(provided) - set(DEFAULTS):
        raise ValueError('配置应为已约定字段的 JSON 对象，不接受未知键')
    cfg = {**DEFAULTS, **provided}
    if cfg['harris_k_values'] != [0.04, 0.06, 0.1] or cfg['pyramid_levels'] != 4:
        raise ValueError('正式实验需三组 k=[0.04,0.06,0.1] 与 pyramid_levels=4')
    sources = {'chess': source_path(chess_override or cfg['chess'])}
    if texture_override or cfg['texture']:
        sources['texture'] = source_path(texture_override or cfg['texture'])
    hashes = {str(path): sha256(path) for path in sources.values()}
    chess = load_gray(sources['chess'])
    texture = load_gray(sources['texture']) if 'texture' in sources else None
    responses, points, rows = measure_detectors(chess, cfg)
    manual = manual_harris_response(chess, cfg['harris_k_values'][0], cfg['block_size'], cfg['sobel_ksize'])
    api = responses['harris_0.04']
    correlation = (float(np.corrcoef(api.ravel(), manual['response'].ravel())[0, 1])
                   if np.std(api) > 0 and np.std(manual['response']) > 0 else None)
    max_difference = float(np.abs(api - manual['response']).max())
    pyramid = gaussian_pyramid(chess, cfg['pyramid_levels'])
    dogs = [adjacent_dog(pyramid[i], pyramid[i + 1]) for i in range(3)]
    candidates = [dog_candidates(dog, max_points=cfg['max_dog_candidates']) for dog in dogs]
    gaussian, sigmas = gaussian_dogs(chess, cfg['dog_sigma'], cfg['dog_scale_ratio'])
    extrema = scale_extrema(gaussian, cfg['dog_contrast_threshold'])
    provenance = f'配置/命令行指定文件 {sources["chess"]}（未匹配程序棋盘来源记录）'
    description = f'本次使用指定棋盘文件，灰度分析尺寸为 {chess.shape[1]}×{chess.shape[0]}。未预设格子数量或交点真值；按实际响应检测。'
    record = ROOT / 'evidence/chess_source.json'
    if record.exists():
        known = json.loads(record.read_text(encoding='utf-8'))
        if known.get('sha256') == hashes[str(sources['chess'])]:
            provenance = '用户明确授权程序绘制的标准棋盘格（哈希匹配来源记录）'
            description = (f'你已授权程序绘制标准棋盘作为正式素材：{known["rows"]}×{known["columns"]} 格、'
                           f'每格 {known["square_size"]} 像素，{chess.shape[1]}×{chess.shape[0]} 灰度PNG，'
                           f'共有 {known["expected_internal_intersections"]} 个内部交点。不是实拍照片；换图后按新文件重新判断来源。')
    info = {'time': timestamp(), 'program_version': VERSION, 'environment': environment(),
            'parameters': cfg, 'input_sources': {k: str(v) for k, v in sources.items()},
            'input_sha256': hashes, 'chess_provenance': provenance, 'chess_description': description, 'detectors': rows,
            'texture_detectors': [], 'manual_comparison': {'correlation': correlation, 'max_abs_difference': max_difference},
            'pyramid': [], 'adjacent_dog': [], 'gaussian_dog': {'sigmas': sigmas, 'extrema_count': len(extrema)}, 'checks': []}
    coordinates = {'chess': {name: found.tolist() for name, found in points.items()}, 'adjacent_dog': [],
                   'gaussian_extrema': [{'x': int(x), 'y': int(y), 'dog_index': int(s), 'response': float(r)} for x, y, s, r in extrema]}
    raw = {**responses, **{f'manual_{key}': value for key, value in manual.items()},
           **{f'adjacent_dog_{i}': d for i, d in enumerate(dogs)}, **{f'gaussian_dog_{i}': d for i, d in enumerate(gaussian)}}
    with LatestRun('lab5') as latest:
        info['pytest'] = test_suite(latest.evidence)
        save_png(latest.output / 'chess_gray.png', chess)
        harris_panels = []
        for k in cfg['harris_k_values']:
            key = f'harris_{k:g}'
            marked = overlay(chess, points[key])
            save_png(latest.output / f'{key}.png', marked)
            harris_panels.append((f'Harris k={k:g}: {len(points[key])} corners', marked))
        figure(latest.output / 'l5_harris_compare.png', harris_panels)
        shi, fast = overlay(chess, points['shi_tomasi'], (0, 255, 0)), overlay(chess, points['fast'], (255, 0, 0))
        save_png(latest.output / 'shi_tomasi.png', shi)
        save_png(latest.output / 'fast.png', fast)
        figure(latest.output / 'l5_detector_compare.png', [harris_panels[0], (f'Shi-Tomasi: {len(points["shi_tomasi"])}', shi), (f'FAST: {len(points["fast"])}', fast)])
        if texture is not None:
            _, texture_points, texture_rows = measure_detectors(texture, cfg)
            info['texture_detectors'] = texture_rows
            coordinates['texture'] = {key: value.tolist() for key, value in texture_points.items()}
            figure(latest.output / 'l5_texture_compare.png', [(name, overlay(texture, texture_points[name])) for name in ('harris_0.04', 'shi_tomasi', 'fast')])
        # Eigenvalue scatter and response maps use consistent scales for comparison.
        fig, axis = plt.subplots(figsize=(6, 5))
        axis.scatter(manual['lambda1'].ravel()[::7], manual['lambda2'].ravel()[::7], s=8, alpha=0.4)
        axis.set(xlabel='lambda1 (larger)', ylabel='lambda2 (smaller)', title='Second-moment eigenvalues')
        axis.grid(alpha=0.2)
        buffer = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buffer, format='png', dpi=140)
        plt.close(fig)
        atomic_write(latest.output / 'l5_lambda_plane.png', buffer.getvalue())
        response_peak = max(float(np.abs(api).max()), float(np.abs(manual['response']).max()))
        def display_response(response):
            return (np.clip(128 + response / response_peak * 127, 0, 255).astype(np.uint8)
                    if response_peak else np.full(response.shape, 128, np.uint8))
        figure(latest.output / 'l5_manual_compare.png', [('API signed R', display_response(api)), ('Manual signed R', display_response(manual['response']))], 2)
        pyramid_panels = []
        for level, image in enumerate(pyramid):
            found = select_points(harris_response(image, 0.04, cfg['block_size'], cfg['sobel_ksize']), cfg['quality_level'], cfg['min_distance'], cfg['max_harris_corners'])
            info['pyramid'].append({'level': level, 'width': image.shape[1], 'height': image.shape[0], 'harris_count': len(found)})
            raw[f'pyramid_{level}'] = image
            save_png(latest.output / f'pyramid_{level}.png', image)
            pyramid_panels.append((f'L{level}: {image.shape[1]} x {image.shape[0]}', image))
        figure(latest.output / 'l5_pyramid_compare.png', pyramid_panels, 4)
        dog_panels = []
        for index, (dog, found) in enumerate(zip(dogs, candidates)):
            displays = dog_displays(dog)
            marked = overlay(pyramid[index], found, (0, 255, 255))
            for name, image in {**displays, 'candidates': marked}.items():
                save_png(latest.output / f'dog_{index}_{name}.png', image)
            dog_panels += [(f'D{index} absolute', displays['absolute']), (f'D{index} signed (zero=128)', displays['signed']), (f'D{index} candidates: {len(found)}', marked)]
            info['adjacent_dog'].append({'fine_level': index, 'min': float(dog.min()), 'max': float(dog.max()), 'candidate_count': len(found)})
            coordinates['adjacent_dog'].append({'level': index, 'xy': found.tolist(), 'xy_at_base': (found * 2 ** index).tolist()})
        figure(latest.output / 'l5_dog_compare.png', dog_panels)
        figure(latest.output / 'l5_gaussian_dog_compare.png', [(f'Gaussian DoG {i}: sigma {sigmas[i]:.2f} -> {sigmas[i+1]:.2f}', dog_displays(d)['signed']) for i, d in enumerate(gaussian)])
        archive = io.BytesIO()
        np.savez_compressed(archive, **raw)
        atomic_write(latest.evidence / 'raw_arrays.npz', archive.getvalue())
        csv_buffer = io.StringIO(newline='')
        fieldnames = ['scene', 'detector', 'count', 'elapsed_ms', 'min_response', 'max_response', 'positive_threshold_pixels']
        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
        writer.writeheader()
        for scene, data in [('chess', rows), ('texture', info['texture_detectors'])]:
            for row in data:
                writer.writerow({'scene': scene, **row})
        write_text(latest.evidence / 'metrics.csv', csv_buffer.getvalue())
        write_text(latest.evidence / 'coordinates.json', json.dumps(coordinates, ensure_ascii=False, indent=2, allow_nan=False))
        def check(name, condition):
            if not condition:
                raise RuntimeError(f'正式检查失败: {name}')
            info['checks'].append({'name': name, 'passed': True})
        check('pytest 全部通过且无跳过', info['pytest']['tests'] >= 5 and not any(info['pytest'][k] for k in ('failures', 'errors', 'skipped')))
        check('Harris 三组 k 坐标整数且不越界', all(verify_points(points[f'harris_{k:g}'], chess.shape) for k in cfg['harris_k_values']))
        check('Shi-Tomasi 坐标合法且数量不超过配置上限', verify_points(points['shi_tomasi'], chess.shape) and len(points['shi_tomasi']) <= cfg['max_shi_corners'])
        check('FAST 坐标合法（允许零结果）', verify_points(points['fast'], chess.shape))
        check('手写 R 与 API 数值一致', np.allclose(manual['response'], api, rtol=2e-5, atol=2e-8))
        check('特征值重建 trace 和 determinant', np.allclose(manual['lambda1'] + manual['lambda2'], manual['trace'], atol=1e-7) and np.allclose(manual['lambda1'] * manual['lambda2'], manual['determinant'], atol=1e-7))
        check('四层尺寸满足 ceil(n/2)', len(pyramid) == 4 and all(pyramid[i+1].shape == tuple((n+1)//2 for n in pyramid[i].shape) for i in range(3)))
        check('相邻差分保留 float32 且与细层同尺寸', all(d.dtype == np.float32 and d.shape == pyramid[i].shape for i, d in enumerate(dogs)))
        check('DoG 空间候选坐标合法', all(verify_points(found, pyramid[i].shape) for i, found in enumerate(candidates)))
        check('Gaussian DoG 五层和尺度候选边界合法', len(gaussian) == 5 and all(1 <= int(s) <= 3 and 1 <= x < chess.shape[1]-1 and 1 <= y < chess.shape[0]-1 for x,y,s,_ in extrema))
        check('所有原始数组均有限', all(np.isfinite(value).all() for value in raw.values()))
        with np.load(latest.evidence / 'raw_arrays.npz', allow_pickle=False) as restored:
            check('NPZ 回读原始数组一致', set(restored.files) == set(raw) and all(np.array_equal(restored[key], value) for key, value in raw.items()))
        pngs = list(latest.output.glob('*.png'))
        check('全部 PNG 可回读', bool(pngs) and all(cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_UNCHANGED) is not None for path in pngs))
        check('原始输入 SHA-256 不变', all(sha256(Path(path)) == digest for path, digest in hashes.items()))
        info['elapsed_ms'] = round((perf_counter() - start) * 1000, 3)
        info['png_count'] = len(pngs)
        write_text(latest.evidence / 'results.json', json.dumps(info, ensure_ascii=False, indent=2, allow_nan=False))
        manifest = {path.name: sha256(path) for path in pngs}
        write_text(latest.evidence / 'manifest.json', json.dumps(manifest, indent=2))
        write_text(latest.evidence / 'run.log', '$ ' + subprocess.list2cmdline([sys.executable, *sys.argv]) + '\n' + f'SUCCESS: pytest {info["pytest"]["tests"]} tests + {info["pytest"]["subtests"]} subtests; checks {len(info["checks"])}; PNG {len(pngs)}\n')
        latest.commit()
    write_text(ROOT / 'docs/lab5_report.md', report_text(info))
    print(f'SUCCESS: lab5; pytest {info["pytest"]["tests"]} tests + {info["pytest"]["subtests"]} subtests; checks {len(info["checks"])}; PNG {info["png_count"]}')
    print('Harris/Shi/FAST counts: ' + ', '.join(f'{row["detector"]}={row["count"]}' for row in rows))
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'config/lab5_images.json')
    parser.add_argument('--chess', type=Path, help='覆盖棋盘路径，支持中文和空格')
    parser.add_argument('--texture', type=Path, help='覆盖补充纹理图；配置 texture=null 可省略')
    args = parser.parse_args()
    try:
        run(args.config, args.chess, args.texture)
        return 0
    except (OSError, ValueError, TypeError, RuntimeError, cv2.error, subprocess.SubprocessError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
