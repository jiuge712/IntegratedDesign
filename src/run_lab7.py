"""Run BF/FLANN matching, reproducible human sampling and latest-only evidence."""
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
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from common import ROOT,VERSION,sha256,timestamp,write_text,atomic_write
from features import SIFT_DEFAULTS,sift_config,extract_sift,keypoint_records
from lab2_common import save_figure
from matching import (positive_integer,ratio_parameter,benchmark_matchers,nearest,filter_ratio,
                      mutual_nearest,symmetric_ratio,match_records)
from lab6_geometry import positive_number
from lab7_annotations import dataset_identifier,pair_id,random_sample,read_labels,error_estimate
from lab7_artifacts import load_photo,source_path,save_png,write_csv,annotation_artifacts
from lab7_report import report_text
from latest_runs import LatestRun
from version_check import environment

DEFAULTS={'image1':'data/input/seven-1.jpg','image2':'data/input/seven-2.jpg','max_input_side':0,
          'sift':SIFT_DEFAULTS,'ratio_thresholds':[0.6,0.75,0.9],'display_threshold':0.75,
          'max_distance':None,'distance_thresholds':[100.0,200.0,300.0],
          'sample_size':50,'sample_seed':7,'max_draw_matches':50,'benchmark_repeats':3,
          'flann_trees':5,'flann_checks':50,'labels':None}


def load_config(path):
    provided=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(provided,dict) or set(provided)-set(DEFAULTS):
        raise ValueError('实验七JSON配置包含未知字段或不是对象')
    cfg={**DEFAULTS,**provided}
    cfg['sift']=sift_config(cfg['sift'])
    for key in ('max_input_side','sample_seed'):
        positive_integer(cfg[key],key,0)
    for key in ('sample_size','max_draw_matches','benchmark_repeats','flann_trees','flann_checks'):
        positive_integer(cfg[key],key)
    if cfg['max_input_side'] and cfg['max_input_side']<16:
        raise ValueError('max_input_side为0或不小于16')
    if cfg['sample_seed']>2**31-1:
        raise ValueError('sample_seed超出OpenCV整数范围')
    if cfg['ratio_thresholds']!=[0.6,0.75,0.9]:
        raise ValueError('正式实验需ratio_thresholds=[0.6,0.75,0.9]')
    for value in cfg['ratio_thresholds']:
        ratio_parameter(value)
    if cfg['display_threshold'] not in cfg['ratio_thresholds']:
        raise ValueError('display_threshold必须属于三档阈值')
    if cfg['max_distance'] is not None:
        positive_number(cfg['max_distance'],'max_distance',zero=True)
    if not isinstance(cfg['distance_thresholds'],list) or not cfg['distance_thresholds']:
        raise ValueError('distance_thresholds需为非空列表')
    for value in cfg['distance_thresholds']:
        positive_number(value,'distance_threshold',zero=True)
    return cfg


def run_tests(directory):
    command=[sys.executable,'-X','utf8','-m','pytest','-v','--basetemp='+str(ROOT/'.tmp/pytest_lab7'),
             '--junitxml='+str(directory/'pytest.xml')]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=180)
    log='$ '+subprocess.list2cmdline(command)+'\n'+result.stdout+result.stderr
    write_text(directory/'pytest.log',log)
    if result.returncode:
        write_text(ROOT/'evidence/lab7_test_failure.log',log)
        raise RuntimeError('pytest未全部通过，见evidence/lab7_test_failure.log')
    suites=ET.parse(directory/'pytest.xml').getroot().findall('testsuite')
    count=sum(len(s.findall('testcase')) for s in suites)
    return {'tests':count,'subtests':sum(int(s.attrib.get('tests',0)) for s in suites)-count,
            **{key:sum(int(s.attrib.get(key,0)) for s in suites) for key in ('failures','errors','skipped')},
            'command':command,'basetemp':str(ROOT/'.tmp/pytest_lab7')}


def draw_subset(image1,kp1,image2,kp2,matches,limit,seed,color):
    ordered=sorted(matches,key=lambda m:(m.queryIdx,m.trainIdx))
    chosen=np.random.default_rng(seed).choice(len(ordered),min(limit,len(ordered)),replace=False)
    drawn=[ordered[i] for i in sorted(chosen)]
    return cv2.drawMatches(image1,kp1,image2,kp2,drawn,None,matchColor=color,
                           flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)


def panel(path,items,columns):
    rows=(len(items)+columns-1)//columns
    fig,axes=plt.subplots(rows,columns,figsize=(12,4.8*rows) if columns==1 else (6*columns,3.6*rows),squeeze=False,layout='constrained')
    for ax,(title,image) in zip(axes.flat,items):
        ax.imshow(cv2.cvtColor(image,cv2.COLOR_BGR2RGB))
        ax.set_title(title,fontsize=10)
        ax.axis('off')
    for ax in list(axes.flat)[len(items):]:
        ax.axis('off')
    save_figure(path,fig)


def run(config_path,image1_override=None,image2_override=None,labels_override=None):
    start=perf_counter()
    cfg=load_config(config_path)
    image1,source1=load_photo(image1_override or cfg['image1'],cfg['max_input_side'])
    image2,source2=load_photo(image2_override or cfg['image2'],cfg['max_input_side'])
    kp1,desc1=extract_sift(image1,cfg['sift'])
    kp2,desc2=extract_sift(image2,cfg['sift'])
    keypoints={'image1':keypoint_records(kp1),'image2':keypoint_records(kp2)}
    fingerprint=dataset_identifier([source1,source2],{'sift':cfg['sift'],'opencv':cv2.__version__},keypoints,[desc1,desc2])
    label_value=labels_override or cfg['labels']
    label_path=source_path(label_value) if label_value else None
    labels=read_labels(label_path,fingerprint,len(kp1),len(kp2))
    label_hash=sha256(label_path) if label_path else None
    datasets,benchmark=benchmark_matchers(desc1,desc2,cfg['benchmark_repeats'],cfg['flann_trees'],cfg['flann_checks'],cfg['sample_seed'])
    forward,backward=datasets['bf']
    first=nearest(forward)
    records=match_records(forward)
    by_query={row['query_index']:row for row in records}
    info={'status':'SUCCESS','time':timestamp(),'program_version':VERSION,'environment':environment(),
          'parameters':cfg,'sources':{'image1':source1,'image2':source2},'dataset_id':fingerprint,
          'feature_counts':{'image1':len(kp1),'image2':len(kp2)},
          'descriptor_shapes':{'image1':list(desc1.shape),'image2':list(desc2.shape)},
          'raw':{'queries':len(forward),'nearest_count':len(first),'complete_pairs':sum(len(p)==2 for p in forward)},
          'thresholds':[],'benchmark':benchmark,'distance_experiment':[],'checks':[],
          'labels_source':str(label_path) if label_path else None,'labels_sha256':label_hash}
    match_json={'bf_forward':records,'bf_reverse':match_records(backward),'stages':{},'flann_forward':match_records(datasets['flann'][0])}
    manifest={'dataset_id':fingerprint,'sources':[source1,source2],'sampling':'uniform without replacement, separate seeded stream per threshold',
              'sample_seed':cfg['sample_seed'],'sample_size':cfg['sample_size'],'population_stage':'symmetric_ratio','groups':[],'pairs':[]}
    sampled_union={}
    groups={}
    for threshold in cfg['ratio_thresholds']:
        ratio=filter_ratio(forward,threshold,cfg['max_distance'])
        mutual=mutual_nearest(ratio,backward)
        final=symmetric_ratio(forward,backward,threshold,cfg['max_distance'])
        selected=random_sample(final,threshold,cfg['sample_size'],cfg['sample_seed'])
        info['thresholds'].append({'threshold':threshold,'ratio_count':len(ratio),'mutual_nearest_count':len(mutual),
                                   'symmetric_ratio_count':len(final),'retained_fraction':len(final)/len(first) if first else 0.0,
                                   'human':error_estimate(selected,fingerprint,labels)})
        groups[threshold]=(ratio,mutual,final,selected)
        match_json['stages'][str(threshold)]={name:[[int(m.queryIdx),int(m.trainIdx),float(m.distance)] for m in values]
                                            for name,values in [('ratio',ratio),('mutual_nearest',mutual),('symmetric_ratio',final)]}
        ids=[]
        for match in selected:
            pid=pair_id(fingerprint,match.queryIdx,match.trainIdx)
            ids.append(pid)
            sampled_union[pid]={'pair_id':pid,'query_index':int(match.queryIdx),'train_index':int(match.trainIdx),
                                'xy1':list(kp1[match.queryIdx].pt),'xy2':list(kp2[match.trainIdx].pt),
                                'ratio':by_query[match.queryIdx]['ratio']}
        manifest['groups'].append({'threshold':threshold,'population_count':len(final),'pair_ids':ids})
    manifest['pairs']=sorted(sampled_union.values(),key=lambda row:(row['query_index'],row['train_index']))
    info['annotation_unique_pairs']=len(manifest['pairs'])
    for distance in cfg['distance_thresholds']:
        info['distance_experiment'].append({'max_distance':distance,'count':len(symmetric_ratio(forward,backward,cfg['display_threshold'],distance))})
    flann_forward,flann_backward=datasets['flann']
    a={(m.queryIdx,m.trainIdx) for m in groups[cfg['display_threshold']][2]}
    b={(m.queryIdx,m.trainIdx) for m in symmetric_ratio(flann_forward,flann_backward,cfg['display_threshold'],cfg['max_distance'])}
    flann_first={m.queryIdx:m.trainIdx for m in nearest(flann_forward)}
    comparable=[m for m in first if m.queryIdx in flann_first]
    info['backend_agreement']={'nearest_index_agreement':sum(m.trainIdx==flann_first[m.queryIdx] for m in comparable)/len(comparable) if comparable else None,
                               'symmetric_pair_jaccard':len(a&b)/len(a|b) if a|b else 1.0}
    with LatestRun('lab7') as latest:
        info['pytest']=run_tests(latest.evidence)
        save_png(latest.output/'image1_work.png',image1)
        save_png(latest.output/'image2_work.png',image2)
        panel(latest.output/'l7_inputs_keypoints.png',[
            (f'Image1: {len(kp1)} SIFT',cv2.drawKeypoints(image1,kp1,None,color=(230,120,20),flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)),
            (f'Image2: {len(kp2)} SIFT',cv2.drawKeypoints(image2,kp2,None,color=(230,120,20),flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS))],2)
        ratio,mutual,final,_=groups[cfg['display_threshold']]
        pictures=[]
        for name,title,matches,color in [('raw','Before: nearest candidates',first,(150,150,150)),
                                        ('ratio','Forward ratio',ratio,(230,120,20)),
                                        ('symmetric','Bidirectional ratio',final,(230,120,20))]:
            drawn=draw_subset(image1,kp1,image2,kp2,matches,cfg['max_draw_matches'],cfg['sample_seed'],color)
            save_png(latest.output/f'l7_matches_{name}.png',drawn)
            pictures.append((f'{title}: {len(matches)} total',drawn))
        panel(latest.output/'l7_before_after.png',pictures,1)
        fig,ax=plt.subplots(figsize=(8,4),layout='constrained')
        xx=np.arange(len(info['thresholds']))
        for offset,key,title in [(-0.25,'ratio_count','Forward ratio'),(0,'mutual_nearest_count','Mutual nearest'),(0.25,'symmetric_ratio_count','Bidirectional ratio')]:
            ax.bar(xx+offset,[row[key] for row in info['thresholds']],width=0.25,label=title)
        ax.set_xticks(xx,[str(row['threshold']) for row in info['thresholds']])
        ax.set(xlabel='Ratio threshold',ylabel='Matches',title='Counts do not measure correctness')
        ax.legend()
        save_figure(latest.output/'l7_threshold_counts.png',fig)
        fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
        values=[row['ratio'] for row in records if row['ratio'] is not None]
        axes[0].hist(values,bins=np.linspace(0,1,41),color='#4477aa')
        for threshold in cfg['ratio_thresholds']:
            axes[0].axvline(threshold,label=str(threshold),linestyle='--')
        axes[0].set(xlabel='d1/d2',ylabel='Queries',title='BF nearest / second nearest')
        axes[0].legend()
        axes[1].hist([row['distance1'] for row in records],bins=40,color='#cc8844')
        axes[1].set(xlabel='SIFT L2 nearest distance',ylabel='Queries',title='Absolute distance')
        save_figure(latest.output/'l7_ratio_distribution.png',fig)
        annotation_artifacts(latest.output,latest.evidence,manifest,image1,image2,labels)
        # Correct/incorrect colors are used only for externally supplied human labels.
        for threshold,(_,_,_,sample) in groups.items():
            decisive=[m for m in sample if labels.get(pair_id(fingerprint,m.queryIdx,m.trainIdx),{}).get('label') in ('correct','incorrect')]
            if decisive:
                result=np.zeros((max(image1.shape[0],image2.shape[0]),image1.shape[1]+image2.shape[1],3),np.uint8)
                result[:image1.shape[0],:image1.shape[1]]=image1
                result[:image2.shape[0],image1.shape[1]:]=image2
                for match in decisive:
                    color=(0,200,0) if labels[pair_id(fingerprint,match.queryIdx,match.trainIdx)]['label']=='correct' else (0,0,255)
                    p=tuple(int(round(v)) for v in kp1[match.queryIdx].pt)
                    q=tuple(int(round(v)) for v in kp2[match.trainIdx].pt)
                    cv2.line(result,p,(q[0]+image1.shape[1],q[1]),color,1,cv2.LINE_AA)
                save_png(latest.output/f'l7_human_labeled_{threshold:g}.png',result)
        buffer=io.BytesIO()
        np.savez_compressed(buffer,image1_descriptors=desc1,image2_descriptors=desc2)
        atomic_write(latest.evidence/'descriptors.npz',buffer.getvalue())
        for filename,content in [('keypoints.json',keypoints),('matches.json',match_json)]:
            write_text(latest.evidence/filename,json.dumps(content,ensure_ascii=False,indent=2,allow_nan=False))
        if label_path:
            atomic_write(latest.evidence/'labels_used.csv',label_path.read_bytes())
        rows=[{'threshold':row['threshold'],'ratio_count':row['ratio_count'],'mutual_nearest_count':row['mutual_nearest_count'],
               'symmetric_ratio_count':row['symmetric_ratio_count'],'retained_fraction':row['retained_fraction'],
               **{key:row['human'][key] for key in ('sample_count','decisive_count','incorrect','error_rate','course_50_pairs_complete')}} for row in info['thresholds']]
        write_csv(latest.evidence/'metrics.csv',list(rows[0]),rows)
        def check(name,passed):
            if not bool(passed):
                raise RuntimeError('正式检查失败: '+name)
            info['checks'].append({'name':name,'passed':True})
        check('pytest全部通过无跳过',not any(info['pytest'][key] for key in ('failures','errors','skipped')))
        check('两图描述子N×128与关键点逐行对应',desc1.shape==(len(kp1),128) and desc2.shape==(len(kp2),128))
        check('前后向KNN覆盖全部查询',len(forward)==len(kp1) and len(backward)==len(kp2))
        check('所有匹配索引合法',all(0<=r['query_index']<len(kp1) and 0<=r['train_index']<len(kp2) for r in records))
        check('三阶段提纯关系自洽',all(row['symmetric_ratio_count']<=row['mutual_nearest_count']<=row['ratio_count']<=len(first) for row in info['thresholds']))
        check('阈值增大时接受集合不减',all(info['thresholds'][i]['symmetric_ratio_count']<=info['thresholds'][i+1]['symmetric_ratio_count'] for i in (0,1)))
        check('抽样不重复且属于对应最终集合',all(len({(m.queryIdx,m.trainIdx) for m in sample})==len(sample) and all((m.queryIdx,m.trainIdx) in {(v.queryIdx,v.trainIdx) for v in finals} for m in sample) for _,_,finals,sample in groups.values()))
        check('无标签不伪造误匹配率',all(row['human']['error_rate'] is None for row in info['thresholds']) if not labels else True)
        check('人工样本数和误率分母自洽',all(row['human']['decisive_count']<=row['human']['sample_count']<=cfg['sample_size'] and (row['human']['error_rate'] is None or 0<=row['human']['error_rate']<=1) for row in info['thresholds']))
        with np.load(latest.evidence/'descriptors.npz',allow_pickle=False) as saved:
            check('描述子归档回读一致',np.array_equal(saved['image1_descriptors'],desc1) and np.array_equal(saved['image2_descriptors'],desc2))
        pngs=list(latest.output.glob('*.png'))
        check('全部PNG可回读',bool(pngs) and all(cv2.imdecode(np.frombuffer(p.read_bytes(),np.uint8),cv2.IMREAD_UNCHANGED) is not None for p in pngs))
        check('标注页面和模板已生成',(latest.output/'annotate.html').is_file() and (latest.output/'labels_template.csv').is_file())
        check('原始两张照片哈希不变',all(sha256(Path(source['path']))==source['sha256'] for source in (source1,source2)))
        check('持久人工标签不被覆盖',not label_path or sha256(label_path)==label_hash)
        info['png_count']=len(pngs)
        info['elapsed_ms']=round((perf_counter()-start)*1000,3)
        write_text(latest.evidence/'results.json',json.dumps(info,ensure_ascii=False,indent=2,allow_nan=False))
        write_text(latest.evidence/'manifest.json',json.dumps({p.name:sha256(p) for p in latest.output.iterdir() if p.is_file()},indent=2))
        write_text(latest.evidence/'run.log','$ '+subprocess.list2cmdline([sys.executable,*sys.argv])+'\nSUCCESS: automatic checks passed; human tasks tracked separately\n')
        report=report_text(info)
        write_text(latest.evidence/'lab_report.md',report.replace('../data/output/lab7_latest/','../../data/output/lab7_latest/'))
        latest.commit()
    write_text(ROOT/'docs/lab7_report.md',report)
    print(f'SUCCESS: lab7; SIFT={len(kp1)}/{len(kp2)}; pytest {info["pytest"]["tests"]}+{info["pytest"]["subtests"]}; checks={len(info["checks"])}; PNG={len(pngs)}')
    for row in info['thresholds']:
        print(f'ratio={row["threshold"]}: forward={row["ratio_count"]}, mutual={row["mutual_nearest_count"]}, symmetric={row["symmetric_ratio_count"]}, human={row["human"]["decisive_count"]}/{row["human"]["sample_count"]}')
    return info


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'config/lab7_images.json')
    parser.add_argument('--image1',type=Path)
    parser.add_argument('--image2',type=Path)
    parser.add_argument('--labels',type=Path,help='持久人工标注CSV，不放输出/证据目录')
    args=parser.parse_args()
    try:
        if sys.prefix==sys.base_prefix:
            raise ValueError('请使用项目虚拟环境')
        run(args.config,args.image1,args.image2,args.labels)
        return 0
    except (OSError,ValueError,TypeError,RuntimeError,cv2.error,subprocess.SubprocessError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
