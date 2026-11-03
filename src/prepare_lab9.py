"""Generate user-authorized, physically projected chessboard images, not real photos."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import uuid
import cv2
import numpy as np
from common import ROOT,sha256,write_text,timestamp
from lab7_artifacts import save_png
from latest_runs import remove_owned

GENERATOR_VERSION=1
PATTERN=(9,7)
SQUARE_MM=25.
IMAGE_SIZE=(1280,960)
TRUE_K=np.array([[1100.,0,643.2],[0,1120.,476.7],[0,0,1.]])
TRUE_DIST=np.array([-.18,.045,.001,-.0007,.005])


def rotation(pitch,yaw,roll):
    p,y,r=np.deg2rad([pitch,yaw,roll])
    Rx=np.array([[1,0,0],[0,np.cos(p),-np.sin(p)],[0,np.sin(p),np.cos(p)]])
    Ry=np.array([[np.cos(y),0,np.sin(y)],[0,1,0],[-np.sin(y),0,np.cos(y)]])
    Rz=np.array([[np.cos(r),-np.sin(r),0],[np.sin(r),np.cos(r),0],[0,0,1]])
    return Rz@Ry@Rx


def object_points():
    obj=np.zeros((PATTERN[0]*PATTERN[1],3),np.float32)
    obj[:,:2]=np.mgrid[0:PATTERN[0],0:PATTERN[1]].T.reshape(-1,2)*SQUARE_MM
    return obj


def synthetic_maps(width,height,supersample=2):
    # Pixel-center-aware supersampling in the original K coordinate system.
    yy,xx=np.indices((height*supersample,width*supersample),dtype=np.float32)
    points=np.stack(((xx+.5)/supersample-.5,(yy+.5)/supersample-.5),axis=-1)
    rays=cv2.undistortPoints(points.reshape(-1,1,2),TRUE_K,TRUE_DIST).reshape(*xx.shape,2)
    return rays[:,:,0].copy(),rays[:,:,1].copy()


def render_board(R,t,rays,rng):
    cols,rows=PATTERN;texel=100;margin=25
    yy,xx=np.indices(((rows+1)*texel,(cols+1)*texel))
    texture=np.where((xx//texel+yy//texel)%2==0,25,235).astype(np.uint8)
    texture=np.pad(texture,margin,constant_values=250)
    inverse=np.linalg.inv(np.column_stack((R[:,:2],t)))
    nx,ny=rays
    denominator=inverse[2,0]*nx+inverse[2,1]*ny+inverse[2,2]
    X=(inverse[0,0]*nx+inverse[0,1]*ny+inverse[0,2])/denominator
    Y=(inverse[1,0]*nx+inverse[1,1]*ny+inverse[1,2])/denominator
    inside=(X>=-SQUARE_MM)&(X<=cols*SQUARE_MM)&(Y>=-SQUARE_MM)&(Y<=rows*SQUARE_MM)
    mapx=((X+SQUARE_MM)*texel/SQUARE_MM-.5+margin).astype(np.float32)
    mapy=((Y+SQUARE_MM)*texel/SQUARE_MM-.5+margin).astype(np.float32)
    image=cv2.remap(texture,mapx,mapy,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=185)
    image=cv2.resize(image,IMAGE_SIZE,interpolation=cv2.INTER_AREA)
    image=cv2.GaussianBlur(image,(3,3),.45)
    image=np.rint(image.astype(np.float32)+rng.normal(0,.4,image.shape)).clip(0,255).astype(np.uint8)
    return image,float(inside.mean())


def choose_pose(pitch,yaw,roll,index,rng):
    R=rotation(pitch,yaw,roll)
    center=np.array([(PATTERN[0]-1)*SQUARE_MM/2,(PATTERN[1]-1)*SQUARE_MM/2,0.])
    desired=np.array([640+rng.uniform(-55,55),480+rng.uniform(-45,45)])
    outer=np.float64([[-25,-25,0],[225,-25,0],[225,175,0],[-25,175,0]])
    perimeter=np.concatenate([np.linspace(outer[i],outer[(i+1)%4],15) for i in range(4)])
    target=343+rng.uniform(-9,9)
    for z in sorted(np.arange(310.,401.,2.),key=lambda x:abs(x-target)):
        camera_center=np.array([(desired[0]-TRUE_K[0,2])*z/TRUE_K[0,0],
                                (desired[1]-TRUE_K[1,2])*z/TRUE_K[1,1],z])
        t=camera_center-R@center
        rvec=cv2.Rodrigues(R)[0]
        edge=cv2.projectPoints(perimeter,rvec,t,TRUE_K,TRUE_DIST)[0].reshape(-1,2)
        projected=cv2.projectPoints(outer,rvec,t,TRUE_K,TRUE_DIST)[0].reshape(-1,2)
        area=cv2.contourArea(projected.astype(np.float32))/(1280*960)
        if edge[:,0].min()>20 and edge[:,0].max()<1260 and edge[:,1].min()>20 and edge[:,1].max()<940 and area>=.315:
            return R,t,dict(pitch_input_deg=pitch,yaw_input_deg=yaw,roll_input_deg=roll,
                           rvec=rvec.ravel().tolist(),tvec_mm=t.tolist(),projected_outer_fraction=area)
    raise ValueError('无法为该姿态生成完整且占比≥30%的棋盘')


def prepare(output_dir=None,seed=9):
    if isinstance(seed,bool) or not isinstance(seed,int) or seed<0:raise ValueError('seed必须为非负整数')
    destination=Path(output_dir or ROOT/'data/calib/lab9_synthetic')
    destination=(destination if destination.is_absolute() else ROOT/destination).resolve()
    parent=(ROOT/'data/calib').resolve()
    if not parent.is_relative_to(ROOT.resolve()):raise ValueError('素材根目录越界')
    if destination==parent or not destination.is_relative_to(parent):raise ValueError('生成目录必须为项目data/calib内的独立子目录')
    if destination.is_symlink() or destination.is_junction():raise ValueError('拒绝链接素材目录')
    if destination.exists():
        manifest=destination/'source_manifest.json'
        if not manifest.is_file():raise ValueError('目标已有未知内容，保留原文件，拒绝覆盖')
        info=json.loads(manifest.read_text(encoding='utf-8'))
        if info.get('generator_version')!=GENERATOR_VERSION or info.get('seed')!=seed:
            raise ValueError('已有生成参数不同，请另选新目录，不覆盖素材')
        for item in info['calibration_views']+info['validation_views']+[info['template']]:
            path=(destination/item['file']).resolve()
            if not path.is_relative_to(destination) or sha256(path)!=item['sha256']:
                raise ValueError('已有素材被修改或来源不符，拒绝覆盖')
        return info
    parent.mkdir(parents=True,exist_ok=True)
    if not parent.is_relative_to(ROOT.resolve()):raise ValueError('素材根目录越界')
    stage=parent/('.stage_lab9_sources_'+uuid.uuid4().hex);stage.mkdir()
    try:
        (stage/'validation').mkdir()
        rays=synthetic_maps(*IMAGE_SIZE)
        rng=np.random.default_rng(seed)
        info=dict(generator_version=GENERATOR_VERSION,seed=seed,time=timestamp(),
                  source_kind='user_authorized_synthetic_camera',
                  authorization='用户明确授权实验九棋盘格图片由程序生成',
                  warning='Synthetic camera only; not measurements of any real phone/camera.',
                  image_size=list(IMAGE_SIZE),pattern_size=list(PATTERN),square_size_mm=SQUARE_MM,
                  true_K=TRUE_K.tolist(),true_dist=TRUE_DIST.tolist(),
                  rendering='inverse pinhole rays with 5-parameter lens distortion; 2x area supersampling, Gaussian sigma .45px, noise sigma .4 DN',
                  calibration_views=[],validation_views=[])
        poses=[(p,y,float(rng.uniform(-7,7))) for p in (-23.,-8.,8.,23.) for y in (-27.,-13.,0.,13.,27.)]
        poses += [(-17.,19.,-5.),(18.,-20.,6.)]
        for i,(pitch,yaw,roll) in enumerate(poses):
            R,t,record=choose_pose(pitch,yaw,roll,i,rng)
            image,fraction=render_board(R,t,rays,rng)
            if fraction<.30:raise ValueError('渲染后棋盘面积不足30%')
            name=f'calib_{i+1:02d}.png' if i<20 else f'validation/validation_{i-19:02d}.png'
            save_png(stage/name,image)
            record.update(file=name,sha256=sha256(stage/name),board_fraction=fraction,
                          true_corners=cv2.projectPoints(object_points(),cv2.Rodrigues(R)[0],t,TRUE_K,TRUE_DIST)[0].reshape(-1,2).tolist())
            info['calibration_views' if i<20 else 'validation_views'].append(record)
        yy,xx=np.indices((8*80,10*80))
        template=np.pad(np.where((xx//80+yy//80)%2==0,0,255).astype(np.uint8),40,constant_values=255)
        save_png(stage/'board_template.png',template)
        info['template']=dict(file='board_template.png',sha256=sha256(stage/'board_template.png'))
        write_text(stage/'source_manifest.json',json.dumps(info,ensure_ascii=False,indent=2,allow_nan=False))
        stage.rename(destination)
    finally:
        if stage.exists():remove_owned(stage,parent)
    return info


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path);parser.add_argument('--seed',type=int,default=9)
    args=parser.parse_args()
    try:
        info=prepare(args.output_dir,args.seed)
        print(f'SUCCESS: synthetic sources; calibration={len(info["calibration_views"])}; held-out={len(info["validation_views"])}; seed={info["seed"]}')
        return 0
    except (OSError,ValueError,cv2.error) as exc:
        print('ERROR: '+str(exc),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
