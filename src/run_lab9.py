"""Calibrate from detected raster corners, validate, and publish latest lab-nine results."""
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
from common import ROOT,VERSION,sha256,write_text,timestamp,atomic_write
from baseline_pipeline import read_image
from calibration import (board_points,gray_uint8,detect_board,calibrate_views,pose_coverage,straightness,
                         corrected_points,undistort_image,projected_board_fraction,check_source_manifest,straightness_accepted,
                         result_exports,load_calibration)
from matching import positive_integer
from lab6_geometry import positive_number
from lab7_artifacts import save_png,write_csv
from lab2_common import save_figure
from latest_runs import LatestRun
from version_check import environment
from lab9_report import report_text,test_plan_text

DEFAULTS=dict(input_dir='data/calib/lab9_synthetic',image_glob='calib_*.png',validation_glob='validation/validation_*.png',
              cols=9,rows=7,square_size_mm=25.,min_views=15,max_rms=.5,min_pitch_span_deg=30.,
              min_yaw_span_deg=30.,min_board_fraction=.30,camera_id=None)


def source_path(value):
    p=Path(value);p=(p if p.is_absolute() else ROOT/p).resolve()
    if any(p.is_relative_to((ROOT/name).resolve()) for name in ('data/output','evidence','docs','results')):
        raise ValueError('标定输入需在持久素材目录，不得放在结果、证据或文档目录')
    return p


def load_config(path):
    path=Path(path);path=path if path.is_absolute() else ROOT/path
    provided=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(provided,dict) or set(provided)-set(DEFAULTS):raise ValueError('实验九JSON包含未知字段或不是对象')
    cfg={**DEFAULTS,**provided}
    board_points(cfg['cols'],cfg['rows'],cfg['square_size_mm'])
    positive_integer(cfg['min_views'],'min_views',15)
    for key in ('max_rms','min_pitch_span_deg','min_yaw_span_deg','min_board_fraction'):
        positive_number(cfg[key],key)
    if cfg['min_board_fraction']>1:raise ValueError('min_board_fraction不能大于1')
    if cfg['min_board_fraction']<.30 or min(cfg['min_pitch_span_deg'],cfg['min_yaw_span_deg'])<30 or cfg['max_rms']>1:
        raise ValueError('正式验收需占比至少30%、俯仰/偏航跨度至少30°，RMS上限不能超过1px')
    for key in ('input_dir','image_glob'):
        if not isinstance(cfg[key],str) or not cfg[key].strip():raise ValueError(key+'需非空字符串')
    for key in ('image_glob','validation_glob'):
        value=cfg[key]
        if value is None and key=='validation_glob':continue
        if not isinstance(value,str) or Path(value).is_absolute() or '..' in Path(value).parts:
            raise ValueError('图片glob必须为目录内相对模式')
    if cfg['camera_id'] is not None and (not isinstance(cfg['camera_id'],str) or not cfg['camera_id'].strip()):
        raise ValueError('camera_id需非空字符串或null')
    return cfg


def run_tests(folder):
    command=[sys.executable,'-X','utf8','-m','pytest','-v','-o','cache_dir='+str(ROOT/'.tmp/pytest_lab9_cache'),'--basetemp='+str(ROOT/'.tmp/pytest_lab9'),
             '--junitxml='+str(folder/'pytest.xml')]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=240)
    log='$ '+subprocess.list2cmdline(command)+'\n'+result.stdout+result.stderr
    write_text(folder/'pytest.log',log)
    if result.returncode:
        write_text(ROOT/'evidence/lab9_test_failure.log',log)
        raise RuntimeError('pytest失败，前次结果保留；见evidence/lab9_test_failure.log')
    suites=ET.parse(folder/'pytest.xml').getroot().findall('testsuite')
    count=sum(len(s.findall('testcase')) for s in suites)
    return dict(tests=count,subtests=sum(int(s.attrib.get('tests',0)) for s in suites)-count,
                **{k:sum(int(s.attrib.get(k,0)) for s in suites) for k in ('failures','errors','skipped')},command=command)


def save_npy(path,array):
    buffer=io.BytesIO();np.save(buffer,array,allow_pickle=False);atomic_write(path,buffer.getvalue())


def contact_sheet(images,columns=5):
    cards=[]
    for index,image in enumerate(images):
        if image.ndim==2:image=cv2.cvtColor(image,cv2.COLOR_GRAY2BGR)
        thumb=cv2.resize(image,(320,240));cv2.rectangle(thumb,(0,0),(319,24),(30,30,30),-1)
        cv2.putText(thumb,f'calib_{index+1:02d}',(8,18),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
        cards.append(thumb)
    while len(cards)%columns:cards.append(np.full_like(cards[0],255))
    return np.vstack([np.hstack(cards[i:i+columns]) for i in range(0,len(cards),columns)])


def run(config_path,input_override=None):
    start=perf_counter();cfg=load_config(config_path)
    folder=source_path(input_override or cfg['input_dir'])
    files=sorted(source_path(p) for p in folder.glob(cfg['image_glob']) if p.is_file())
    if len(files)<cfg['min_views']:raise ValueError('图片少于15张或目录/模式不符，请先prepare_lab9.py或提供标定图')
    manifest=check_source_manifest(folder,files,cfg['cols'],cfg['rows'],cfg['square_size_mm'])
    validation_files=sorted(source_path(p) for p in folder.glob(cfg['validation_glob']) if p.is_file()) if cfg['validation_glob'] else []
    if set(validation_files)&set(files):raise ValueError('验证图必须独立，不能参与拟合')
    camera_id=cfg['camera_id'] or (f'lab9_synthetic_v{manifest["generator_version"]}_seed{manifest["seed"]}' if manifest else 'unverified_user_camera')
    records=[];images=[];detected=[];all_hashes={};size=None
    for path in files:
        digest=sha256(path);all_hashes[str(path)]=digest
        record=dict(path=str(path),sha256=digest,detected=False)
        try:image=read_image(path)
        except (OSError,ValueError):
            record['reason']='cannot_decode';records.append(record);continue
        gray=gray_uint8(image)
        if size is None:size=(gray.shape[1],gray.shape[0])
        if size!=(gray.shape[1],gray.shape[0]):raise ValueError('同一相机标定必须同分辨率，拒绝隐式缩放混合尺寸')
        found=detect_board(image,cfg['cols'],cfg['rows'])
        if found is None:
            record['reason']='corners_not_found';records.append(record);continue
        record.update(detected=True,used_index=len(detected),corner_count=cfg['cols']*cfg['rows'])
        records.append(record);images.append(image);detected.append(found)
    if len(set(all_hashes.values()))!=len(all_hashes):raise ValueError('存在完全重复的标定图片，不得重复计数充足张数')
    if len(detected)<cfg['min_views']:raise ValueError('成功检出的可用棋盘图不足15张，失败图已排除且不删除原片')
    raw=[x['raw'] for x in detected];refined=[x['refined'] for x in detected]
    args=(size,cfg['cols'],cfg['rows'],cfg['square_size_mm'],cfg['min_views'])
    before=calibrate_views(raw,*args);calib=calibrate_views(refined,*args)
    K,dist=calib['K'],calib['dist'];coverage=pose_coverage(calib['rvecs'])
    fractions=[projected_board_fraction(rv,tv,K,dist,size,cfg['cols'],cfg['rows'],cfg['square_size_mm'])
               for rv,tv in zip(calib['rvecs'],calib['tvecs'])]
    line_before=[straightness(x,cfg['cols'],cfg['rows']) for x in refined]
    line_after=[straightness(corrected_points(x,K,dist),cfg['cols'],cfg['rows']) for x in refined]
    info=dict(status='SUCCESS',time=timestamp(),program_version=VERSION,environment=environment(),parameters=cfg,
              source_kind='synthetic' if manifest else 'provided_unverified',camera_id=camera_id,
              warning='K/dist仅适用于该相机模型及本分辨率；合成参数不用于实验七/八或其他真实相机图片。',
              input_directory=str(folder),image_size=list(size),collection=records,
              input_count=len(files),detected_count=len(detected),detection_rate=len(detected)/len(files),
              corners_per_image=cfg['cols']*cfg['rows'],rms=calib['rms'],recomputed_rms=calib['recomputed_rms'],
              raw_corner_rms=before['rms'],K=K.tolist(),dist=dist.tolist(),coverage=coverage,
              projected_board_fractions=fractions,per_view_rms=calib['per_view_rms'],
              straightness_before_px=line_before,straightness_after_px=line_after,
              straightness_mean_before_px=float(np.mean(line_before)),straightness_mean_after_px=float(np.mean(line_after)),
              rvecs=[v.ravel().tolist() for v in calib['rvecs']],tvecs_mm=[v.ravel().tolist() for v in calib['tvecs']],
              validation=[],known_truth=None,checks=[],physical_camera_calibrated=False if manifest else None)
    validation_images=[]
    obj=board_points(cfg['cols'],cfg['rows'],cfg['square_size_mm'])
    for path in validation_files:
        all_hashes[str(path)]=sha256(path);image=read_image(path)
        if image.shape[:2]!=(size[1],size[0]):raise ValueError('验证图分辨率不符')
        found=detect_board(image,cfg['cols'],cfg['rows'])
        if found is None:raise ValueError('独立验证图角点未检出')
        und=undistort_image(image,K,dist);redetected=detect_board(und,cfg['cols'],cfg['rows'])
        if redetected is None:raise ValueError('去畸变图角点重检失败')
        ok,rv,tv=cv2.solvePnP(obj,found['refined'],K,dist)
        if not ok:raise ValueError('独立验证图位姿求解失败')
        predicted=cv2.projectPoints(obj,rv,tv,K,dist)[0].reshape(-1,2)
        error=np.linalg.norm(predicted-found['refined'].reshape(-1,2),axis=1)
        info['validation'].append(dict(path=str(path),sha256=all_hashes[str(path)],not_used_for_fitting=True,
            rms=float(np.sqrt(np.mean(error**2))),straightness_before_px=straightness(found['refined'],cfg['cols'],cfg['rows']),
            straightness_after_redetection_px=straightness(redetected['refined'],cfg['cols'],cfg['rows'])))
        validation_images.append((image,und))
    if manifest:
        trueK=np.array(manifest['true_K']);trueD=np.array(manifest['true_dist'])
        info['known_truth']=dict(true_K=trueK.tolist(),true_dist=trueD.tolist(),
            focal_relative_errors=[float(abs(K[i,i]-trueK[i,i])/trueK[i,i]) for i in (0,1)],
            principal_point_error_px=float(np.linalg.norm(K[:2,2]-trueK[:2,2])),
            distortion_coefficient_errors=(dist-trueD).tolist(),
            true_coverage=pose_coverage([v['rvec'] for v in manifest['calibration_views']]),
            actual_min_rendered_board_fraction=min(v['board_fraction'] for v in manifest['calibration_views']),
            solver_used_truth_as_input=False,manifest_sha256=sha256(folder/'source_manifest.json'))
    def check(name,expected,actual,passed):
        if not bool(passed):raise RuntimeError('正式验收失败：'+name+f'（实际{actual}）')
        info['checks'].append(dict(id=f'IT9-{len(info["checks"])+1:02d}',name=name,expected=expected,actual=actual,passed=True))
    check('可用棋盘格数量','>=15',len(detected),len(detected)>=cfg['min_views'])
    check('每张内角点数','cols*rows',cfg['cols']*cfg['rows'],all(x['refined'].shape[0]==len(obj) for x in detected))
    check('俯仰覆盖','>=30 deg',coverage['pitch_span_deg'],coverage['pitch_span_deg']>=cfg['min_pitch_span_deg'])
    check('偏航覆盖','>=30 deg',coverage['yaw_span_deg'],coverage['yaw_span_deg']>=cfg['min_yaw_span_deg'])
    check('棋盘画面占比','>=configured fraction',min(fractions),min(fractions)>=cfg['min_board_fraction'])
    check('标定RMS','< configured max_rms',calib['rms'],calib['rms']<cfg['max_rms'])
    check('去畸变角点直线度','decreases and <0.5px',info['straightness_mean_after_px'],
          straightness_accepted(info['straightness_mean_before_px'],info['straightness_mean_after_px']))
    if validation_images:
        check('未参与拟合的验证图','RMS<max and redetected lines improve',info['validation'],
              all(v['rms']<cfg['max_rms'] and straightness_accepted(v['straightness_before_px'],v['straightness_after_redetection_px']) for v in info['validation']))
    if manifest:
        check('已知合成K独立恢复','focal errors<2%; principal error<2px',info['known_truth']['focal_relative_errors'],
              max(info['known_truth']['focal_relative_errors'])<.02 and info['known_truth']['principal_point_error_px']<2)
    with LatestRun('lab9') as latest:
        info['pytest']=run_tests(latest.evidence)
        check('全项目测试','no failures/errors/skips',info['pytest']['tests'],not any(info['pytest'][k] for k in ('failures','errors','skipped')))
        visuals=[]
        for i,(image,found) in enumerate(zip(images,detected)):
            vis=cv2.cvtColor(image,cv2.COLOR_GRAY2BGR) if image.ndim==2 else image[:,:,:3].copy()
            cv2.drawChessboardCorners(vis,(cfg['cols'],cfg['rows']),found['refined'],True)
            save_png(latest.output/f'calib_detect_{i+1:02d}.png',vis);visuals.append(vis)
        save_png(latest.output/'l9_detection_overview.png',contact_sheet(visuals))
        first=images[0];und=undistort_image(first,K,dist)
        save_png(latest.output/'l9_distorted.png',first);save_png(latest.output/'l9_undistorted.png',und)
        save_png(latest.output/'l9_undistort_compare.png',np.hstack((first,und)))
        if validation_images:save_png(latest.output/'l9_validation_compare.png',np.hstack(validation_images[0]))
        fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
        axes[0].bar(np.arange(1,len(detected)+1),calib['per_view_rms']);axes[0].axhline(cfg['max_rms'],color='r',linestyle='--')
        axes[0].set(xlabel='View',ylabel='Reprojection RMS (px)',title='Subpixel calibration errors')
        axes[1].hist(np.concatenate(calib['corner_errors']),bins=35);axes[1].set(xlabel='Corner error (px)',ylabel='Count',title='All observed corner residuals')
        save_figure(latest.output/'l9_reprojection_errors.png',fig)
        fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
        a=np.array(coverage['pitch_yaw_deg']);axes[0].scatter(a[:,0],a[:,1]);axes[0].set(xlabel='Pitch of normal (deg)',ylabel='Yaw of normal (deg)',title='Estimated pose coverage')
        axes[1].plot(line_before,label='Distorted');axes[1].plot(line_after,label='Undistorted points');axes[1].legend();axes[1].set(xlabel='View',ylabel='Line RMS (px)',title='TLS row/column straightness')
        save_figure(latest.output/'l9_pose_and_straightness.png',fig)
        save_npy(latest.output/'K.npy',K);save_npy(latest.output/'dist.npy',dist)
        info['export_sha256']={n:sha256(latest.output/n) for n in ('K.npy','dist.npy')}
        buffer=io.BytesIO();np.savez_compressed(buffer,object_points=obj,raw_corners=np.stack(raw),refined_corners=np.stack(refined),
              rvecs=np.array(info['rvecs']),tvecs_mm=np.array(info['tvecs_mm']),per_corner_errors=np.stack(calib['corner_errors']))
        atomic_write(latest.evidence/'corners_and_poses.npz',buffer.getvalue())
        rows=[dict(file=Path(row['path']).name,view=i+1,rms=calib['per_view_rms'][i],board_fraction=fractions[i],
                   pitch_deg=coverage['pitch_yaw_deg'][i][0],yaw_deg=coverage['pitch_yaw_deg'][i][1],
                   straight_before=line_before[i],straight_after=line_after[i]) for i,row in enumerate(x for x in records if x['detected'])]
        write_csv(latest.evidence/'per_view_metrics.csv',list(rows[0]),rows)
        write_text(latest.evidence/'collection.json',json.dumps(records,ensure_ascii=False,indent=2))
        check('输入素材未变','all SHA256 unchanged',len(all_hashes),all(sha256(Path(p))==h for p,h in all_hashes.items()))
        with np.load(latest.evidence/'corners_and_poses.npz',allow_pickle=False) as saved:
            check('角点归档回读','N*63 observed corners',list(saved['refined_corners'].shape),np.array_equal(saved['refined_corners'],np.stack(refined)))
        pngs=list(latest.output.glob('*.png'));info['png_count']=len(pngs)
        check('全部PNG可回读','all PNG decoded',len(pngs),all(read_image(p).size>0 for p in pngs))
        info['elapsed_ms']=round((perf_counter()-start)*1000,3)
        text=json.dumps(info,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
        write_text(latest.output/'calib_result.json',text);write_text(latest.evidence/'results.json',text)
        load_calibration(latest.output,camera_id,size)
        report=report_text(info);plan=test_plan_text(info)
        write_text(latest.evidence/'lab_report.md',report.replace('../data/output/lab9_latest/','../../data/output/lab9_latest/'))
        write_text(latest.evidence/'test_plan_l9.md',plan)
        write_text(latest.evidence/'manifest.json',json.dumps({p.name:sha256(p) for p in latest.output.iterdir() if p.is_file()},indent=2))
        write_text(latest.evidence/'run.log','$ '+subprocess.list2cmdline([sys.executable,*sys.argv])+'\nSUCCESS: synthetic != physical camera\n')
        with result_exports(latest.output) as exports:
            load_calibration(exports,camera_id,size)
            write_text(latest.evidence/'export_verification.json',json.dumps(dict(passed=True,directory=str(exports),camera_id=camera_id)))
            latest.commit()
    write_text(ROOT/'docs/lab9_report.md',report);write_text(ROOT/'docs/test_plan_l9.md',plan)
    print(f'SUCCESS: lab9; detected={len(detected)}/{len(files)}; RMS={calib["rms"]:.6f}px; checks={len(info["checks"])}; PNG={len(pngs)}')
    print('K:\n'+np.array2string(K,precision=7));print('dist [k1,k2,p1,p2,k3]: '+np.array2string(dist,precision=8))
    print(('Synthetic model only. ' if manifest else 'Input camera identity remains user-declared. ')
          +'results/K.npy, results/dist.npy and calib_result.json exported with camera/size/hash metadata.')
    return info


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'config/lab9_images.json')
    parser.add_argument('--input-dir',type=Path)
    args=parser.parse_args()
    try:
        if sys.prefix==sys.base_prefix:raise ValueError('请使用项目虚拟环境')
        run(args.config,args.input_dir);return 0
    except (OSError,ValueError,TypeError,RuntimeError,cv2.error,subprocess.SubprocessError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
