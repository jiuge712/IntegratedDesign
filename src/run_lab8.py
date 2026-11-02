"""Run SIFT -> matching -> right-to-left RANSAC -> full-canvas stitching."""
from __future__ import annotations
import argparse
import io
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter
import xml.etree.ElementTree as ET
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import ROOT, VERSION, sha256, timestamp, write_text, atomic_write
from features import sift_config, keypoint_records
from matching import positive_integer, ratio_parameter, symmetric_ratio
from lab6_geometry import positive_number
from homography import match_and_estimate, estimate_homography, stitch_pair
from lab7_artifacts import load_photo, save_png, write_csv
from lab2_common import save_figure
from latest_runs import LatestRun
from version_check import environment
from lab8_report import report_text

DEFAULTS = dict(image1='data/input/eight-v6-1.jpg', image2='data/input/eight-v6-2.jpg',
                max_input_side=2400, sift={}, ratio_threshold=.75, ransac_threshold=5.,
                confidence=.995, max_iters=10000, seed=8, max_draw_matches=100,
                max_canvas_pixels=20_000_000)


def load_config(path):
    path = Path(path)
    path = path if path.is_absolute() else ROOT/path
    provided = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(provided, dict) or set(provided)-set(DEFAULTS):
        raise ValueError('实验八配置必须是已知字段组成的JSON对象')
    cfg = {**DEFAULTS, **provided}
    cfg['sift'] = sift_config(cfg['sift'])
    for key in ('image1', 'image2'):
        if not isinstance(cfg[key], str) or not cfg[key].strip():
            raise ValueError(key+'需为非空图片路径')
    for key in ('max_input_side', 'seed'):
        positive_integer(cfg[key], key, 0)
    if cfg['seed'] > 2**31-1 or 0 < cfg['max_input_side'] < 16:
        raise ValueError('seed超出范围或max_input_side不足16')
    for key in ('max_iters', 'max_draw_matches', 'max_canvas_pixels'):
        positive_integer(cfg[key], key)
    ratio_parameter(cfg['ratio_threshold'])
    positive_number(cfg['ransac_threshold'], 'ransac_threshold')
    if positive_number(cfg['confidence'], 'confidence') >= 1:
        raise ValueError('confidence必须小于1')
    return cfg


def run_tests(directory):
    command = [sys.executable, '-X', 'utf8', '-m', 'pytest', '-v',
               '--basetemp='+str(ROOT/'.tmp/pytest_lab8'), '--junitxml='+str(directory/'pytest.xml')]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=240)
    log = '$ '+subprocess.list2cmdline(command)+'\n'+result.stdout+result.stderr
    write_text(directory/'pytest.log', log)
    if result.returncode:
        write_text(ROOT/'evidence/lab8_test_failure.log', log)
        raise RuntimeError('pytest失败，前次结果保留；见evidence/lab8_test_failure.log')
    suites = ET.parse(directory/'pytest.xml').getroot().findall('testsuite')
    count = sum(len(s.findall('testcase')) for s in suites)
    return dict(tests=count, subtests=sum(int(s.attrib.get('tests', 0)) for s in suites)-count,
                **{key:sum(int(s.attrib.get(key, 0)) for s in suites) for key in ('failures','errors','skipped')},
                command=command)


def draw_matches(image1, image2, data, selected, limit, seed, color, title):
    indices = np.flatnonzero(selected)
    chosen = sorted(np.random.default_rng(seed).choice(indices, min(limit, len(indices)), replace=False).tolist())
    picture = cv2.drawMatches(image1, data['kp1'], image2, data['kp2'],
                             [data['matches'][i] for i in chosen], None, matchColor=color,
                             flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
    scale = min(1., 2400/picture.shape[1])
    if scale < 1:
        picture = cv2.resize(picture, (round(picture.shape[1]*scale), round(picture.shape[0]*scale)))
    cv2.rectangle(picture, (0,0), (picture.shape[1]-1,40), (25,25,25), -1)
    cv2.putText(picture, f'{title}: {len(indices)} total, {len(chosen)} drawn', (12,28),
                cv2.FONT_HERSHEY_SIMPLEX, .7, color, 1, cv2.LINE_AA)
    return picture, chosen


def source_matrix(source):
    return np.vstack([source['source_to_work_pixel_centers'], [0.,0.,1.]])


def run(config_path, image1_override=None, image2_override=None):
    start = perf_counter()
    cfg = load_config(config_path)
    image1, source1 = load_photo(image1_override or cfg['image1'], cfg['max_input_side'])
    image2, source2 = load_photo(image2_override or cfg['image2'], cfg['max_input_side'])
    data = match_and_estimate(image1, image2, cfg['ratio_threshold'], cfg['sift'],
                              cfg['ransac_threshold'], cfg['confidence'], cfg['max_iters'], cfg['seed'])
    n = len(data['matches']); mask = data['inliers']; H = data['H']
    if n < 30 or mask.mean() <= .5:
        raise ValueError(f'本次匹配{n}对、内点{mask.sum()}；正式链路需≥30对且内点比例>50%，请检查图片/参数')
    stitched = stitch_pair(image1, image2, H, cfg['max_canvas_pixels'])
    geometry = stitched['geometry']
    original_H = np.linalg.inv(source_matrix(source1)) @ H @ source_matrix(source2)
    original_H /= original_H[2,2]
    info = dict(status='SUCCESS', time=timestamp(), program_version=VERSION, environment=environment(),
                parameters=cfg, sources={'image1':source1,'image2':source2},
                feature_counts=[len(data['kp1']),len(data['kp2'])], match_count=n,
                inliers=int(mask.sum()), outliers=int((~mask).sum()), inlier_ratio=float(mask.mean()),
                inlier_median_error_working_px=float(np.median(data['errors'][mask])),
                inlier_p95_error_working_px=float(np.percentile(data['errors'][mask],95)),
                H_working_right_to_left=H.tolist(), H_original_right_to_left=original_H.tolist(),
                canvas=dict(size=list(geometry['size']), origin_xy=geometry['origin'],
                            translation=geometry['translation'].tolist(),
                            projected_right_corners=geometry['right_corners_in_left'].tolist()),
                overlap_pixels=int(stitched['overlap'].sum()),
                overlap_fraction_of_left=float(stitched['overlap'].sum()/stitched['left_mask'].sum()),
                trials=[], checks=[], camera_view_angle_degrees=None,
                material_source='user-provided files; authorship, capture angle and publication rights not inferred',
                m1=dict(technical_demo_ready=True, real_review_completed=False, score=None),
                visual_review='Inspect current results after every source/config change; numeric checks do not certify all pixels.')
    for threshold in sorted(set([.6,.75,.9,cfg['ratio_threshold']])):
        matches = symmetric_ratio(data['forward'], data['reverse'], threshold)
        left = np.float64([data['kp1'][m.queryIdx].pt for m in matches]).reshape(-1,2)
        right = np.float64([data['kp2'][m.trainIdx].pt for m in matches]).reshape(-1,2)
        try:
            matrix, accepted, errors = estimate_homography(right,left,cfg['ransac_threshold'],
                                                           cfg['confidence'],cfg['max_iters'],cfg['seed'])
            info['trials'].append(dict(ratio=threshold, matches=len(matches), inliers=int(accepted.sum()),
                                      inlier_ratio=float(accepted.mean()), H=matrix.tolist()))
        except ValueError as exc:
            info['trials'].append(dict(ratio=threshold, matches=len(matches), error=str(exc)))
    with LatestRun('lab8') as latest:
        info['pytest'] = run_tests(latest.evidence)
        for name, image in [('image1_work.png',image1),('image2_work.png',image2),
                            ('l8_warped_right.png',stitched['warped_right']),('l8_stitch_hard.png',stitched['hard']),
                            ('l8_stitch_feather.png',stitched['feather']),('l8_overlap_diagnostic.png',stitched['overlay'])]:
            save_png(latest.output/name, image)
        masks = np.zeros_like(stitched['hard'])
        masks[stitched['left_mask']] = (255,0,0)
        masks[stitched['right_mask']] = (0,0,255)
        masks[stitched['overlap']] = (0,255,0)
        save_png(latest.output/'l8_valid_masks.png',masks)
        info['drawn_match_indices'] = {}
        figures = []
        for name, selected, color, title in [('before',np.ones(n,bool),(180,180,180),'Before RANSAC'),
                                            ('inliers',mask,(0,255,0),'RANSAC inliers'),
                                            ('outliers',~mask,(0,0,255),'RANSAC outliers')]:
            picture, indices = draw_matches(image1,image2,data,selected,cfg['max_draw_matches'],cfg['seed'],color,title)
            save_png(latest.output/f'l8_{name}.png',picture)
            info['drawn_match_indices'][name] = indices
            if name != 'before': figures.append(picture)
        save_png(latest.output/'l8_inlier_outlier_compare.png',np.vstack(figures))
        support = image1.copy()
        for point, accepted in zip(data['left'],mask):
            cv2.circle(support,tuple(np.rint(point).astype(int)),3,(0,255,0) if accepted else (0,0,255),1)
        save_png(latest.output/'l8_support.png',support)
        fig, axes = plt.subplots(1,2,figsize=(10,4),layout='constrained')
        trials = [r for r in info['trials'] if 'error' not in r]
        xx = np.arange(len(trials))
        axes[0].bar(xx-.15,[r['matches'] for r in trials],.3,label='Matched')
        axes[0].bar(xx+.15,[r['inliers'] for r in trials],.3,label='Inliers')
        axes[0].set_xticks(xx,[str(r['ratio']) for r in trials]);axes[0].legend()
        axes[0].set(title='RANSAC counts',xlabel='Ratio threshold',ylabel='Pairs')
        axes[1].bar(xx,[100*r['inlier_ratio'] for r in trials]);axes[1].set_xticks(xx,[str(r['ratio']) for r in trials])
        axes[1].set(title='Model consistency is not human ground truth',xlabel='Ratio threshold',ylabel='Inliers (%)',ylim=(0,100))
        save_figure(latest.output/'l8_thresholds.png',fig)
        records=[]
        for i,m in enumerate(data['matches']):
            records.append(dict(query_index=int(m.queryIdx),train_index=int(m.trainIdx),
                                left_x=float(data['left'][i,0]),left_y=float(data['left'][i,1]),
                                right_x=float(data['right'][i,0]),right_y=float(data['right'][i,1]),
                                distance=float(m.distance),inlier=int(mask[i]),error_working_px=float(data['errors'][i])))
        write_csv(latest.evidence/'matches.csv',list(records[0]),records)
        write_text(latest.evidence/'keypoints.json',json.dumps(dict(image1=keypoint_records(data['kp1']),
                                                                   image2=keypoint_records(data['kp2'])),indent=2))
        buffer=io.BytesIO()
        np.savez_compressed(buffer,image1_descriptors=data['desc1'],image2_descriptors=data['desc2'],
                            left_points=data['left'],right_points=data['right'],H=H,
                            H_original=original_H,inliers=mask,errors=data['errors'],
                            translation=geometry['translation'],alpha=stitched['alpha'])
        atomic_write(latest.evidence/'geometry.npz',buffer.getvalue())
        def check(name, condition):
            if not bool(condition): raise RuntimeError('正式检查失败：'+name)
            info['checks'].append(dict(name=name,passed=True))
        check('全部pytest通过且无跳过',not any(info['pytest'][k] for k in ('failures','errors','skipped')))
        check('匹配数大于0且至少30',n>=30)
        check('H形状3×3且有限',H.shape==(3,3) and np.isfinite(H).all())
        check('实际图片内点比例大于50%',mask.mean()>.5)
        check('内外点总数等于匹配数',info['inliers']+info['outliers']==n)
        check('全部匹配索引合法',all(0<=m.queryIdx<len(data['kp1']) and 0<=m.trainIdx<len(data['kp2']) for m in data['matches']))
        check('完整画布覆盖两图投影角点',all(np.all(v>=-1e-7) and np.all(v<=np.array(geometry['size'])-1+1e-7)
              for v in (geometry['left_corners']-np.array(geometry['origin']),geometry['right_corners_in_left']-np.array(geometry['origin']))))
        check('有效重叠不为空',stitched['overlap'].any())
        check('羽化权重有限且位于0至1',np.isfinite(stitched['alpha']).all() and stitched['alpha'].min()>=0 and stitched['alpha'].max()<=1)
        check('独占区域与直接覆盖一致',np.array_equal(stitched['feather'][~stitched['overlap']],stitched['hard'][~stitched['overlap']]))
        with np.load(latest.evidence/'geometry.npz',allow_pickle=False) as saved:
            check('归档H与内点回读一致',np.array_equal(saved['H'],H) and np.array_equal(saved['inliers'],mask))
        pngs=list(latest.output.glob('*.png'))
        check('全部PNG可回读',bool(pngs) and all(cv2.imdecode(np.frombuffer(p.read_bytes(),np.uint8),cv2.IMREAD_UNCHANGED) is not None for p in pngs))
        check('两个原始输入SHA256未变',all(sha256(Path(s['path']))==s['sha256'] for s in (source1,source2)))
        info['png_count']=len(pngs);info['elapsed_ms']=round((perf_counter()-start)*1000,3)
        write_text(latest.evidence/'results.json',json.dumps(info,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        write_text(latest.evidence/'manifest.json',json.dumps({p.name:sha256(p) for p in pngs},indent=2))
        write_text(latest.evidence/'run.log','$ '+subprocess.list2cmdline([sys.executable,*sys.argv])+'\nSUCCESS\n')
        report=report_text(info)
        write_text(latest.evidence/'lab_report.md',report.replace('../data/output/lab8_latest/','../../data/output/lab8_latest/'))
        latest.commit()
    write_text(ROOT/'docs/lab8_report.md',report)
    print(f'SUCCESS: lab8; matches={n}; inliers={info["inliers"]}; ratio={info["inlier_ratio"]:.2%}; canvas={geometry["size"]}; PNG={len(pngs)}')
    print('H (right -> left, working pixels):\n'+np.array2string(H,precision=9))
    print(f'pytest: {info["pytest"]["tests"]} main cases + {info["pytest"]["subtests"]} subtests; checks={len(info["checks"])}')
    return info


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'config/lab8_images.json')
    parser.add_argument('--image1',type=Path);parser.add_argument('--image2',type=Path)
    args=parser.parse_args()
    try:
        if sys.prefix==sys.base_prefix: raise ValueError('请使用项目虚拟环境')
        run(args.config,args.image1,args.image2)
        return 0
    except (OSError,ValueError,TypeError,RuntimeError,cv2.error,subprocess.SubprocessError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
