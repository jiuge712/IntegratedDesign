"""SIFT extraction, controlled parameter sweeps and known-transform verification."""
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

from baseline_pipeline import read_image
from common import ROOT, VERSION, atomic_write, sha256, timestamp, write_text
from features import SIFT_DEFAULTS, extract_sift, sift_config, keypoint_records
from lab2_common import save_figure
from lab6_geometry import positive_number, transform_full_canvas, project_xy, ratio_matches, match_statistics
from latest_runs import LatestRun
from version_check import environment
from lab6_report import report_text

DEFAULTS = {
    'input':'data/input/uneven_real.jpg', 'max_input_side':1600, 'sift':SIFT_DEFAULTS,
    'nfeatures_values':[0,300,800], 'contrast_thresholds':[0.04,0.01,0.08],
    'edge_thresholds':[5.0,10.0,20.0], 'rotation_degrees':30.0, 'scale_factor':0.6,
    'ratio_threshold':0.75, 'geometry_tolerance_px':3.0, 'max_draw_matches':50,
}


def integer(value,name,minimum=0):
    if isinstance(value,bool) or not isinstance(value,int) or value < minimum:
        raise ValueError(f'{name} 必须为不小于 {minimum} 的整数')
    return value


def load_config(path):
    provided = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(provided,dict) or set(provided)-set(DEFAULTS):
        raise ValueError('实验六配置应为已约定字段的 JSON 对象，不接受未知键')
    cfg = {**DEFAULTS,**provided}
    cfg['sift'] = sift_config(cfg['sift'])
    integer(cfg['max_input_side'],'max_input_side')
    if 0 < cfg['max_input_side'] < 16:
        raise ValueError('max_input_side 设0保持原尺寸，或使用不小于16的值')
    integer(cfg['max_draw_matches'],'max_draw_matches',1)
    positive_number(cfg['scale_factor'],'scale_factor')
    positive_number(cfg['geometry_tolerance_px'],'geometry_tolerance_px')
    angle = cfg['rotation_degrees']
    if isinstance(angle,(str,bool)) or not np.isscalar(angle) or not np.isfinite(angle):
        raise ValueError('rotation_degrees 必须有限')
    ratio_matches(np.empty((0,128),np.float32),np.empty((0,128),np.float32),cfg['ratio_threshold'])
    for key,parameter in [('nfeatures_values','nfeatures'),('contrast_thresholds','contrastThreshold'),('edge_thresholds','edgeThreshold')]:
        if not isinstance(cfg[key],list) or len(cfg[key]) < 2:
            raise ValueError(f'{key} 至少提供两个参数值进行对比')
        for value in cfg[key]:
            sift_config({**cfg['sift'],parameter:value})
    return cfg


def load_input(value,max_side):
    path = Path(value)
    path = (path if path.is_absolute() else ROOT/path).resolve()
    if any(path.is_relative_to((ROOT/folder).resolve()) for folder in ('data/output','evidence','docs')):
        raise ValueError('原图不能放在输出、证据或文档目录')
    digest = sha256(path)
    image = read_image(path)
    if image.dtype != np.uint8 or min(image.shape[:2]) < 16:
        raise ValueError('实验六正式输入要求 uint8 且宽高至少16')
    original_shape = list(image.shape)
    if image.ndim == 2:
        image = cv2.cvtColor(image,cv2.COLOR_GRAY2BGR)
    elif image.shape[2] == 4:
        image = image[:,:,:3].copy()
    h,w = image.shape[:2]
    factor = min(1.0,max_side/max(h,w)) if max_side else 1.0
    if factor < 1:
        width,height = max(1,round(w*factor)),max(1,round(h*factor))
        if min(width,height)<16:
            raise ValueError('等比缩放后最短边不足16，请提高max_input_side或设0保持原尺寸')
        image = cv2.resize(image,(width,height),interpolation=cv2.INTER_AREA)
    sx,sy = image.shape[1]/w,image.shape[0]/h
    source_to_work = np.array([[sx,0,(sx-1)/2],[0,sy,(sy-1)/2]],np.float64)
    return image, {'path':str(path),'sha256':digest,'original_shape':original_shape,
                   'working_shape':list(image.shape),'source_to_work_pixel_centers':source_to_work.tolist(),
                   'resize_interpolation':'INTER_AREA' if factor<1 else 'none',
                   'alpha_policy':'discard without compositing' if len(original_shape)==3 and original_shape[2]==4 else 'not present'}


def save_png(path,image):
    ok,encoded = cv2.imencode('.png',image)
    if not ok:
        raise OSError(f'PNG 编码失败: {path}')
    atomic_write(path,encoded.tobytes())
    if not np.array_equal(read_image(path),image):
        raise OSError(f'PNG 无损回读失败: {path}')


def panels(path,items,columns=3):
    rows = (len(items)+columns-1)//columns
    fig,axes = plt.subplots(rows,columns,figsize=(5*columns,4*rows),squeeze=False,layout='constrained')
    for axis,(title,image) in zip(axes.flat,items):
        axis.imshow(cv2.cvtColor(image,cv2.COLOR_BGR2RGB) if image.ndim==3 else image,cmap='gray',vmin=0,vmax=255)
        axis.set_title(title,fontsize=10)
        axis.axis('off')
    for axis in list(axes.flat)[len(items):]:
        axis.axis('off')
    save_figure(path,fig)


def rich_keypoints(image,points):
    return cv2.drawKeypoints(image,points,None,color=(0,255,0),flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)


def point_statistics(points,desc):
    sizes = [p.size for p in points]
    angles = [p.angle for p in points]
    return {'count':len(points),'descriptor_shape':list(desc.shape),'descriptor_dtype':str(desc.dtype),
            'size_min':float(min(sizes)) if sizes else None,'size_median':float(np.median(sizes)) if sizes else None,
            'size_max':float(max(sizes)) if sizes else None,
            'angle_histogram_10deg':np.histogram(angles,bins=np.arange(0,361,10))[0].tolist()}


def run_pytest(directory):
    command = [sys.executable,'-X','utf8','-m','pytest','-v',
               '--basetemp='+str(ROOT/'.tmp/pytest_lab6'),'--junitxml='+str(directory/'pytest.xml')]
    result = subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=180)
    text = '$ '+subprocess.list2cmdline(command)+'\n'+result.stdout+result.stderr
    write_text(directory/'pytest.log',text)
    if result.returncode:
        write_text(ROOT/'evidence/lab6_test_failure.log',text)
        raise RuntimeError('pytest 未通过，见 evidence/lab6_test_failure.log')
    suites = ET.parse(directory/'pytest.xml').getroot().findall('testsuite')
    total = sum(int(s.attrib.get('tests',0)) for s in suites)
    count = sum(len(s.findall('testcase')) for s in suites)
    return {'tests':count,'subtests':total-count,'failures':sum(int(s.attrib.get('failures',0)) for s in suites),
            'errors':sum(int(s.attrib.get('errors',0)) for s in suites),'skipped':sum(int(s.attrib.get('skipped',0)) for s in suites),
            'returncode':result.returncode,'command':command,'basetemp':str(ROOT/'.tmp/pytest_lab6')}


def rose(path,vector,title,maximum):
    fig,axes = plt.subplots(4,4,figsize=(8,8),subplot_kw={'projection':'polar'},layout='constrained')
    grid = vector.reshape(4,4,8)
    for row in range(4):
        for column in range(4):
            axis = axes[row,column]
            axis.bar(np.arange(8)*np.pi/4,grid[row,column],width=np.pi/5,color='#4477aa')
            axis.set_ylim(0,max(maximum,1))
            axis.set_theta_direction(-1)
            axis.set_xticks(np.arange(8)*np.pi/4)
            axis.set_xticklabels(['0','45','90','135','180','225','270','315'],fontsize=6)
            axis.set_yticklabels([])
            axis.set_title(f'cell ({row},{column})',fontsize=9)
    fig.suptitle(title,fontsize=12)
    save_figure(path,fig)


def run(config_path,input_override=None):
    start = perf_counter()
    cfg = load_config(config_path)
    image,source = load_input(input_override or cfg['input'],cfg['max_input_side'])
    cache = {}
    def extract(parameters):
        params = sift_config(parameters)
        key = json.dumps(params,sort_keys=True)
        if key not in cache:
            begin = perf_counter()
            points,desc = extract_sift(image,params)
            cache[key] = (points,desc,round((perf_counter()-begin)*1000,4))
        return cache[key]
    points,descriptors,elapsed = extract(cfg['sift'])
    statistics = point_statistics(points,descriptors)
    statistics['elapsed_ms'] = elapsed
    sweep = []
    contrast_panels = []
    for group,parameter in [('nfeatures_values','nfeatures'),('contrast_thresholds','contrastThreshold'),('edge_thresholds','edgeThreshold')]:
        for value in cfg[group]:
            params = {**cfg['sift'],parameter:value}
            found,desc,duration = extract(params)
            sweep.append({'group':parameter,'value':value,'count':len(found),'elapsed_ms':duration,'parameters':sift_config(params),
                          'size_median':float(np.median([p.size for p in found])) if found else None})
            if parameter == 'contrastThreshold':
                contrast_panels.append((f'contrast={value}: {len(found)} keypoints',rich_keypoints(image,found)))
    info = {'time':timestamp(),'program_version':VERSION,'environment':environment(),'source':source,
            'parameters':cfg,'original_features':statistics,'parameter_experiments':sweep,
            'unique_parameter_extractions':len(cache),'transforms':[],'checks':[],'descriptor_examples':[]}
    keypoints_json = {'original':keypoint_records(points)}
    matches_json = {}
    raw = {'original_descriptors':descriptors}
    for key,(found,desc,_) in cache.items():
        raw[f'sweep_{list(cache).index(key)}_descriptors'] = desc
    specifications = [('rotation',cfg['rotation_degrees'],1.0),('scale',0.0,cfg['scale_factor']),
                      ('combined',cfg['rotation_degrees'],cfg['scale_factor'])]
    transformed_items = []
    with LatestRun('lab6') as latest:
        info['pytest'] = run_pytest(latest.evidence)
        save_png(latest.output/'working_input.png',image)
        save_png(latest.output/'l6_keypoints.png',rich_keypoints(image,points))
        for name,angle,scale in specifications:
            transformed,matrix = transform_full_canvas(image,angle,scale)
            begin = perf_counter()
            target,desc2 = extract_sift(transformed,cfg['sift'])
            duration = round((perf_counter()-begin)*1000,4)
            good,pairs = ratio_matches(descriptors,desc2,cfg['ratio_threshold'])
            metric,records = match_statistics(points,target,good,matrix,cfg['geometry_tolerance_px'])
            row = {'name':name,'rotation_degrees':angle,'scale_factor':scale,'shape':list(transformed.shape),
                   'matrix_work_to_transformed':matrix.tolist(),'complete_knn_pairs':pairs,
                   'extraction_elapsed_ms':duration,'target_features':point_statistics(target,desc2),**metric,
                   'drawn_matches':min(len(good),cfg['max_draw_matches'])}
            info['transforms'].append(row)
            keypoints_json[name] = keypoint_records(target)
            matches_json[name] = records
            raw[name+'_descriptors'] = desc2
            raw[name+'_matrix'] = matrix
            save_png(latest.output/f'{name}.png',transformed)
            save_png(latest.output/f'{name}_keypoints.png',rich_keypoints(transformed,target))
            drawn = cv2.drawMatches(image,points,transformed,target,good[:cfg['max_draw_matches']],None,
                                   matchColor=(0,255,0),flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
            save_png(latest.output/f'l6_matches_{name}.png',drawn)
            transformed_items.append((f'{name}: {angle:g} deg, {scale:g}x',transformed))
        panels(latest.output/'l6_transform_compare.png',[('Working input',image),*transformed_items],2)
        panels(latest.output/'l6_contrast_keypoints.png',contrast_panels)
        fig,axes = plt.subplots(1,3,figsize=(13,4),layout='constrained')
        for axis,parameter in zip(axes,['nfeatures','contrastThreshold','edgeThreshold']):
            rows = [row for row in sweep if row['group']==parameter]
            axis.bar([str(row['value']) for row in rows],[row['count'] for row in rows],color='#4477aa')
            axis.set(xlabel=parameter,ylabel='Keypoints',title='Vary '+parameter)
        save_figure(latest.output/'l6_parameter_counts.png',fig)
        fig,axes = plt.subplots(1,2,figsize=(10,4),layout='constrained')
        axes[0].hist([p.size for p in points],bins=30,color='#4477aa')
        axes[0].set(xlabel='KeyPoint.size (diameter, work pixels)',ylabel='Count',title='Scale distribution')
        axes[1].hist([p.angle for p in points],bins=np.arange(0,361,10),color='#ee9944')
        axes[1].set(xlabel='Angle (degrees)',ylabel='Count',title='Orientation distribution',xlim=(0,360))
        save_figure(latest.output/'l6_distributions.png',fig)
        if points:
            first = max(range(len(points)),key=lambda i:points[i].response)
            separated = [i for i in range(len(points)) if np.linalg.norm(np.array(points[i].pt)-points[first].pt)>0.1*max(image.shape[:2])]
            selected = [first]
            if separated:
                selected.append(max(separated,key=lambda i:float(np.linalg.norm(descriptors[i]-descriptors[first]))))
            maximum = float(descriptors[selected].max())
            for index,point_index in enumerate(selected,1):
                point = points[point_index]
                info['descriptor_examples'].append({'example':index,'keypoint_index':point_index,**keypoint_records([point])[0]})
                rose(latest.output/f'l6_descriptor_{index}.png',descriptors[point_index],f'SIFT descriptor {index}: 4 x 4 cells x 8 bins',maximum)
            fig,axes = plt.subplots(len(selected),1,figsize=(12,3*len(selected)),squeeze=False,layout='constrained')
            for axis,point_index in zip(axes.flat,selected):
                axis.bar(np.arange(128),descriptors[point_index],color='#4477aa',width=1)
                axis.set(xlabel='Descriptor bin (cell-major, 8 orientations per cell)',ylabel='Stored value',title=f'Keypoint row {point_index}',ylim=(0,max(maximum*1.1,1)))
            save_figure(latest.output/'l6_descriptor_compare.png',fig)
        archive = io.BytesIO()
        np.savez_compressed(archive,**raw)
        atomic_write(latest.evidence/'features.npz',archive.getvalue())
        for filename,content in [('keypoints.json',keypoints_json),('matches.json',matches_json)]:
            write_text(latest.evidence/filename,json.dumps(content,ensure_ascii=False,indent=2,allow_nan=False))
        buffer = io.StringIO(newline='')
        writer = csv.DictWriter(buffer,fieldnames=['group','value','count','elapsed_ms','size_median'])
        writer.writeheader()
        writer.writerows({key:row[key] for key in writer.fieldnames} for row in sweep)
        write_text(latest.evidence/'parameters.csv',buffer.getvalue())
        buffer = io.StringIO(newline='')
        fields = ['name','source_keypoints','target_keypoints','ratio_passed','ratio_passed_per_source','geometry_consistent','geometry_consistent_per_source','geometry_consistent_per_match','median_reprojection_error_px','unique_train_indices','drawn_matches']
        writer = csv.DictWriter(buffer,fieldnames=fields)
        writer.writeheader()
        writer.writerows({key:row[key] for key in fields} for row in info['transforms'])
        write_text(latest.evidence/'invariance.csv',buffer.getvalue())
        def check(name,passed):
            if not bool(passed):
                raise RuntimeError('正式检查失败: '+name)
            info['checks'].append({'name':name,'passed':True})
        check('pytest 全部通过且无跳过',info['pytest']['tests']>0 and not any(info['pytest'][key] for key in ('failures','errors','skipped')))
        check('原图特征与 N×128 float32 描述子对应',descriptors.shape==(len(points),128) and descriptors.dtype==np.float32)
        check('原图关键点位置、尺度及方向合法',all(0<=p.pt[0]<image.shape[1] and 0<=p.pt[1]<image.shape[0] and p.size>0 and 0<=p.angle<360 for p in points))
        check('参数实验覆盖三个独立参数',{row['group'] for row in sweep}=={'nfeatures','contrastThreshold','edgeThreshold'})
        check('三种已知变换均完成描述子提取',len(info['transforms'])==3 and all(raw[row['name']+'_descriptors'].shape==(row['target_keypoints'],128) for row in info['transforms']))
        check('匹配全部描述子且结果计数自洽',all(row['ratio_passed']<=row['complete_knn_pairs']<=len(points) and row['geometry_consistent']<=row['ratio_passed'] and row['drawn_matches']<=cfg['max_draw_matches'] for row in info['transforms']))
        check('匹配索引与已知几何误差有效',all(0<=r['query_index']<len(points) and 0<=r['train_index']<row['target_keypoints'] and np.isfinite(r['reprojection_error_px']) for row in info['transforms'] for r in matches_json[row['name']]))
        check('变换画布包含源图四个边界角',all(np.all(project_xy(np.array([[0,0],[image.shape[1],0],[0,image.shape[0]],[image.shape[1],image.shape[0]]]),raw[row['name']+'_matrix'])>=-1e-7) and np.all(project_xy(np.array([[0,0],[image.shape[1],0],[0,image.shape[0]],[image.shape[1],image.shape[0]]]),raw[row['name']+'_matrix'])<=np.array([row['shape'][1],row['shape'][0]])+1e-7) for row in info['transforms']))
        check('特征归档均为有限数值',all(np.isfinite(value).all() for value in raw.values()))
        with np.load(latest.evidence/'features.npz',allow_pickle=False) as saved:
            check('NPZ 回读描述子和变换矩阵一致',set(saved.files)==set(raw) and all(np.array_equal(saved[key],value) for key,value in raw.items()))
        pngs = list(latest.output.glob('*.png'))
        check('全部 PNG 可回读',bool(pngs) and all(read_image(path).size>0 for path in pngs))
        check('原始输入 SHA-256 保持不变',sha256(Path(source['path']))==source['sha256'])
        info['png_count'] = len(pngs)
        info['elapsed_ms'] = round((perf_counter()-start)*1000,3)
        info['status'] = 'SUCCESS'
        write_text(latest.evidence/'results.json',json.dumps(info,ensure_ascii=False,indent=2,allow_nan=False))
        write_text(latest.evidence/'manifest.json',json.dumps({path.name:sha256(path) for path in pngs},indent=2))
        write_text(latest.evidence/'run.log','$ '+subprocess.list2cmdline([sys.executable,*sys.argv])+'\nSUCCESS\n')
        report = report_text(info)
        write_text(latest.evidence/'lab_report.md',report.replace('../data/output/lab6_latest/','../../data/output/lab6_latest/'))
        latest.commit()
    write_text(ROOT/'docs/lab6_report.md',report)
    print(f'SUCCESS: lab6; {len(points)} keypoints; descriptors={descriptors.shape}; PNG={len(pngs)}; checks={len(info["checks"])}')
    print(f'pytest: {info["pytest"]["tests"]} tests + {info["pytest"]["subtests"]} subtests')
    for row in info['transforms']:
        print(f'{row["name"]}: ratio_passed={row["ratio_passed"]} ({row["ratio_passed_per_source"]:.3%}), geometry_consistent={row["geometry_consistent"]}')
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'config/lab6_images.json')
    parser.add_argument('--input',type=Path,help='覆盖个人图片路径')
    args = parser.parse_args()
    try:
        if sys.prefix==sys.base_prefix:
            raise ValueError('请使用项目独立虚拟环境')
        run(args.config,args.input)
        return 0
    except (OSError,ValueError,TypeError,RuntimeError,cv2.error,subprocess.SubprocessError) as exc:
        print(f'ERROR: {exc}',file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
