"""Fixed, Otsu and adaptive Gaussian thresholds with source-derived illumination."""
from __future__ import annotations
import cv2
import numpy as np
from lab4_edges import require_gray


def threshold_segments(image:np.ndarray,fixed_threshold=128) -> dict:
    require_gray(image)
    if isinstance(fixed_threshold,(str,bool)) or not np.isfinite(fixed_threshold) or not 0<=fixed_threshold<=255:
        raise ValueError('固定阈值必须介于 0 和 255 之间')
    _,fixed=cv2.threshold(image,float(fixed_threshold),255,cv2.THRESH_BINARY)
    threshold,otsu=cv2.threshold(image,0,255,cv2.THRESH_BINARY|cv2.THRESH_OTSU)
    return {'fixed':fixed,'otsu':otsu,'otsu_threshold':float(threshold)}


def adaptive_segment(image:np.ndarray,block_size=31,c=5.0) -> np.ndarray:
    require_gray(image)
    if isinstance(block_size,bool) or not isinstance(block_size,(int,np.integer)) or block_size<3 or block_size%2==0:
        raise ValueError('block_size 必须为不小于 3 的奇整数')
    if isinstance(c,(bool,str)) or not np.isfinite(c):
        raise ValueError('adaptive C 必须为有限数值')
    return cv2.adaptiveThreshold(image,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                 cv2.THRESH_BINARY,int(block_size),float(c))


def uneven_illumination(image:np.ndarray,left_gain=0.35,right_gain=1.0) -> tuple[np.ndarray,np.ndarray]:
    require_gray(image)
    if any(isinstance(x,(bool,str)) for x in (left_gain,right_gain)) or not np.isfinite([left_gain,right_gain]).all() or not 0<left_gain<right_gain<=1:
        raise ValueError('光照增益必须满足 0<left<right<=1')
    if image.shape[1]<2:
        raise ValueError('光照派生图至少需要两列像素')
    gain=np.broadcast_to(np.linspace(left_gain,right_gain,image.shape[1],dtype=np.float64),image.shape).copy()
    return np.clip(image.astype(np.float64)*gain,0,255).astype(np.uint8),gain


def binary_statistics(image:np.ndarray) -> dict:
    require_gray(image)
    if not np.isin(image,[0,255]).all():
        raise ValueError('二值统计只接受 0/255 图')
    if image.shape[1]<2:
        return {'white_pixels':int(np.count_nonzero(image)),'white_fraction':float(np.mean(image!=0))}
    middle=image.shape[1]//2
    return {'white_pixels':int(np.count_nonzero(image)),'white_fraction':float(np.mean(image!=0)),
            'left_white_fraction':float(np.mean(image[:,:middle]!=0)),
            'right_white_fraction':float(np.mean(image[:,middle:]!=0))}
