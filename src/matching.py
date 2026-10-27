"""SIFT L2 KNN, ratio, mutual-nearest and bidirectional ratio matching."""
from __future__ import annotations
from time import perf_counter
import cv2
import numpy as np
from lab6_geometry import descriptor_matrix, positive_number


def positive_integer(value,name,minimum=1):
    if isinstance(value,bool) or not isinstance(value,(int,np.integer)) or value<minimum:
        raise ValueError(f'{name} 必须为不小于{minimum}的整数')
    return int(value)


def ratio_parameter(value):
    value=positive_number(value,'ratio')
    if value>=1:
        raise ValueError('ratio 必须小于1')
    return value


def knn_matches(query:np.ndarray,train:np.ndarray,backend='bf',trees=5,checks=50,seed=7)->list:
    descriptor_matrix(query)
    descriptor_matrix(train)
    if backend not in ('bf','flann'):
        raise ValueError('backend 必须为 bf 或 flann')
    trees=positive_integer(trees,'flann_trees')
    checks=positive_integer(checks,'flann_checks')
    seed=positive_integer(seed,'seed',0)
    if seed>2**31-1:
        raise ValueError('seed 超出OpenCV有符号整数范围')
    if len(query)==0 or len(train)==0:
        return [[] for _ in range(len(query))]
    if backend=='bf':
        matcher=cv2.BFMatcher(cv2.NORM_L2,crossCheck=False)
    else:
        cv2.setRNGSeed(seed)
        matcher=cv2.FlannBasedMatcher({'algorithm':1,'trees':trees},{'checks':checks})
    # FLANN requires k <= train count; a singleton still permits nearest-neighbor checks.
    raw=matcher.knnMatch(np.ascontiguousarray(query),np.ascontiguousarray(train),k=min(2,len(train)))
    return [sorted(pair,key=lambda m:(m.distance,m.trainIdx)) for pair in raw]


def nearest(raw:list)->list:
    return [pair[0] for pair in raw if pair]


def filter_ratio(raw:list,threshold=0.75,max_distance=None)->list:
    threshold=ratio_parameter(threshold)
    if max_distance is not None:
        max_distance=positive_number(max_distance,'max_distance',zero=True)
    return [pair[0] for pair in raw if len(pair)>=2 and pair[1].distance>0
            and pair[0].distance<threshold*pair[1].distance
            and (max_distance is None or pair[0].distance<=max_distance)]


def mutual_nearest(forward:list,reverse_raw:list)->list:
    reverse={(m.trainIdx,m.queryIdx) for m in nearest(reverse_raw)}
    return [m for m in forward if (m.queryIdx,m.trainIdx) in reverse]


def symmetric_ratio(forward_raw:list,reverse_raw:list,threshold=0.75,max_distance=None)->list:
    backward={(m.trainIdx,m.queryIdx) for m in filter_ratio(reverse_raw,threshold,max_distance)}
    return [m for m in filter_ratio(forward_raw,threshold,max_distance) if (m.queryIdx,m.trainIdx) in backward]


def match_records(raw:list)->list[dict]:
    rows=[]
    for pair in raw:
        if not pair:
            continue
        first=pair[0]
        second=pair[1] if len(pair)>=2 else None
        rows.append({'query_index':int(first.queryIdx),'train_index':int(first.trainIdx),
                     'distance1':float(first.distance),'distance2':float(second.distance) if second else None,
                     'ratio':float(first.distance/second.distance) if second and second.distance>0 else None})
    return rows


def benchmark_matchers(desc1,desc2,repeats=3,trees=5,checks=50,seed=7):
    repeats=positive_integer(repeats,'benchmark_repeats')
    data,results={},[]
    for backend in ('bf','flann'):
        # Warm up each path; measured runs include constructing matcher and FLANN indexes.
        knn_matches(desc1,desc2,backend,trees,checks,seed)
        knn_matches(desc2,desc1,backend,trees,checks,seed)
        durations=[]
        for _ in range(repeats):
            start=perf_counter()
            forward=knn_matches(desc1,desc2,backend,trees,checks,seed)
            reverse=knn_matches(desc2,desc1,backend,trees,checks,seed)
            durations.append((perf_counter()-start)*1000)
        data[backend]=(forward,reverse)
        results.append({'backend':backend,'repeats':repeats,'bidirectional_ms':durations,
                        'median_ms':float(np.median(durations)),'min_ms':float(min(durations)),
                        'forward_complete_pairs':sum(len(pair)==2 for pair in forward),
                        'reverse_complete_pairs':sum(len(pair)==2 for pair in reverse)})
    return data,results
