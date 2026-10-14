"""Signed Sobel, explicit-smoothed Canny, hand NMS and 8-neighbor hysteresis."""
from __future__ import annotations
from collections import deque
import cv2
import numpy as np


def require_gray(image: np.ndarray) -> None:
    if not isinstance(image,np.ndarray) or image.dtype!=np.uint8 or image.ndim!=2 or image.size==0:
        raise ValueError('实验四要求非空单通道 uint8 图像')


def unit_gray(values:np.ndarray) -> np.ndarray:
    values=np.asarray(values,dtype=np.float64)
    if values.ndim!=2 or values.size==0 or not np.isfinite(values).all() or np.any(values<0):
        raise ValueError('归一化输入必须为非空有限非负二维数组')
    peak=float(values.max())
    if peak==0:
        return np.zeros(values.shape,np.uint8)
    return np.clip(values/peak*255,0,255).astype(np.uint8)


def sobel_gradients(image:np.ndarray,kernel=3) -> dict:
    require_gray(image)
    if isinstance(kernel,bool) or not isinstance(kernel,(int,np.integer)) or kernel not in (3,5):
        raise ValueError('本实验 Sobel kernel 必须为 3 或 5')
    gx=cv2.Sobel(image,cv2.CV_64F,1,0,ksize=int(kernel),borderType=cv2.BORDER_REFLECT_101)
    gy=cv2.Sobel(image,cv2.CV_64F,0,1,ksize=int(kernel),borderType=cv2.BORDER_REFLECT_101)
    magnitude=np.hypot(gx,gy)
    direction=np.arctan2(gy,gx)
    return {'gx':gx,'gy':gy,'magnitude':magnitude,'direction_radians':direction,
            'gx_display':unit_gray(np.abs(gx)),'gy_display':unit_gray(np.abs(gy)),
            'magnitude_display':unit_gray(magnitude)}


def thresholds(low,high) -> tuple[float,float]:
    if isinstance(low,(bool,str)) or isinstance(high,(bool,str)):
        raise ValueError('Canny 阈值必须为数值')
    low,high=float(low),float(high)
    if not np.isfinite([low,high]).all() or not 0<=low<high:
        raise ValueError('Canny 阈值必须有限且 0<=low<high')
    return low,high


def canny_input(image:np.ndarray,blur_sigma=1.0) -> np.ndarray:
    require_gray(image)
    if isinstance(blur_sigma,(str,bool)) or not np.isfinite(blur_sigma) or blur_sigma<0:
        raise ValueError('canny_blur_sigma 必须为有限非负数')
    if blur_sigma==0:
        return image.copy()
    return cv2.GaussianBlur(image,(0,0),float(blur_sigma),borderType=cv2.BORDER_REFLECT_101)


def canny_edges(image:np.ndarray,low=100,high=200,blur_sigma=1.0) -> np.ndarray:
    low,high=thresholds(low,high)
    # Explicit smoothing: the caller can reproduce this same input in the hand pipeline.
    smoothed=canny_input(image,blur_sigma)
    return cv2.Canny(smoothed,low,high,apertureSize=3,L2gradient=True)


def nonmaximum_suppression(magnitude:np.ndarray,direction:np.ndarray) -> np.ndarray:
    mag=np.asarray(magnitude,dtype=np.float64)
    direction=np.asarray(direction,dtype=np.float64)
    if mag.ndim!=2 or mag.size==0 or mag.shape!=direction.shape or not np.isfinite(mag).all() or not np.isfinite(direction).all() or np.any(mag<0):
        raise ValueError('NMS 幅值与方向必须为同尺寸有限二维数组，幅值非负')
    result=np.zeros_like(mag)
    if min(mag.shape)<3:
        return result
    angle=(np.degrees(direction[1:-1,1:-1])+180)%180
    center=mag[1:-1,1:-1]
    sectors=((angle<22.5)|(angle>=157.5),(angle>=22.5)&(angle<67.5),
             (angle>=67.5)&(angle<112.5),(angle>=112.5)&(angle<157.5))
    # dy is a row derivative (positive downward): 45 degrees uses NW/SE neighbors.
    neighbors=((mag[1:-1,:-2],mag[1:-1,2:]),(mag[:-2,:-2],mag[2:,2:]),
               (mag[:-2,1:-1],mag[2:,1:-1]),(mag[:-2,2:],mag[2:,:-2]))
    target=result[1:-1,1:-1]
    for sector,(before,after) in zip(sectors,neighbors):
        # Strict on one side breaks flat plateaus into a single retained side.
        keep=sector&(center>before)&(center>=after)
        target[keep]=center[keep]
    return result


def hysteresis(nms:np.ndarray,low=100,high=200) -> np.ndarray:
    low,high=thresholds(low,high)
    nms=np.asarray(nms,dtype=np.float64)
    if nms.ndim!=2 or nms.size==0 or not np.isfinite(nms).all() or np.any(nms<0):
        raise ValueError('滞后连接需要有限非负二维幅值')
    eligible=(nms>=low)&(nms>0)
    selected=(nms>=high)&(nms>0)
    queue=deque(map(tuple,np.argwhere(selected)))
    h,w=nms.shape
    while queue:
        y,x=queue.popleft()
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                yy,xx=y+dy,x+dx
                if 0<=yy<h and 0<=xx<w and eligible[yy,xx] and not selected[yy,xx]:
                    selected[yy,xx]=True
                    queue.append((yy,xx))
    return selected.astype(np.uint8)*255


def manual_canny(image:np.ndarray,low=100,high=200,blur_sigma=1.0) -> dict:
    thresholds(low,high)
    smoothed=canny_input(image,blur_sigma)
    sobel=sobel_gradients(smoothed,3)
    nms=nonmaximum_suppression(sobel['magnitude'],sobel['direction_radians'])
    return {'smoothed':smoothed,'nms':nms,'nms_display':unit_gray(nms),
            'edges':hysteresis(nms,low,high)}


def edge_agreement(a:np.ndarray,b:np.ndarray) -> dict:
    require_gray(a)
    require_gray(b)
    if a.shape!=b.shape or not np.isin(a,[0,255]).all() or not np.isin(b,[0,255]).all():
        raise ValueError('一致性比较需要同尺寸 0/255 边缘图')
    aa,bb=a!=0,b!=0
    union=int(np.count_nonzero(aa|bb))
    intersection=int(np.count_nonzero(aa&bb))
    return {'different_pixels':int(np.count_nonzero(aa!=bb)),
            'different_fraction':float(np.mean(aa!=bb)),
            'intersection':intersection,'union':union,'iou':intersection/union if union else 1.0}
