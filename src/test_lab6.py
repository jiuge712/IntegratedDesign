"""SIFT contracts, known geometry, meaningful matching and latest-only tests."""
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import cv2
import numpy as np
import pytest

from common import ROOT
from features import extract_sift, sift_config, keypoint_records
from lab6_geometry import transform_full_canvas, project_xy, ratio_matches, match_statistics
from latest_runs import LatestRun


@pytest.fixture(scope='module')
def texture():
    # Synthetic unit-test data, separate from the user's formal photograph.
    rng = np.random.default_rng(6)
    image = rng.integers(0, 256, (256, 320), dtype=np.uint8)
    image = cv2.GaussianBlur(image, (3,3), 0.7)
    for _ in range(35):
        x, y = rng.integers([15,15], [305,241])
        cv2.circle(image, (int(x),int(y)), int(rng.integers(3,12)), int(rng.integers(0,256)), 2)
    cv2.putText(image, 'SIFT 6', (30,120), cv2.FONT_HERSHEY_SIMPLEX, 1, 255, 2)
    return image


@pytest.mark.parametrize('image,error', [(None,TypeError), ([],TypeError),
    (np.empty((0,0),np.uint8),ValueError), (np.zeros((20,20),np.float32),ValueError),
    (np.zeros((20,20,2),np.uint8),ValueError)])
def test_invalid_input(image,error):
    with pytest.raises(error):
        extract_sift(image)


@pytest.mark.parametrize('cfg', [{'nfeatures':-1}, {'nfeatures':True}, {'nfeatures':2.5},
    {'nOctaveLayers':0}, {'contrastThreshold':0}, {'contrastThreshold':float('nan')},
    {'edgeThreshold':-1}, {'sigma':float('inf')}, {'enable_precise_upscale':1}, {'unknown':1}])
def test_invalid_parameters(cfg):
    with pytest.raises(ValueError):
        sift_config(cfg)


def test_cfg_not_mapping():
    with pytest.raises(TypeError):
        sift_config([])


@pytest.mark.parametrize('shape', [(32,32),(1,1)])
def test_no_features_has_stable_empty_descriptor(shape):
    points, desc = extract_sift(np.zeros(shape,np.uint8))
    assert points == [] and desc.shape == (0,128) and desc.dtype == np.float32


def test_keypoint_descriptor_alignment_and_input_unchanged(texture):
    original = texture.copy()
    cfg = {'contrastThreshold':0.04}
    points, desc = extract_sift(texture,cfg)
    assert len(points) > 20 and desc.shape == (len(points),128)
    assert desc.dtype == np.float32 and np.isfinite(desc).all()
    for point in points:
        assert 0 <= point.pt[0] < texture.shape[1] and 0 <= point.pt[1] < texture.shape[0]
        assert point.size > 0 and 0 <= point.angle < 360
    assert len(keypoint_records(points)) == len(points)
    np.testing.assert_array_equal(texture,original)
    assert cfg == {'contrastThreshold':0.04}


def test_bgr_bgra_agree_with_explicit_gray(texture):
    bgr = cv2.cvtColor(texture,cv2.COLOR_GRAY2BGR)
    bgra = cv2.cvtColor(bgr,cv2.COLOR_BGR2BGRA)
    bgra[:,:,3] = 0
    _, gray_desc = extract_sift(texture)
    for image in (bgr,bgra):
        _, desc = extract_sift(image)
        np.testing.assert_array_equal(desc,gray_desc)


def test_nfeatures_and_contrast_on_texture(texture):
    unlimited, _ = extract_sift(texture)
    limited, _ = extract_sift(texture,{'nfeatures':20})
    weak, _ = extract_sift(texture,{'contrastThreshold':0.01})
    assert 0 < len(limited) <= len(unlimited) <= len(weak)


@pytest.mark.parametrize('angle,scale', [(0,1),(30,1),(0,0.6),(30,0.6),(-50,0.7)])
def test_full_canvas_contains_all_original_edges(texture,angle,scale):
    transformed, matrix = transform_full_canvas(texture,angle,scale)
    h,w = texture.shape
    edges = project_xy(np.array([[0,0],[w,0],[0,h],[w,h]]),matrix)
    assert edges.min() >= -1e-7
    assert edges[:,0].max() <= transformed.shape[1] + 1e-7
    assert edges[:,1].max() <= transformed.shape[0] + 1e-7
    np.testing.assert_allclose(matrix[:,:2].T @ matrix[:,:2],np.eye(2)*scale**2,atol=1e-12)
    if angle == 0 and scale == 1:
        np.testing.assert_array_equal(transformed,texture)


def test_transform_invalid_scale(texture):
    with pytest.raises(ValueError):
        transform_full_canvas(texture,scale=0)


def test_ratio_known_descriptors_and_all_queries():
    train = np.zeros((3,128),np.float32)
    train[1,0],train[2,0] = 10,30
    query = np.repeat(train[:1],350,axis=0)
    matches,count = ratio_matches(query,train)
    assert count == 350 and len(matches) == 350
    assert max(m.queryIdx for m in matches) == 349  # no des[:300] truncation


def test_ratio_ambiguous_identical_neighbors_rejected():
    assert ratio_matches(np.zeros((1,128),np.float32),np.zeros((2,128),np.float32))[0] == []


@pytest.mark.parametrize('count', [0,1])
def test_insufficient_train_descriptors_safe(count):
    assert ratio_matches(np.zeros((2,128),np.float32),np.zeros((count,128),np.float32)) == ([],0)


def test_ratio_invalid_dtype():
    with pytest.raises(ValueError):
        ratio_matches(np.zeros((2,128),np.uint8),np.zeros((2,128),np.float32))


def test_geometry_known_correct_and_wrong_match():
    source = [cv2.KeyPoint(1,2,3),cv2.KeyPoint(8,9,3)]
    target = [cv2.KeyPoint(6,8,3),cv2.KeyPoint(100,100,3)]
    matches = [cv2.DMatch(0,0,0.1),cv2.DMatch(1,1,0.2)]
    stats,rows = match_statistics(source,target,matches,np.array([[1,0,5],[0,1,6]]))
    assert stats['ratio_passed_per_source'] == 1
    assert stats['geometry_consistent_per_match'] == 0.5
    assert rows[0]['reprojection_error_px'] == 0 and not rows[1]['geometry_consistent']


def test_empty_geometry_has_no_fabricated_accuracy():
    stats,_ = match_statistics([],[],[],np.array([[1,0,0],[0,1,0]]))
    assert stats['geometry_consistent_per_match'] is None


def test_rotation_scale_matches_known_geometry(texture):
    transformed, matrix = transform_full_canvas(texture,30,0.6)
    source, desc = extract_sift(texture)
    target, desc2 = extract_sift(transformed)
    matches,_ = ratio_matches(desc,desc2)
    stats,_ = match_statistics(source,target,matches,matrix)
    assert stats['geometry_consistent'] > 10
    assert stats['geometry_consistent_per_match'] > 0.75


def test_latest_lab6_replaces_and_rolls_back(tmp_path):
    with patch('latest_runs.ROOT',tmp_path):
        for value in ('first','second'):
            with LatestRun('lab6') as latest:
                (latest.output/'marker').write_text(value)
                (latest.evidence/'marker').write_text(value)
                latest.commit()
        with pytest.raises(RuntimeError):
            with LatestRun('lab6') as latest:
                raise RuntimeError('unfinished run')
        for root in (tmp_path/'data/output',tmp_path/'evidence'):
            assert [p.name for p in root.iterdir()] == ['lab6_latest']
            assert (root/'lab6_latest/marker').read_text() == 'second'


@pytest.mark.parametrize('height,width,should_succeed',[(100,200,True),(16,200,False)])
def test_input_resize_preserves_aspect_or_reports_too_short(tmp_path,height,width,should_succeed):
    from run_lab6 import load_input
    source = tmp_path/'resize.png'
    ok,encoded = cv2.imencode('.png',np.zeros((height,width,3),np.uint8))
    assert ok
    source.write_bytes(encoded.tobytes())
    if should_succeed:
        image,info = load_input(source,80)
        assert image.shape[:2] == (40,80)
        np.testing.assert_allclose(np.array(info['source_to_work_pixel_centers'])[:,:2],np.eye(2)*0.4)
    else:
        with pytest.raises(ValueError,match='最短边不足16'):
            load_input(source,80)


@pytest.mark.parametrize('mode',['missing','unknown'])
def test_cli_errors_are_clear(tmp_path,mode):
    command = [sys.executable,'-X','utf8',str(ROOT/'src/run_lab6.py')]
    if mode == 'missing':
        command += ['--input',str(tmp_path/'absent.png')]
    else:
        config = tmp_path/'bad.json'
        config.write_text(json.dumps({'unknown':1}))
        command += ['--config',str(config)]
    result = subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=30)
    assert result.returncode == 1 and 'ERROR:' in result.stderr and 'Traceback' not in result.stderr
