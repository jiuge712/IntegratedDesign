"""Reproducible random samples and validated human labels, with no invented truth."""
from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

FIELDS=['dataset_id','pair_id','query_index','train_index','label','reviewer','note']


def dataset_identifier(sources,parameters,keypoint_rows,descriptors):
    digest=hashlib.sha256(json.dumps({'sources':sources,'parameters':parameters,'keypoints':keypoint_rows},
                                    sort_keys=True,ensure_ascii=False,allow_nan=False).encode())
    for desc in descriptors:
        digest.update(np.ascontiguousarray(desc).tobytes())
    return digest.hexdigest()


def pair_id(dataset_id,query_index,train_index):
    return f'{dataset_id[:16]}-q{query_index}-t{train_index}'


def random_sample(matches,threshold,size=50,seed=7):
    ordered=sorted(matches,key=lambda m:(m.queryIdx,m.trainIdx))
    # Separate deterministic stream per threshold; independent of OpenCV match ordering.
    stream=np.random.default_rng(np.random.SeedSequence([seed,int(round(threshold*1_000_000))]))
    indices=stream.choice(len(ordered),size=min(size,len(ordered)),replace=False)
    return [ordered[i] for i in sorted(indices)]


def read_labels(path:Path|None,dataset_id,query_count,train_count)->dict:
    if path is None:
        return {}
    labels={}
    with path.open('r',encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        if reader.fieldnames!=FIELDS:
            raise ValueError('标注CSV表头必须为 '+','.join(FIELDS))
        for number,row in enumerate(reader,2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f'标注第{number}行CSV列数不匹配，请保留完整七列')
            if row['dataset_id']!=dataset_id:
                raise ValueError(f'标注第{number}行来源不匹配；换图/提取参数后请使用新模板，不沿用旧标签')
            try:
                query,train=int(row['query_index']),int(row['train_index'])
            except (TypeError,ValueError):
                raise ValueError(f'标注第{number}行索引必须为整数') from None
            if not (0<=query<query_count and 0<=train<train_count) or row['pair_id']!=pair_id(dataset_id,query,train):
                raise ValueError(f'标注第{number}行配对ID或索引无效')
            label=row['label'].strip().lower()
            if label not in ('','correct','incorrect','uncertain'):
                raise ValueError(f'标注第{number}行label应为correct/incorrect/uncertain或空')
            if label and not row['reviewer'].strip():
                raise ValueError(f'标注第{number}行请填写真实标注者reviewer')
            key=row['pair_id']
            if key in labels:
                raise ValueError(f'标注第{number}行配对重复；同一对在多个阈值组共用一个标签')
            labels[key]={**row,'label':label}
    return labels


def error_estimate(samples,dataset_id,labels,course_size=50):
    known=[labels.get(pair_id(dataset_id,m.queryIdx,m.trainIdx),{}).get('label','') for m in samples]
    correct=known.count('correct')
    incorrect=known.count('incorrect')
    decisive=correct+incorrect
    complete=bool(samples) and decisive==len(samples)
    rate=incorrect/decisive if complete else None
    interval=None
    if complete:
        z=1.959963984540054
        denominator=1+z*z/decisive
        middle=(rate+z*z/(2*decisive))/denominator
        radius=z*np.sqrt(rate*(1-rate)/decisive+z*z/(4*decisive**2))/denominator
        interval=[max(0,float(middle-radius)),min(1,float(middle+radius))]
    return {'sample_count':len(samples),'decisive_count':decisive,'correct':correct,'incorrect':incorrect,
            'uncertain':known.count('uncertain'),'unlabeled':known.count(''),'complete_for_sample':complete,
            'course_50_pairs_complete':complete and decisive>=course_size,
            'error_rate':rate,'wilson_95_interval':interval,'basis':'human CSV labels only; no geometry/ratio pseudo-labels'}
