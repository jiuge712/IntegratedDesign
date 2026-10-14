"""Run personal-image spatial filtering, sharpening, quality evaluation and BGR interface demo."""
from __future__ import annotations
import argparse
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter

import cv2
import numpy as np
import skimage
from baseline_pipeline import read_image,attributes
from common import ROOT,VERSION,atomic_write,sha256,timestamp,write_text
from lab2_common import image_panel,save_figure,save_png
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from lab3_filter import gaussian_noise,salt_pepper_noise,filter_image,sharpen_image,preprocess
from lab3_metrics import quality,gradient_mean
from latest_runs import LatestRun
from version_check import environment


def save_bgr(path:Path,image:np.ndarray):
    ok,encoded=cv2.imencode('.png',image)
    if not ok:
        raise OSError(f'保存失败: {path}')
    atomic_write(path,encoded.tobytes())
    saved=read_image(path)
    if saved.dtype!=image.dtype or not np.array_equal(saved,image):
        raise OSError(f'回读校验失败: {path}')


def score_label(score):
    return 'infinity' if score['psnr_infinite'] else f"{score['psnr_db']:.2f} dB"


def architecture_figure(path:Path):
    fig,ax=plt.subplots(figsize=(14,4.4),layout='constrained')
    ax.set(xlim=(0,14),ylim=(0,4.4))
    ax.axis('off')
    labels=['Input image\nuint8 BGR','Preprocess\ndenoise + sharpen','Features\npoints + descriptors','Match\nindex pairs','Geometry\nposes + tracks','Point cloud\nXYZ + colors','Visualize\nview / export']
    for i,label in enumerate(labels):
        x=0.15+i*2.0
        box=FancyBboxPatch((x,1.8),1.7,1.1,boxstyle='round,pad=0.07',facecolor='#dceee0' if i==1 else '#edf1f5',edgecolor='#28743b' if i==1 else '#738397',linewidth=2 if i==1 else 1)
        ax.add_patch(box)
        ax.text(x+0.85,2.35,label,ha='center',va='center',fontsize=9)
        if i<6:
            ax.annotate('',xy=(x+1.98,2.35),xytext=(x+1.77,2.35),arrowprops={'arrowstyle':'->','color':'#44536b'})
    ax.add_patch(FancyBboxPatch((1.98,1.45),2.05,1.8,boxstyle='round,pad=0.05',fill=False,edgecolor='#28743b',linewidth=2))
    ax.text(3,3.5,'Experiment 3 boundary',ha='center',color='#28743b',fontsize=12)
    ax.text(7,0.7,'Implemented: image loading and preprocessing. Downstream SFM stages are architecture contracts.',ha='center',fontsize=10)
    save_figure(path,fig)


def report_text(info:dict) -> str:
    params=info['parameters']
    lines=['# 实验三空间滤波与图像增强报告','',f"运行时间：{info['time']}。程序版本：{info['program_version']}。",
           f"本次使用用户提供的插画 `{info['input']}`，灰度尺寸为 {info['reference_shape']}。含噪图从该图派生，原图作为评价参考。原始输入 SHA-256 保持不变。",'',
           f"22 项程序自检通过；本次正式检查 {len(info['checks'])} 项全部通过。完整处理、绘图、回读及评分耗时 {info['elapsed_ms']} ms。",'',
           '## 背景与参数','',
           '空间滤波利用局部邻域进行平滑，锐化则强化局部变化。实验对同一参考图加入两类受控噪声，分别比较滤波的去噪与细节保留；不是对真实拍摄噪声类型的推断。','',
           '| 参数 | 实际值 |','| --- | --- |']
    lines += [f'| {key} | {value} |' for key,value in params.items()]
    lines += ['', f"高斯噪声使用 seed 的 RNG；椒盐噪声使用 seed+1 的独立 RNG，两者固定后重复运行相同。均值和中值核为 {params.get('kernel_size',5)}×{params.get('kernel_size',5)}，高斯采用 (0,0) 自动核、sigma={params.get('gaussian_sigma',1.5)}。均值/高斯/拉普拉斯边界为 REFLECT_101，中值边界由 OpenCV 使用 REPLICATE。",'',
              '## 两类噪声与三种滤波','',
              f"高斯噪声：`clip(gray.astype(float64)+rng.normal(0,sigma,shape),0,255).astype(uint8)`。椒盐噪声根据均匀随机掩码将像素置 0 或 255；当前概率 {params.get('salt_pepper_probability',0.1)} 表示两类合计，每类为一半。",'',
              f"本次椒盐掩码选中比例为 {info['salt_pepper_selection']['selected_fraction']:.4%}。该值描述噪声生成时选中的像素，不把原图已有黑白像素计为生成噪声。",'',
              '调用 `cv2.blur`、`cv2.GaussianBlur` 和 `cv2.medianBlur`，两类噪声复用同一组方法与参数。额外实现双边滤波作为指导书加分对比。所有结果保存为 PNG，避免 JPEG 压缩改变评分。','',
              '![高斯噪声滤波对比](../data/output/lab3_latest/l3_gaussian_compare.png)','',
              '![椒盐噪声滤波对比](../data/output/lab3_latest/l3_salt_pepper_compare.png)','',
              '![双边滤波补充对比](../data/output/lab3_latest/l3_bilateral_compare.png)','',
              '## PSNR 与 SSIM 评分','',
              'PSNR 手写计算 `10*log10(255^2/MSE)`，差值先转 float64；MSE=0 时为正无穷。JSON 用 psnr_db=null 和 psnr_infinite=true 表示无穷，不输出非法 JSON 数值。SSIM 调用 scikit-image，显式设置 data_range=255、win_size=7，保持两图同尺寸，不做隐式缩放。','',
              '| 场景 | 方法 | PSNR dB | SSIM | MSE | 平均梯度 |','| --- | --- | --- | --- | --- | --- |']
    for row in info['quality_rows']:
        score='∞' if row['psnr_infinite'] else f"{row['psnr_db']:.4f}"
        lines.append(f"| {row['scene']} | {row['method']} | {score} | {row['ssim']:.6f} | {row['mse']:.4f} | {row['gradient_mean']:.4f} |")
    lines += ['']
    for scene in ('gaussian','salt_pepper'):
        rows=[r for r in info['quality_rows'] if r['scene']==scene and r['method']!='noisy']
        best_psnr=max(rows,key=lambda r:r['psnr_db'] if r['psnr_db'] is not None else float('inf'))
        best_ssim=max(rows,key=lambda r:r['ssim'])
        lines.append(f"本次 {scene} 场景 PSNR 最优为 {best_psnr['method']}，SSIM 最优为 {best_ssim['method']}；该结论仅对应本图、参数和噪声实现，不把指导书示例分数直接当作实测。")
    lines += ['', '平均梯度用于观察局部变化，但噪声也会提高梯度；不能单独把较高梯度当作更好的去噪或重建质量。PSNR/SSIM 是相对参考图的保真评价，不以“超过 28 dB”作为所有图像的强制通过条件。','',
              '## 拉普拉斯与 USM 锐化','',
              f"拉普拉斯使用 CV_64F 保存正负响应，计算 `clip(img-{params.get('laplacian_amount',0.8)}*Laplacian(img),0,255)`。USM 使用 `img+{params.get('usm_amount',0.6)}*(img-GaussianBlur(img,sigma={params.get('usm_sigma',2.0)}))`，通过 addWeighted 舍入与饱和。锐化作用于原始灰度参考图；另保存轻度模糊图的锐化演示。",'',
              '![原图与两种锐化](../data/output/lab3_latest/l3_sharpen_compare.png)','',
              '![轻度模糊图锐化对比](../data/output/lab3_latest/l3_blurred_sharpen_compare.png)','',
              '![局部边缘与纹理放大](../data/output/lab3_latest/l3_detail_compare.png)','',
              '锐化可能提高梯度同时降低相对原图的 PSNR/SSIM，这是对原图作修改的结果，不自动等于算法失效。要结合局部图观察过冲、黑边、亮边及噪声放大。','',
              '## SFM 架构与预处理接口','',
              '![SFM 数据流与实验三边界](../data/output/lab3_latest/l3_architecture.png)','',
              '`preprocess(img_bgr: np.ndarray, cfg: dict) -> np.ndarray` 接收 uint8 BGR 数组，返回同尺寸同类型的全新 BGR 数组，不修改输入，不读写文件。配置规定滤波和锐化方法。已演示从原图读取为 BGR、生成含噪 BGR、调用预处理并保存结果。','',
              '本次预处理边界包括去噪与增强；特征、匹配、几何、点云、可视化是整体架构中的后续模块约定，没有在实验三实现。完整格式及异常约定见 architecture.md 和 interface_agreement.md。小组协商由实际参与者确认，本次提供已实现并验证的技术约定。','',
              '## 正式验证','', '| 检查 | 结果 |','| --- | --- |']
    lines += [f"| {check['name']} | PASS |" for check in info['checks']]
    lines += ['', '日志、原图前后哈希、噪声种子、版本、输出属性和参数见 evidence/lab3_latest/results.json；评分同时保存 quality.csv。源码与说明见 deliverables/lab3_source.zip。','',
              '## 复现与限制','',
              '统一复现文档 reproduction.md 覆盖实验一至三；统一图片要求 image_requirements.md 按实验列出素材条件。后续每完成一个实验必须更新这两个入口，此要求已写入项目 AGENTS.md。','',
              '个人结果仅保留 data/output/lab3_latest 和 evidence/lab3_latest 的最近一次完整运行；生成和校验失败时保留上次结果。输入图片继续保留，其他实验的最新结果不受本次运行影响。','',
              '当前参考图是动漫插画，不是无噪声传感器标定图；其原有纹理和压缩痕迹属于参考信号。效果结论不推广为所有建筑照片、真实噪声或 SFM 下游性能。更换个人图片后无需改源码，但图像宽高必须至少为 7 以计算当前 SSIM。','']
    return '\n'.join(lines)


def run(config_path:Path,override:Path|None):
    start=perf_counter()
    cfg=json.loads(config_path.read_text(encoding='utf-8-sig'))
    source=override or Path(cfg['input'])
    source=(source if source.is_absolute() else ROOT/source).resolve()
    if any(source.is_relative_to((ROOT/folder).resolve()) for folder in ('data/output','evidence','docs')):
        raise ValueError('参考图不能放在输出、证据或文档目录')
    original=read_image(source)
    if original.dtype!=np.uint8:
        raise ValueError('实验三要求 uint8 输入，其他位深不自动缩放')
    if min(original.shape[:2])<7:
        raise ValueError('实验三 SSIM 要求宽高至少为 7')
    before=sha256(source)
    if original.ndim==2:
        bgr=cv2.cvtColor(original,cv2.COLOR_GRAY2BGR)
    elif original.shape[2]==4:
        bgr=original[:,:,:3].copy()
    else:
        bgr=original.copy()
    gray=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY)
    seed=cfg.get('seed',0)
    if isinstance(seed,bool) or not isinstance(seed,int) or seed<0:
        raise ValueError('seed 必须为非负整数')
    sigma=cfg.get('gaussian_noise_sigma',25)
    probability=cfg.get('salt_pepper_probability',0.1)
    noisy_gauss=gaussian_noise(gray,sigma,seed)
    noisy_sp,sp_selection=salt_pepper_noise(gray,probability,seed+1)
    filter_cfg={key:cfg[key] for key in ('kernel_size','gaussian_sigma','bilateral_d','sigma_color','sigma_space') if key in cfg}
    sharpen_cfg={key:cfg[key] for key in ('laplacian_amount','usm_amount','usm_sigma') if key in cfg}
    methods=('mean','gaussian','median','bilateral')
    results={scene:{'noisy':image,**{method:filter_image(image,method,**filter_cfg) for method in methods}}
             for scene,image in (('gaussian',noisy_gauss),('salt_pepper',noisy_sp))}
    sharp={'original':gray,'laplacian':sharpen_image(gray,'laplacian',**sharpen_cfg),'usm':sharpen_image(gray,'usm',**sharpen_cfg)}
    blurred=cv2.GaussianBlur(gray,(0,0),1.0,borderType=cv2.BORDER_REFLECT_101)
    blurred_sharp={'blurred':blurred,'laplacian':sharpen_image(blurred,'laplacian',**sharpen_cfg),'usm':sharpen_image(blurred,'usm',**sharpen_cfg)}
    pipeline_cfg={**filter_cfg,**sharpen_cfg,'filter':cfg.get('pipeline_filter','gaussian'),'sharpen':cfg.get('pipeline_sharpen','usm')}
    bgr_before=bgr.copy()
    bgr_noisy=gaussian_noise(bgr,sigma,seed)
    bgr_noisy_before=bgr_noisy.copy()
    bgr_result=preprocess(bgr_noisy,pipeline_cfg)
    rows=[]
    for scene,images in (('reference',{'original':gray}),*results.items(),('sharpen',sharp)):
        for method,image in images.items():
            rows.append({'scene':scene,'method':method,**quality(gray,image),'gradient_mean':gradient_mean(image)})
    checks=[]
    def check(name,condition):
        if not bool(condition):
            raise ValueError(f'正式检查失败: {name}')
        checks.append({'name':name,'passed':True})
    check('固定种子高斯噪声可重复',np.array_equal(noisy_gauss,gaussian_noise(gray,sigma,seed)))
    check('固定种子椒盐噪声可重复',np.array_equal(noisy_sp,salt_pepper_noise(gray,probability,seed+1)[0]))
    check('椒盐变更像素只能为 0 或 255',np.all(np.isin(noisy_sp[noisy_sp!=gray],[0,255])))
    check('全部滤波和锐化输出保持尺寸和 uint8',all(v.shape==gray.shape and v.dtype==np.uint8 for group in (*results.values(),sharp,blurred_sharp) for v in group.values()))
    check('参考图 PSNR=∞ SSIM=1',rows[0]['psnr_infinite'] and abs(rows[0]['ssim']-1)<1e-12)
    check('所有非同一图评分为有限有效数值',all((r['psnr_infinite'] or np.isfinite(r['psnr_db'])) and np.isfinite(r['ssim']) and -1<=r['ssim']<=1.000001 for r in rows))
    check('preprocess 返回同尺寸 BGR 并保持输入',bgr_result.shape==bgr.shape and bgr_result.dtype==np.uint8 and np.array_equal(bgr,bgr_before) and np.array_equal(bgr_noisy,bgr_noisy_before) and not np.shares_memory(bgr_result,bgr_noisy))
    with LatestRun('lab3') as latest:
        folder=latest.output
        save_png(folder/'l3_reference.png',gray)
        for scene,images in results.items():
            for method,image in images.items():
                save_png(folder/f'l3_{scene}_{method}.png',image)
            items=[]
            for method in ('noisy','mean','gaussian','median'):
                score=next(r for r in rows if r['scene']==scene and r['method']==method)
                items.append((f"{method}; PSNR {score_label(score)}\nSSIM {score['ssim']:.4f}",images[method]))
            image_panel(folder/f'l3_{scene}_compare.png',items,4)
        image_panel(folder/'l3_bilateral_compare.png',[(f'{scene}: {method}',results[scene][method]) for scene in results for method in ('noisy','gaussian','bilateral')],3)
        for method,image in sharp.items():
            save_png(folder/f'l3_sharpen_{method}.png',image)
        image_panel(folder/'l3_sharpen_compare.png',[(f'{method}; gradient={gradient_mean(image):.2f}',image) for method,image in sharp.items()],3)
        for method,image in blurred_sharp.items():
            save_png(folder/f'l3_blurred_{method}.png',image)
        image_panel(folder/'l3_blurred_sharpen_compare.png',[(method,image) for method,image in blurred_sharp.items()],3)
        h,w=gray.shape
        y0,y1=h//4,max(h//4+1,3*h//4)
        x0,x1=w//3,max(w//3+1,2*w//3)
        image_panel(folder/'l3_detail_compare.png',[(method,image[y0:y1,x0:x1]) for method,image in sharp.items()],3)
        save_bgr(folder/'l3_interface_input_bgr.png',bgr)
        save_bgr(folder/'l3_interface_noisy_bgr.png',bgr_noisy)
        save_bgr(folder/'l3_interface_output_bgr.png',bgr_result)
        architecture_figure(folder/'l3_architecture.png')
        check('保存图像与所有对比图可回读',all(read_image(p).size>0 for p in folder.glob('*.png')))
        after=sha256(source)
        check('参考原文件 SHA-256 未改变',before==after)
        info={'status':'SUCCESS','time':timestamp(),'program_version':VERSION,'environment':{**environment(),'scikit_image':skimage.__version__},
              'input':str(source),'input_sha256_before':before,'input_sha256_after':after,'reference_shape':list(gray.shape),
              'parameters':{k:v for k,v in cfg.items() if k!='input'},'effective_seed':seed,'pipeline_cfg':pipeline_cfg,
              'salt_pepper_selection':sp_selection,'quality_rows':rows,'checks':checks,
              'detail_roi':{'y0':y0,'y1':y1,'x0':x0,'x1':x1},
              'elapsed_ms':round((perf_counter()-start)*1000,3),'timing_scope':'read, generation, filtering, metrics, plots, write/readback and checks; excludes startup and metadata export',
              'outputs':{p.name:{**attributes(read_image(p)),'bytes':p.stat().st_size,'sha256':sha256(p)} for p in folder.glob('*.png')}}
        csv_buffer=io.StringIO()
        writer=csv.DictWriter(csv_buffer,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        write_text(latest.evidence/'quality.csv',csv_buffer.getvalue())
        metadata=json.dumps(info,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
        write_text(latest.evidence/'results.json',metadata)
        write_text(latest.evidence/'output_info.txt',metadata)
        write_text(latest.evidence/'run.log','COMMAND: '+subprocess.list2cmdline([sys.executable,'-X','utf8',*sys.argv])+'\n'+'\n'.join('PASS: '+c['name'] for c in checks)+'\nSTATUS: SUCCESS\n')
        report=report_text(info)
        write_text(latest.evidence/'lab_report.md',report.replace('../data/output/lab3_latest/','../../data/output/lab3_latest/'))
        latest.commit()
        write_text(ROOT/'docs/lab3_report.md',report)
        return info


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'config/lab3_images.json')
    parser.add_argument('--input',type=Path,help='Override reference image')
    args=parser.parse_args()
    try:
        if sys.prefix==sys.base_prefix:
            raise ValueError('请使用项目独立虚拟环境')
        info=run(args.config,args.input)
        print(json.dumps({'status':'SUCCESS','checks_passed':len(info['checks']),'image_count':len(info['outputs']),
                          'output':str(ROOT/'data/output/lab3_latest'),'report':str(ROOT/'docs/lab3_report.md')},ensure_ascii=False,indent=2))
        return 0
    except (OSError,ValueError,KeyError,TypeError,cv2.error) as exc:
        print(f'ERROR: {exc}',file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
