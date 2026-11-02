"""Geometry, real black pixels, input boundaries and latest-result rollback."""
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
import cv2
import numpy as np
import pytest
from common import ROOT
from homography import estimate_homography,project_points,canvas_geometry,stitch_pair,valid_homography,match_and_estimate
from latest_runs import LatestRun
from run_lab8 import load_config


def sample_points():
    return np.float64([[10,10],[100,10],[100,90],[10,90],[50,20],[40,70]])


def test_ransac_rejects_known_outliers_and_finds_right_to_left_H():
    rng=np.random.default_rng(88)
    right=rng.uniform(0,400,(100,2))
    H=np.array([[1.03,.04,-25.],[-.02,.98,17.],[.0002,-.0001,1.]])
    left=project_points(right,H)
    left[:25]=rng.uniform(500,900,(25,2))
    actual,mask,errors=estimate_homography(right,left,threshold=1.)
    assert mask[25:].sum()>=74 and mask[:25].sum()==0
    assert np.median(errors[25:])<.001
    assert np.max(np.linalg.norm(project_points(right[25:],actual)-left[25:],axis=1))<.01


def test_ransac_does_not_mutate_coordinates_and_is_seeded():
    right=sample_points();left=right+[3.,-2.]
    saved=(right.copy(),left.copy())
    a=estimate_homography(right,left);b=estimate_homography(right,left)
    assert np.array_equal(a[1],b[1]) and np.allclose(a[0],b[0])
    assert np.array_equal(right,saved[0]) and np.array_equal(left,saved[1])


@pytest.mark.parametrize('mode',['few','unequal','collinear','duplicate','nan','wrong_shape'])
def test_bad_point_sets_rejected(mode):
    right=sample_points();left=right.copy()
    if mode=='few':right=right[:3];left=left[:3]
    if mode=='unequal':left=left[:4]
    if mode=='collinear':right=np.array([[i,i] for i in range(6)])
    if mode=='duplicate':right=np.ones((6,2))
    if mode=='nan':right[0,0]=np.nan
    if mode=='wrong_shape':right=right.reshape(3,4)
    with pytest.raises(ValueError):estimate_homography(right,left)


@pytest.mark.parametrize('kwargs',[{'threshold':0},{'confidence':1.},{'max_iters':0},{'seed':2**31},{'seed':True}])
def test_bad_ransac_parameters(kwargs):
    with pytest.raises(ValueError):estimate_homography(sample_points(),sample_points(),**kwargs)


@pytest.mark.parametrize('H',[np.zeros((3,3)),np.eye(2),np.full((3,3),np.nan),np.diag([1,0,1])])
def test_invalid_H_rejected(H):
    with pytest.raises(ValueError):valid_homography(H)


def test_negative_translation_canvas_covers_both_full_images():
    H=np.array([[1.,0,-7],[0,1,-3],[0,0,1]])
    g=canvas_geometry((10,20,3),(10,20,3),H)
    assert g['size']==(27,13) and g['origin']==[-7.,-3.]
    assert np.allclose(project_points([[0,0]],g['translation']),[[7,3]])
    image=np.full((10,20,3),120,np.uint8)
    result=stitch_pair(image,image,H)
    assert result['left_mask'].sum()==200 and result['right_mask'].sum()==200


def test_horizon_crossing_rejected_before_allocating():
    H=np.array([[1.,0,0],[0,1,0],[.2,0,-1]])
    with pytest.raises(ValueError,match='无穷远线'):canvas_geometry((20,20),(20,20),H)


def test_large_canvas_rejected_before_allocating():
    with pytest.raises(ValueError,match='资源上限'):
        canvas_geometry((100,100),(100,100),np.eye(3),max_pixels=9999)


def test_black_pixels_are_valid_and_contribute_to_blending():
    left=np.zeros((20,30,3),np.uint8);right=np.full_like(left,200)
    result=stitch_pair(left,right,np.eye(3))
    assert result['overlap'].all() and np.all(result['feather']==100)
    assert np.all(result['hard']==0)


def test_feather_identity_single_source_and_input_immutability():
    left=np.full((30,40,3),40,np.uint8);right=np.full_like(left,200)
    saved=(left.copy(),right.copy())
    H=np.array([[1.,0,10],[0,1,0],[0,0,1]])
    result=stitch_pair(left,right,H)
    onlyleft=result['left_mask']&~result['right_mask']
    onlyright=result['right_mask']&~result['left_mask']
    assert np.all(result['feather'][onlyleft]==40) and np.all(result['feather'][onlyright]==200)
    middle=result['feather'][result['overlap']]
    assert middle.min()>40 and middle.max()<200
    assert np.array_equal(left,saved[0]) and np.array_equal(right,saved[1])


def test_disjoint_images_rejected():
    image=np.ones((10,10,3),np.uint8)
    H=np.array([[1.,0,30],[0,1,0],[0,0,1]])
    with pytest.raises(ValueError,match='没有有效重叠'):stitch_pair(image,image,H)


def test_blank_photos_fail_without_pseudo_matches():
    image=np.zeros((64,64,3),np.uint8)
    with pytest.raises(ValueError,match='至少需4对'):match_and_estimate(image,image)


@pytest.mark.parametrize('content',[{'unknown':1},{'ratio_threshold':1},{'max_input_side':1},
                                  {'image1':''},{'confidence':False},{'max_canvas_pixels':0}])
def test_bad_configuration_rejected(tmp_path,content):
    path=tmp_path/'cfg.json';path.write_text(json.dumps(content),encoding='utf-8')
    with pytest.raises(ValueError):load_config(path)


def test_latest_lab8_success_and_failed_stage_preserve_only_latest(tmp_path):
    with patch('latest_runs.ROOT',tmp_path):
        for marker in ('old','new'):
            with LatestRun('lab8') as latest:
                (latest.output/'marker').write_text(marker)
                (latest.evidence/'marker').write_text(marker)
                latest.commit()
        with pytest.raises(RuntimeError):
            with LatestRun('lab8') as latest:
                (latest.output/'incomplete').write_text('unfinished')
                raise RuntimeError('simulated failure')
        for parent in (tmp_path/'data/output',tmp_path/'evidence'):
            assert [p.name for p in parent.iterdir()]==['lab8_latest']
            assert (parent/'lab8_latest/marker').read_text()=='new'


def test_latest_lab8_rolls_back_both_directories_on_promotion_failure(tmp_path):
    original=Path.rename
    with patch('latest_runs.ROOT',tmp_path):
        with LatestRun('lab8') as latest:
            (latest.output/'marker').write_text('old');(latest.evidence/'marker').write_text('old')
            latest.commit()
        with LatestRun('lab8') as latest:
            (latest.output/'marker').write_text('new');(latest.evidence/'marker').write_text('new')
            def failing_rename(source,target):
                if source==latest.evidence:raise OSError('simulated evidence promotion failure')
                return original(source,target)
            with patch.object(Path,'rename',failing_rename),pytest.raises(OSError):latest.commit()
        assert (tmp_path/'data/output/lab8_latest/marker').read_text()=='old'
        assert (tmp_path/'evidence/lab8_latest/marker').read_text()=='old'
        assert not list((tmp_path/'evidence').glob('.stage*'))


def test_missing_input_cli_returns_error_without_running_pytest(tmp_path):
    result=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'src/run_lab8.py'),'--image1',str(tmp_path/'missing.jpg')],
                          cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=30)
    assert result.returncode==1 and 'ERROR:' in result.stderr and 'Traceback' not in result.stderr
