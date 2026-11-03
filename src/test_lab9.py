"""Calibration geometry, raster detection, source integrity and transactional exports."""
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import cv2
import numpy as np
import pytest
from common import ROOT,sha256
from calibration import (board_points,detect_board,calibrate_views,pose_coverage,straightness,corrected_points,
                         camera_parameters,straightness_accepted,undistort_image,result_exports,
                         load_calibration,check_source_manifest)
from prepare_lab9 import rotation,prepare
from run_lab9 import load_config
from latest_runs import LatestRun


@pytest.fixture(scope='module')
def known_calibration():
    K=np.array([[900.,0,640.],[0,910.,480.],[0,0,1.]])
    dist=np.array([-.2,.06,.001,-.0008,.003])
    obj=board_points();rng=np.random.default_rng(91);corners=[];rvecs=[]
    for p in (-22.,0.,22.):
        for y in (-25.,-12.,0.,12.,25.):
            R=rotation(p,y,float(rng.uniform(-5,5)));rv=cv2.Rodrigues(R)[0]
            t=np.array([-100.,-75.,370.])+rng.normal(0,8,3)
            points=cv2.projectPoints(obj,rv,t,K,dist)[0].reshape(-1,1,2)
            points=(points+rng.normal(0,.01,points.shape)).astype(np.float32)
            corners.append(points);rvecs.append(rv)
    result=calibrate_views(corners,(1280,960))
    return K,dist,corners,rvecs,result


def test_known_intrinsics_recovered_without_truth_initialization(known_calibration):
    K,dist,corners,_,c=known_calibration
    assert c['rms']<.05 and np.max(np.abs(np.diag(c['K'])[:2]/np.diag(K)[:2]-1))<.003
    assert np.linalg.norm(c['K'][:2,2]-K[:2,2])<1.
    assert np.isclose(c['rms'],c['recomputed_rms'],atol=1e-4)


def test_known_pose_spans_and_line_correction(known_calibration):
    _,_,points,_,c=known_calibration
    coverage=pose_coverage(c['rvecs'])
    assert coverage['pitch_span_deg']>30 and coverage['yaw_span_deg']>30
    before=np.mean([straightness(p) for p in points])
    after=np.mean([straightness(corrected_points(p,c['K'],c['dist'])) for p in points])
    assert after<before*.1 and after<.05


def flat_board():
    yy,xx=np.indices((8*35,10*35))
    return np.pad(np.where((xx//35+yy//35)%2,255,0).astype(np.uint8),35,constant_values=255)


@pytest.mark.parametrize('channels',[1,3,4])
def test_actual_raster_detection_and_stable_shape(channels):
    image=flat_board()
    if channels==3:image=cv2.cvtColor(image,cv2.COLOR_GRAY2BGR)
    if channels==4:image=cv2.cvtColor(image,cv2.COLOR_GRAY2BGRA)
    before=image.copy();d=detect_board(image)
    assert d is not None and d['raw'].shape==d['refined'].shape==(63,1,2)
    assert d['refined'].dtype==np.float32 and np.array_equal(image,before)


def test_blank_image_has_no_fabricated_corners():
    assert detect_board(np.zeros((64,64),np.uint8)) is None


@pytest.mark.parametrize('image',[np.zeros((20,20),np.uint16),np.zeros((0,20),np.uint8),np.zeros((20,20,2),np.uint8)])
def test_invalid_image_type_rejected(image):
    with pytest.raises(ValueError):detect_board(image)


def test_board_shape_units_and_minimum_view_count(known_calibration):
    obj=board_points(9,7,25.)
    assert obj.shape==(63,3) and np.array_equal(obj[-1],[200,150,0])
    with pytest.raises(ValueError,match='不足15'):calibrate_views(known_calibration[2][:14],(1280,960))


@pytest.mark.parametrize('change',['count','nan','size'])
def test_calibration_bad_points_and_size(known_calibration,change):
    points=[p.copy() for p in known_calibration[2]];size=(1280,960)
    if change=='count':points[0]=points[0][:-1]
    if change=='nan':points[0][0]=np.nan
    if change=='size':size=(0,960)
    with pytest.raises(ValueError):calibrate_views(points,size)


@pytest.mark.parametrize('mode',['negative_focal','bad_shape','nonfinite','bad_dist'])
def test_invalid_camera_parameters(mode):
    K=np.eye(3);dist=np.zeros(5)
    if mode=='negative_focal':K[0,0]=-1
    if mode=='bad_shape':K=np.eye(4)
    if mode=='nonfinite':K[0,0]=np.nan
    if mode=='bad_dist':dist=np.zeros(4)
    with pytest.raises(ValueError):camera_parameters(K,dist)


def test_straightness_accepts_nearly_undistorted_without_fake_improvement():
    assert straightness_accepted(.01,.015)
    assert not straightness_accepted(.01,.2)
    assert not straightness_accepted(2.,.6)


def test_zero_distortion_pixels_and_input_preserved():
    image=np.random.default_rng(9).integers(0,256,(60,80,3),dtype=np.uint8);before=image.copy()
    K=np.array([[100.,0,40.],[0,100.,30.],[0,0,1.]])
    assert np.array_equal(undistort_image(image,K,np.zeros(5)),image)
    assert np.array_equal(image,before)


def source_fixture(tmp_path):
    image=tmp_path/'calib_01.png';image.write_bytes(b'fixture pixels')
    template=tmp_path/'board_template.png';template.write_bytes(b'template fixture')
    info=dict(source_kind='user_authorized_synthetic_camera',generator_version=1,pattern_size=[9,7],square_size_mm=25.,
              calibration_views=[dict(file=image.name,sha256=sha256(image))],validation_views=[],
              template=dict(file=template.name,sha256=sha256(template)))
    (tmp_path/'source_manifest.json').write_text(json.dumps(info),encoding='utf-8')
    return image


def test_source_manifest_rejects_stale_truth_and_wrong_specification(tmp_path):
    p=source_fixture(tmp_path)
    assert check_source_manifest(tmp_path,[p],9,7,25.) is not None
    with pytest.raises(ValueError):check_source_manifest(tmp_path,[p],8,7,25.)
    p.write_bytes(b'changed')
    with pytest.raises(ValueError,match='哈希'):check_source_manifest(tmp_path,[p],9,7,25.)


def export_fixture(folder,marker=1.):
    folder.mkdir(parents=True,exist_ok=True)
    K=np.array([[100.*marker,0,40.],[0,100.,30.],[0,0,1.]])
    np.save(folder/'K.npy',K,allow_pickle=False);np.save(folder/'dist.npy',np.zeros(5),allow_pickle=False)
    info=dict(camera_id='test_camera',image_size=[80,60],
              export_sha256={n:sha256(folder/n) for n in ('K.npy','dist.npy')})
    (folder/'calib_result.json').write_text(json.dumps(info),encoding='utf-8')


def test_export_loader_rejects_other_camera_size_and_changed_files(tmp_path):
    export_fixture(tmp_path)
    K,dist,_=load_calibration(tmp_path,'test_camera',(80,60));assert K.shape==(3,3) and dist.shape==(5,)
    with pytest.raises(ValueError,match='相机来源'):load_calibration(tmp_path,'other',(80,60))
    with pytest.raises(ValueError,match='尺寸'):load_calibration(tmp_path,'test_camera',(160,120))
    np.save(tmp_path/'dist.npy',np.ones(5),allow_pickle=False)
    with pytest.raises(ValueError,match='哈希'):load_calibration(tmp_path,'test_camera',(80,60))


def test_exports_restore_all_three_if_publication_body_fails(tmp_path):
    source=tmp_path/'output';export_fixture(source,2.)
    old=tmp_path/'results';export_fixture(old)
    before={p.name:p.read_bytes() for p in old.iterdir()}
    with patch('calibration.ROOT',tmp_path),pytest.raises(RuntimeError):
        with result_exports(source):
            assert (old/'K.npy').read_bytes()!=(before['K.npy'])
            raise RuntimeError('simulated canonical promotion failure')
    assert {p.name:p.read_bytes() for p in old.iterdir()}==before


def test_exports_rollback_when_second_file_write_fails(tmp_path):
    import calibration
    source=tmp_path/'output';export_fixture(source,2.)
    old=tmp_path/'results';export_fixture(old)
    before={p.name:p.read_bytes() for p in old.iterdir()};real=calibration.atomic_write;failed=False
    def write(path,content):
        nonlocal failed
        if Path(path).name=='dist.npy' and not failed:
            failed=True;raise OSError('simulated export write failure')
        real(path,content)
    with patch('calibration.ROOT',tmp_path),patch('calibration.atomic_write',write),pytest.raises(OSError):
        with result_exports(source):pass
    assert {p.name:p.read_bytes() for p in old.iterdir()}==before


def test_new_exports_removed_if_first_publication_fails(tmp_path):
    source=tmp_path/'output';export_fixture(source)
    with patch('calibration.ROOT',tmp_path),pytest.raises(RuntimeError):
        with result_exports(source):raise RuntimeError('fail')
    assert not list((tmp_path/'results').iterdir())


def test_generator_rejects_outside_path_and_unknown_existing_folder(tmp_path):
    with pytest.raises(ValueError):prepare(tmp_path)
    with patch('prepare_lab9.ROOT',tmp_path):
        folder=tmp_path/'data/calib/unknown';folder.mkdir(parents=True)
        (folder/'personal.png').write_bytes(b'preserve')
        with pytest.raises(ValueError,match='已有未知'):prepare(folder)
        assert (folder/'personal.png').read_bytes()==b'preserve'


@pytest.mark.parametrize('content',[{'unknown':1},{'cols':2},{'square_size_mm':0},{'min_views':3},
                                   {'image_glob':'../*.png'},{'min_board_fraction':2},{'min_board_fraction':.29},
                                   {'min_pitch_span_deg':29},{'max_rms':1.1}])
def test_bad_configuration_rejected(tmp_path,content):
    path=tmp_path/'cfg.json';path.write_text(json.dumps(content),encoding='utf-8')
    with pytest.raises(ValueError):load_config(path)


def test_latest_lab9_success_and_failure_keep_latest_only(tmp_path):
    with patch('latest_runs.ROOT',tmp_path):
        for value in ('old','new'):
            with LatestRun('lab9') as latest:
                (latest.output/'marker').write_text(value);(latest.evidence/'marker').write_text(value)
                latest.commit()
        with pytest.raises(RuntimeError):
            with LatestRun('lab9'):raise RuntimeError('failed')
        for root in (tmp_path/'data/output',tmp_path/'evidence'):
            assert [p.name for p in root.iterdir()]==['lab9_latest']
            assert (root/'lab9_latest/marker').read_text()=='new'


def test_missing_directory_cli_fails_before_tests(tmp_path):
    result=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'src/run_lab9.py'),'--input-dir',str(tmp_path/'missing')],
                          cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=30)
    assert result.returncode==1 and 'ERROR:' in result.stderr and 'Traceback' not in result.stderr
