"""Chessboard detection, five-coefficient camera calibration and verified exports."""
from __future__ import annotations
from contextlib import contextmanager
import json
from pathlib import Path
import cv2
import numpy as np
from common import ROOT,atomic_write,sha256
from matching import positive_integer
from lab6_geometry import positive_number


def board_points(cols=9,rows=7,square_size=25.):
    cols=positive_integer(cols,'cols',3);rows=positive_integer(rows,'rows',3)
    square_size=positive_number(square_size,'square_size_mm')
    result=np.zeros((cols*rows,3),np.float32)
    result[:,:2]=np.mgrid[0:cols,0:rows].T.reshape(-1,2)*square_size
    return result


def gray_uint8(image):
    if not isinstance(image,np.ndarray) or image.dtype!=np.uint8 or image.size==0:
        raise ValueError('棋盘图片必须为非空uint8数组')
    if image.ndim==2:return image
    if image.ndim==3 and image.shape[2] in (3,4):return cv2.cvtColor(image[:,:,:3],cv2.COLOR_BGR2GRAY)
    raise ValueError('只支持灰度/BGR/BGRA棋盘图片')


def detect_board(image,cols=9,rows=7):
    board_points(cols,rows)
    gray=gray_uint8(image)
    if min(gray.shape)<16:return None
    found,corners=cv2.findChessboardCorners(gray,(cols,rows),
                         cv2.CALIB_CB_ADAPTIVE_THRESH|cv2.CALIB_CB_NORMALIZE_IMAGE)
    if not found or corners is None:return None
    raw=np.asarray(corners,dtype=np.float32).reshape(-1,1,2).copy()
    refined=cv2.cornerSubPix(gray,corners.copy(),(11,11),(-1,-1),
                             (cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_MAX_ITER,40,.001))
    refined=np.asarray(refined,dtype=np.float32).reshape(-1,1,2)
    if refined.shape!=(cols*rows,1,2) or not np.isfinite(refined).all():
        raise ValueError('角点数/坐标不合法')
    return {'raw':raw,'refined':refined}


def camera_parameters(K,dist):
    K=np.array(K,dtype=np.float64,copy=True);dist=np.asarray(dist,dtype=np.float64).reshape(-1)
    if K.shape!=(3,3) or not np.isfinite(K).all() or K[0,0]<=0 or K[1,1]<=0 or not np.allclose(K[2],[0,0,1]):
        raise ValueError('K必须为有效有限3×3针孔内参，fx/fy为正')
    if dist.shape!=(5,) or not np.isfinite(dist).all():raise ValueError('dist需为有限5系数[k1,k2,p1,p2,k3]')
    return K,dist


def point_matrix(points,count):
    array=np.asarray(points,dtype=np.float32)
    if array.shape not in ((count,2),(count,1,2)) or not np.isfinite(array).all():
        raise ValueError('角点数量、shape或有限性错误')
    return np.ascontiguousarray(array.reshape(count,1,2))


def calibrate_views(corners,image_size,cols=9,rows=7,square_size=25.,min_views=15):
    min_views=positive_integer(min_views,'min_views',3)
    if len(image_size)!=2:raise ValueError('image_size必须为(W,H)')
    size=tuple(positive_integer(v,'image_size',16) for v in image_size)
    obj=board_points(cols,rows,square_size)
    if len(corners)<min_views:raise ValueError(f'可用图片不足{min_views}张')
    img=[point_matrix(p,len(obj)) for p in corners]
    rms,K,dist,rvecs,tvecs=cv2.calibrateCamera([obj.copy() for _ in img],img,size,None,None,
                       criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_MAX_ITER,100,1e-9))
    K,dist=camera_parameters(K,dist)
    errors=[];per_view=[]
    for observed,rvec,tvec in zip(img,rvecs,tvecs):
        predicted=cv2.projectPoints(obj,rvec,tvec,K,dist)[0].reshape(-1,2)
        error=np.linalg.norm(predicted.astype(np.float64)-observed.reshape(-1,2),axis=1)
        errors.append(error);per_view.append(float(np.sqrt(np.mean(error**2))))
    recomputed=float(np.sqrt(np.mean(np.concatenate(errors)**2)))
    if not np.isfinite(rms) or not np.isclose(rms,recomputed,atol=1e-3,rtol=1e-3):
        raise ValueError('重投影RMS复算不一致')
    return dict(rms=float(rms),K=K,dist=dist,rvecs=list(rvecs),tvecs=list(tvecs),
                per_view_rms=per_view,corner_errors=errors,recomputed_rms=recomputed)


def pose_coverage(rvecs):
    angles=[]
    for vector in rvecs:
        normal=cv2.Rodrigues(np.asarray(vector,dtype=np.float64).reshape(3))[0][:,2]
        if normal[2]<0:normal=-normal
        angles.append([float(np.degrees(np.arctan2(-normal[1],np.hypot(normal[0],normal[2])))),
                       float(np.degrees(np.arctan2(normal[0],normal[2])))])
    if not angles:raise ValueError('没有可用姿态')
    angles=np.array(angles)
    return dict(definition='board normal: pitch=atan2(-ny,hypot(nx,nz)); yaw=atan2(nx,nz), nz>=0',
                pitch_span_deg=float(np.ptp(angles[:,0])),yaw_span_deg=float(np.ptp(angles[:,1])),
                pitch_yaw_deg=angles.tolist())


def straightness(points,cols=9,rows=7):
    points=point_matrix(points,cols*rows).reshape(rows,cols,2).astype(np.float64)
    residuals=[]
    for line in [*points,*points.transpose(1,0,2)]:
        centered=line-line.mean(axis=0)
        _,singular,V=np.linalg.svd(centered,full_matrices=False)
        if singular[0]<1e-6:raise ValueError('直线度不能使用退化点列')
        residuals.extend((centered@V[-1]).tolist())
    return float(np.sqrt(np.mean(np.asarray(residuals)**2)))


def corrected_points(points,K,dist):
    K,dist=camera_parameters(K,dist)
    points=np.asarray(points,dtype=np.float64).reshape(-1,1,2)
    if not np.isfinite(points).all():raise ValueError('去畸变坐标不有限')
    return cv2.undistortPoints(points,K,dist,P=K)


def straightness_accepted(before,after):
    # Already straight, nearly distortion-free images need not improve numerical noise.
    return after<.5 and (after<before or (before<.1 and after<=before+.05))


def undistort_image(image,K,dist):
    gray_uint8(image)
    K,dist=camera_parameters(K,dist)
    return cv2.undistort(image,K,dist,None,K)


def projected_board_fraction(rvec,tvec,K,dist,size,cols=9,rows=7,square_size=25.):
    outer=np.float64([[-1,-1,0],[cols,-1,0],[cols,rows,0],[-1,rows,0]])*square_size
    xy=cv2.projectPoints(outer,np.asarray(rvec),np.asarray(tvec),K,dist)[0].reshape(-1,2)
    return float(cv2.contourArea(xy.astype(np.float32))/(size[0]*size[1]))


def check_source_manifest(folder,files,cols,rows,square_size):
    folder=Path(folder).resolve();path=folder/'source_manifest.json'
    if not path.exists():return None
    info=json.loads(path.read_text(encoding='utf-8'))
    if info.get('source_kind')!='user_authorized_synthetic_camera' or info.get('generator_version')!=1:
        raise ValueError('素材清单类型不识别，不能自动当作已知真值')
    if info['pattern_size']!=[cols,rows] or info['square_size_mm']!=square_size:
        raise ValueError('配置棋盘规格与生成清单不符')
    listed=[]
    for row in info['calibration_views']+info['validation_views']+[info['template']]:
        p=(folder/row['file']).resolve()
        if not p.is_relative_to(folder) or sha256(p)!=row['sha256']:
            raise ValueError('生成来源清单哈希不符，拒绝使用陈旧真值')
        if row in info['calibration_views']:listed.append(p)
    if set(listed)!=set(Path(p).resolve() for p in files):raise ValueError('标定图片集合与来源清单不符')
    return info


@contextmanager
def result_exports(output):
    """Publish guide-compatible files, restoring all three if promotion fails.

    JSON is written last and carries hashes. Readers must verify it to reject a
    partially observed update. Canonical per-lab results remain under LatestRun.
    """
    folder=ROOT/'results'
    if folder.is_symlink() or folder.is_junction() or not folder.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('results兼容导出目录不能是链接或越界')
    names=('K.npy','dist.npy','calib_result.json')
    paths=[folder/n for n in names]
    if any(p.is_symlink() or (p.exists() and not p.is_file()) for p in paths):
        raise ValueError('results导出目标必须为普通文件')
    previous=[p.read_bytes() if p.exists() else None for p in paths]
    try:
        for p,name in zip(paths,names):atomic_write(p,(Path(output)/name).read_bytes())
        yield folder
    except BaseException:
        for p,content in zip(paths,previous):
            if content is None:p.unlink(missing_ok=True)
            else:atomic_write(p,content)
        raise


def load_calibration(folder,expected_camera_id,expected_size):
    folder=Path(folder)
    info=json.loads((folder/'calib_result.json').read_text(encoding='utf-8'))
    if info['camera_id']!=expected_camera_id or info['image_size']!=list(expected_size):
        raise ValueError('相机来源或图像尺寸不符，不能把本次合成内参用于其他图片')
    if set(info.get('export_sha256',{}))!={'K.npy','dist.npy'}:
        raise ValueError('标定导出哈希字段不完整')
    for name,digest in info['export_sha256'].items():
        if name not in ('K.npy','dist.npy') or sha256(folder/name)!=digest:
            raise ValueError('标定导出哈希不一致，可能更新未完成或文件已改变')
    K,dist=camera_parameters(np.load(folder/'K.npy',allow_pickle=False),np.load(folder/'dist.npy',allow_pickle=False))
    return K,dist,info
