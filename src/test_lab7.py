"""Known-neighbor and human-label contracts; synthetic labels are test fixtures only."""
import csv
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import cv2
import numpy as np
import pytest
from common import ROOT
from matching import knn_matches,nearest,filter_ratio,mutual_nearest,symmetric_ratio,match_records,benchmark_matchers
from lab7_annotations import FIELDS,pair_id,random_sample,read_labels,error_estimate,dataset_identifier
from lab7_artifacts import annotation_artifacts
from latest_runs import LatestRun


def dm(query,train,distance):
    return cv2.DMatch(query,train,float(distance))


@pytest.mark.parametrize('backend',['bf','flann'])
def test_knn_known_nearest_and_second(backend):
    query=np.zeros((1,128),np.float32)
    query[0,0]=1
    train=np.zeros((3,128),np.float32)
    train[:,0]=[0,5,12]
    raw=knn_matches(query,train,backend)
    assert [m.trainIdx for m in raw[0]]==[0,1]
    np.testing.assert_allclose([m.distance for m in raw[0]],[1,4])


@pytest.mark.parametrize('backend',['bf','flann'])
@pytest.mark.parametrize('count',[0,1])
def test_too_few_train_safe(backend,count):
    raw=knn_matches(np.ones((3,128),np.float32),np.zeros((count,128),np.float32),backend)
    assert len(raw)==3
    assert all(len(pair)==count for pair in raw)
    assert filter_ratio(raw)==[]


def test_empty_query_safe():
    assert knn_matches(np.empty((0,128),np.float32),np.ones((2,128),np.float32))==[]


@pytest.mark.parametrize('value',[np.zeros((2,128),np.uint8),np.zeros((2,127),np.float32),np.full((2,128),np.nan,np.float32)])
def test_invalid_descriptor(value):
    with pytest.raises(ValueError):
        knn_matches(value,np.zeros((2,128),np.float32))


@pytest.mark.parametrize('threshold',[0,1,-0.5,float('nan'),True])
def test_invalid_ratio(threshold):
    with pytest.raises(ValueError):
        filter_ratio([],threshold)


def test_ratio_is_strict_and_distance_is_absolute():
    raw=[[dm(0,0,3),dm(0,1,4)],[dm(1,1,1),dm(1,0,10)]]
    assert [m.queryIdx for m in filter_ratio(raw,0.75)]==[1]
    assert len(filter_ratio(raw,0.9))==2
    assert len(filter_ratio(raw,0.9,max_distance=2))==1


def test_zero_second_distance_is_ambiguous_and_json_safe():
    raw=[[dm(0,0,0),dm(0,1,0)]]
    assert filter_ratio(raw)==[]
    assert match_records(raw)[0]['ratio'] is None
    json.dumps(match_records(raw),allow_nan=False)


def test_mutual_nearest_differs_from_bidirectional_ratio():
    forward=[[dm(0,1,3),dm(0,0,10)],[dm(1,0,1),dm(1,1,10)]]
    reverse=[[dm(0,1,1),dm(0,0,10)],[dm(1,0,4),dm(1,1,5)]]
    assert len(mutual_nearest(filter_ratio(forward),reverse))==2
    assert [(m.queryIdx,m.trainIdx) for m in symmetric_ratio(forward,reverse)]==[(1,0)]


def test_mutual_mapping_uses_reversed_indices():
    forward=[dm(0,2,1),dm(1,0,1)]
    reverse=[[dm(0,0,1)],[],[dm(2,0,1)]]
    assert [(m.queryIdx,m.trainIdx) for m in mutual_nearest(forward,reverse)]==[(0,2)]


def test_all_queries_processed_without_300_cutoff():
    train=np.zeros((3,128),np.float32)
    train[:,0]=[0,10,30]
    query=np.zeros((350,128),np.float32)
    raw=knn_matches(query,train)
    assert len(raw)==350 and len(filter_ratio(raw))==350
    assert max(m.queryIdx for m in nearest(raw))==349


def test_benchmark_reports_measured_medians():
    desc=np.random.default_rng(7).normal(size=(12,128)).astype(np.float32)
    data,rows=benchmark_matchers(desc,desc,repeats=2)
    assert set(data)=={'bf','flann'}
    assert len(rows)==2 and all(row['median_ms']>=0 and len(row['bidirectional_ms'])==2 for row in rows)


def test_uniform_sampling_reproducible_unique_and_order_independent():
    matches=[dm(i,i,1) for i in range(200)]
    a=random_sample(matches,0.75)
    b=random_sample(list(reversed(matches)),0.75)
    assert [m.queryIdx for m in a]==[m.queryIdx for m in b]
    assert len(a)==len({m.queryIdx for m in a})==50
    assert max(m.queryIdx for m in a)>100  # sample is not a first/best-50 slice


def test_small_or_empty_population_sampled_honestly():
    assert random_sample([],0.6)==[]
    assert len(random_sample([dm(0,0,1)],0.6))==1


def write_labels(path,rows):
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def label_row(label='correct',dataset='a'*64,query=0,train=0):
    return {'dataset_id':dataset,'pair_id':pair_id(dataset,query,train),'query_index':query,'train_index':train,
            'label':label,'reviewer':'unit-test fixture, not a real human review','note':'中文, comma "quote"\nnewline'}


def test_csv_roundtrip_and_no_file_overwrite(tmp_path):
    path=tmp_path/'标签.csv'
    write_labels(path,[label_row()])
    before=path.read_bytes()
    labels=read_labels(path,'a'*64,1,1)
    assert labels[pair_id('a'*64,0,0)]['note']==label_row()['note']
    assert path.read_bytes()==before


@pytest.mark.parametrize('alteration',['dataset','index','duplicate','unknown_label','missing_reviewer','pair_id'])
def test_invalid_or_stale_labels_rejected(tmp_path,alteration):
    row=label_row()
    if alteration=='dataset':row['dataset_id']='b'*64
    if alteration=='index':row['query_index']=5
    if alteration=='unknown_label':row['label']='probably'
    if alteration=='missing_reviewer':row['reviewer']=''
    if alteration=='pair_id':row['pair_id']='wrong'
    rows=[row,row.copy()] if alteration=='duplicate' else [row]
    path=tmp_path/'labels.csv'
    write_labels(path,rows)
    with pytest.raises(ValueError):
        read_labels(path,'a'*64,2,2)


def test_partial_uncertain_or_absent_labels_have_no_fake_rate():
    sample=[dm(0,0,1),dm(1,1,1)]
    assert error_estimate(sample,'a'*64,{})['error_rate'] is None
    labels={pair_id('a'*64,0,0):{'label':'correct'},pair_id('a'*64,1,1):{'label':'uncertain'}}
    stats=error_estimate(sample,'a'*64,labels)
    assert stats['error_rate'] is None and stats['decisive_count']==1 and stats['uncertain']==1


@pytest.mark.parametrize('extra_column',[False,True])
def test_malformed_csv_column_count_rejected(tmp_path,extra_column):
    path=tmp_path/'malformed.csv'
    row=label_row()
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream)
        writer.writerow(FIELDS)
        values=[row[key] for key in FIELDS]
        writer.writerow(values+['extra'] if extra_column else values[:-1])
    with pytest.raises(ValueError,match='列数不匹配'):
        read_labels(path,'a'*64,1,1)


def test_50_labeled_pairs_compute_real_denominator_and_interval():
    sample=[dm(i,i,1) for i in range(50)]
    labels={pair_id('a'*64,i,i):{'label':'incorrect' if i<10 else 'correct'} for i in range(50)}
    stats=error_estimate(sample,'a'*64,labels)
    assert stats['error_rate']==0.2 and stats['course_50_pairs_complete']
    assert stats['wilson_95_interval'][0]<0.2<stats['wilson_95_interval'][1]


def test_small_complete_sample_not_claimed_as_50_pairs():
    stats=error_estimate([dm(0,0,1)],'a'*64,{pair_id('a'*64,0,0):{'label':'correct'}})
    assert stats['error_rate']==0 and not stats['course_50_pairs_complete']


def test_fingerprint_changes_with_input_parameters_or_features():
    desc=np.ones((1,128),np.float32)
    a=dataset_identifier(['photo'],{'maxside':100},[[1,2]],[desc])
    assert a!=dataset_identifier(['other'],{'maxside':100},[[1,2]],[desc])
    assert a!=dataset_identifier(['photo'],{'maxside':200},[[1,2]],[desc])
    assert a!=dataset_identifier(['photo'],{'maxside':100},[[1,2]],[desc*2])


def test_annotation_json_safely_escapes_user_note(tmp_path):
    output,evidence=tmp_path/'output',tmp_path/'evidence'
    output.mkdir();evidence.mkdir()
    pid=pair_id('a'*64,0,0)
    manifest={'dataset_id':'a'*64,'pairs':[{'pair_id':pid,'query_index':0,'train_index':0,'xy1':[10,10],'xy2':[10,10],'ratio':0.5}],
              'groups':[{'threshold':0.6,'population_count':1,'pair_ids':[pid]}]}
    labels={pid:{'label':'correct','reviewer':'test fixture','note':'</script><script>bad</script>'}}
    annotation_artifacts(output,evidence,manifest,np.zeros((32,32,3),np.uint8),np.zeros((32,32,3),np.uint8),labels)
    assert '</script><script>bad' not in (output/'annotate.html').read_text(encoding='utf-8')


def test_latest_lab7_replaces_and_preserves_on_failure(tmp_path):
    with patch('latest_runs.ROOT',tmp_path):
        for value in ('first','second'):
            with LatestRun('lab7') as latest:
                (latest.output/'marker').write_text(value)
                (latest.evidence/'marker').write_text(value)
                latest.commit()
        with pytest.raises(RuntimeError):
            with LatestRun('lab7'):
                raise RuntimeError('unfinished')
        for root in (tmp_path/'data/output',tmp_path/'evidence'):
            assert [p.name for p in root.iterdir()]==['lab7_latest']
            assert (root/'lab7_latest/marker').read_text()=='second'


@pytest.mark.parametrize('mode',['missing','config'])
def test_cli_errors_do_not_recurse_into_pytest(tmp_path,mode):
    command=[sys.executable,'-X','utf8',str(ROOT/'src/run_lab7.py')]
    if mode=='missing':
        command+=['--image1',str(tmp_path/'no.png')]
    else:
        path=tmp_path/'bad.json'
        path.write_text(json.dumps({'unknown':1}))
        command+=['--config',str(path)]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=30)
    assert result.returncode==1 and 'ERROR:' in result.stderr and 'Traceback' not in result.stderr
