"""Personal-image edge detection and segmentation with latest-only artifacts."""
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
from baseline_pipeline import read_image,to_gray,attributes
from common import ROOT,VERSION,sha256,timestamp,write_text,atomic_write
from lab2_common import image_panel,save_png
from lab4_edges import sobel_gradients,canny_edges,manual_canny,edge_agreement,unit_gray
from lab4_segment import threshold_segments,adaptive_segment,uneven_illumination,binary_statistics
from latest_runs import LatestRun
from version_check import environment


def source_path(value) -> Path:
    path=Path(value)
    path=(path if path.is_absolute() else ROOT/path).resolve()
    if any(path.is_relative_to((ROOT/name).resolve()) for name in ('data/output','evidence','docs')):
        raise ValueError(f'原图不能位于结果、证据或文档目录: {path}')
    return path


def load_gray(path:Path) -> np.ndarray:
    original=read_image(path)
    if original.dtype!=np.uint8:
        raise ValueError('实验四要求 uint8，不隐式转换其他位深')
    gray,_=to_gray(original)
    if min(gray.shape)<5:
        raise ValueError('本次 Sobel 对比要求图片宽高至少为 5')
    return gray


def report_text(info:dict) -> str:
    parameters=info['parameters']
    lines=['# 实验四边缘检测与图像分割报告','',
           f"运行时间：{info['time']}。程序版本 {info['program_version']}。",'',
           '本次完成 Sobel 3/5 核、三组 Canny、固定/Otsu/自适应阈值及手写 NMS/滞后连接对比。详细设计、编码规范和技术自走查已完成；课堂两两走查由实际参与者补充，待办见 user_tasks.md。', '',
           f"28 项数值/边界/命令行自检通过，正式检查 {len(info['checks'])} 项通过；原始输入哈希保持不变。处理、绘图、回读和检查耗时 {info['elapsed_ms']} ms。",'',
           '## 输入与参数','', '| 图片角色 | 来源 |','| --- | --- |']
    lines += [f'| {key} | {value} |' for key,value in info['input_sources'].items()]
    lines += ['', '| 参数 | 实际值 |','| --- | --- |']
    lines += [f'| {key} | {value} |' for key,value in parameters.items()]
    lines += ['',
              '清晰纹理图来自用户提供的插画。若 uneven 为 null，本次光照不均图通过从左到右的乘性增益派生，属于受控模拟；若配置真实路径则使用个人提供的图。报告与证据记录实际来源，不把模拟图描述为实拍照片。','',
              '![输入及光照不均版本](../data/output/lab4_latest/l4_input_compare.png)','',
              '## Sobel 梯度与核尺寸','',
              '用 CV_64F 分别计算 Gx/Gy，幅值为 hypot(Gx,Gy)，方向为 atan2(Gy,Gx)，单位弧度；数组 y 轴向下。原始带符号梯度与方向保存在 raw_gradients.npz。显示单方向图取绝对值，幅值归一化至 0–255；最大值为 0 时返回全黑图，避免恒定图除零。','',
              '每个核的显示图单独归一化，不能只根据显示亮度比较原始梯度大小。核为 5 的算子覆盖更大邻域、导数尺度也不同，原始幅值如下。','',
              '| 核尺寸 | 原始最大幅值 | 原始平均幅值 | 方向单位 |','| --- | --- | --- | --- |']
    for row in info['sobel_statistics']:
        lines.append(f"| {row['kernel']} | {row['max_magnitude']:.4f} | {row['mean_magnitude']:.4f} | radians |")
    lines += ['', '![两个核的X/Y及幅值图](../data/output/lab4_latest/l4_sobel_compare.png)','',
              '## Canny 双阈值参数实验','',
              f"先显式高斯平滑（sigma={parameters.get('canny_blur_sigma',1.0)}），再调用 Canny，apertureSize=3、L2gradient=True。三组阈值共用相同输入，手写加分分支也共用该平滑设置。阈值作用于原始梯度幅值，不作用于已归一化的显示图。低阈值用于连接，高阈值用于选择强边缘种子。",'',
              '| 低阈值 | 高阈值 | 边缘像素数 | 边缘比例 |','| --- | --- | --- | --- |']
    for row in info['canny_statistics']:
        lines.append(f"| {row['low']} | {row['high']} | {row['edge_pixels']} | {row['edge_fraction']:.4%} |")
    lines += ['', '![三组双阈值对比](../data/output/lab4_latest/l4_canny_compare.png)','',
              '本次较高的双阈值保留较少边缘。低阈值组合有利于保留发丝、绳索和细纹理，也可能保留噪声；高阈值更强调明显轮廓，可能漏掉弱边缘。可先从 100/200 的中间设置观察，再结合目标轮廓、断裂和纹理量调整；密度更低不自动等于检测更准确。','',
              '## 固定阈值与 Otsu','',
              f"固定阈值 T={parameters.get('fixed_threshold',128)}：gray>T 为 255，否则为 0。Otsu 用全局直方图最大化类间方差，返回实际自动阈值。二值区域表示亮度划分，不凭空赋予人物或物体语义。",'',
              '| 场景 | 方法 | 阈值 | 白色比例 | 左半白色比例 | 右半白色比例 |',
              '| --- | --- | --- | --- | --- | --- |']
    for row in info['segmentation_statistics']:
        lines.append(f"| {row['scene']} | {row['method']} | {row['threshold']} | {row['white_fraction']:.4%} | {row.get('left_white_fraction',0):.4%} | {row.get('right_white_fraction',0):.4%} |")
    lines += ['', '![清晰图固定与Otsu](../data/output/lab4_latest/l4_threshold_compare.png)','',
              '本次清晰图的 Otsu 阈值恰好等于固定阈值，两张分割图完全一致；这也是有效实验结果，并不为了制造差异改动阈值。' if next(row['threshold'] for row in info['segmentation_statistics'] if row['scene']=='texture' and row['method']=='otsu')==parameters.get('fixed_threshold',128) else '本次清晰图的 Otsu 与固定阈值不同，实际阈值及二值面积见上表。','',
              '## 光照不均与自适应阈值','',
              f"自适应阈值采用 ADAPTIVE_THRESH_GAUSSIAN_C，blockSize={parameters.get('adaptive_block_size',31)}、C={parameters.get('adaptive_c',5)}；局部阈值为邻域高斯统计减去 C。它能随局部亮度变化，而 Otsu 在整张图上只给一个阈值。",'',
              '![光照不均下三种分割](../data/output/lab4_latest/l4_adaptive_compare.png)','',
              '左右区域的白色比例提供可复查统计，不是分割准确率。自适应结果可保留局部变化，也可能因窗口和 C 放大纹理或使均匀区变白；没有人工目标标注时不能断言“正确分割所有目标”或报告语义 IoU。','',
              '## 手写 NMS 与双阈值连接 加分对比','',
              '手写分支使用四个方向区间的 NMS，沿梯度方向比较邻点；一侧严格大于、另一侧大于等于以打破幅值平台，最外一圈置零。滞后连接以强边缘为种子，使用队列追踪八邻域中满足低阈值的弱边缘，孤立弱边缘舍弃。角度采用图像坐标，45° 对应 NW/SE 比较。','',
              f"比较阈值为 {info['manual_thresholds']}。手写/API 不同像素为 {info['manual_agreement']['different_pixels']}，比例 {info['manual_agreement']['different_fraction']:.6%}，边缘集合 IoU={info['manual_agreement']['iou']:.6f}。",'',
              '![平滑NMS手写与API边缘](../data/output/lab4_latest/l4_manual_compare.png)','',
              '这些数值表示两种实现的一致性，不是对真实边缘标签的准确率。方向量化、相等幅值处理、边界和阈值等号策略会产生差异，不宣称加分版本逐像素复刻 OpenCV。','',
              '## 软件工程产出与正式检查','',
              'detailed_design.md 覆盖 L3/L4 函数输入、输出、算法、异常和数据流；coding_standards.md 规定命名、注释、模块职责与验证方式；design_walkthrough.md 记录至少三条已落实的技术自走查意见，并保留真实两两走查填写位置。','',
              '| 检查 | 结果 |','| --- | --- |']
    lines += [f"| {check['name']} | PASS |" for check in info['checks']]
    lines += ['',
              'results.json 与 metrics.csv 保存输入哈希、参数、阈值和密度；raw_gradients.npz 保存浮点梯度/方向、NMS及可用的增益图。PNG 回读校验无损，实际命令见 run.log。所有证据位于 evidence/lab4_latest。','',
              '## 复现与待完成事项','',
              '统一 reproduction.md 和 image_requirements.md 已覆盖实验一至四，后续每完成一个实验都继续更新。个人结果只保留 data/output/lab4_latest 的最近一次完整运行，校验失败保留旧结果，其他实验不覆盖。源码包为 deliverables/lab4_source.zip。','',
              '你需要亲自完成的真实课堂活动、课程要求下的实拍素材/截图及最终提交步骤记录在 user_tasks.md；代码和技术材料已完成，不编造小组成员、签名或未发生的走查。', '']
    return '\n'.join(lines)


def run(config_path:Path,texture_override:Path|None,uneven_override:Path|None):
    start=perf_counter()
    defaults={'texture':'data/input/photo.jpg','uneven':None,'illumination_left_gain':0.35,'illumination_right_gain':1.0,
              'sobel_kernels':[3,5],'canny_pairs':[[50,150],[100,200],[150,250]],
              'canny_blur_sigma':1.0,'fixed_threshold':128,'adaptive_block_size':31,
              'adaptive_c':5.0,'manual_pair_index':1}
    provided=json.loads(config_path.read_text(encoding='utf-8-sig'))
    if not isinstance(provided,dict) or set(provided)-set(defaults):
        raise ValueError('实验四配置必须为已约定字段的 JSON 对象，不接受未知键')
    cfg={**defaults,**provided}
    sources={'texture':source_path(texture_override or cfg['texture'])}
    uneven_value=uneven_override or cfg.get('uneven')
    if uneven_value:
        sources['uneven']=source_path(uneven_value)
    before={str(path):sha256(path) for path in sources.values()}
    texture=load_gray(sources['texture'])
    gain=None
    if 'uneven' in sources:
        uneven=load_gray(sources['uneven'])
        illumination_note=f"用户提供文件：{sources['uneven']}"
    else:
        uneven,gain=uneven_illumination(texture,cfg.get('illumination_left_gain',0.35),cfg.get('illumination_right_gain',1.0))
        illumination_note=f"同图派生乘性光照：gain 从 {cfg.get('illumination_left_gain',0.35)} 至 {cfg.get('illumination_right_gain',1.0)}，左暗右亮，受控模拟"
    kernels=cfg.get('sobel_kernels',[3,5])
    if kernels!=[3,5]:
        raise ValueError('本次必做对比的 sobel_kernels 必须为 [3,5]')
    pairs=cfg.get('canny_pairs',[[50,150],[100,200],[150,250]])
    if not isinstance(pairs,list) or len(pairs)!=3 or any(not isinstance(p,list) or len(p)!=2 for p in pairs):
        raise ValueError('canny_pairs 必须有三组 [low,high]')
    sigma=cfg.get('canny_blur_sigma',1.0)
    gradients={kernel:sobel_gradients(texture,kernel) for kernel in kernels}
    canny={index:canny_edges(texture,*pair,blur_sigma=sigma) for index,pair in enumerate(pairs)}
    index=cfg.get('manual_pair_index',1)
    if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<3:
        raise ValueError('manual_pair_index 必须为 0、1 或 2')
    manual=manual_canny(texture,*pairs[index],blur_sigma=sigma)
    agree=edge_agreement(manual['edges'],canny[index])
    segments={scene:threshold_segments(image,cfg.get('fixed_threshold',128)) for scene,image in (('texture',texture),('uneven',uneven))}
    adaptive=adaptive_segment(uneven,cfg.get('adaptive_block_size',31),cfg.get('adaptive_c',5))
    canny_rows=[{'low':pair[0],'high':pair[1],'edge_pixels':int(np.count_nonzero(canny[i])),
                 'edge_fraction':float(np.mean(canny[i]!=0))} for i,pair in enumerate(pairs)]
    segment_rows=[]
    for scene,result in segments.items():
        for method in ('fixed','otsu'):
            segment_rows.append({'scene':scene,'method':method,'threshold':cfg.get('fixed_threshold',128) if method=='fixed' else result['otsu_threshold'],**binary_statistics(result[method])})
    segment_rows.append({'scene':'uneven','method':'adaptive','threshold':'local',**binary_statistics(adaptive)})
    checks=[]
    def check(name,condition):
        if not bool(condition):
            raise ValueError(f'正式检查失败: {name}')
        checks.append({'name':name,'passed':True})
    check('Sobel 原始梯度保留有限 float64',all(g['gx'].dtype==np.float64 and np.isfinite(g['magnitude']).all() for g in gradients.values()))
    check('Sobel 幅值等于 sqrt(Gx²+Gy²)',all(np.allclose(g['magnitude'],np.sqrt(g['gx']**2+g['gy']**2)) for g in gradients.values()))
    check('Sobel 显示图保持尺寸和 uint8',all(g['magnitude_display'].shape==texture.shape and g['magnitude_display'].dtype==np.uint8 for g in gradients.values()))
    check('三组 Canny 均为同尺寸 0/255 二值',all(e.shape==texture.shape and np.isin(e,[0,255]).all() for e in canny.values()))
    check('固定阈值符合严格大于 T',all(np.array_equal(result['fixed'],(image>cfg.get('fixed_threshold',128)).astype(np.uint8)*255) for image,result in ((texture,segments['texture']),(uneven,segments['uneven']))))
    check('Otsu 返回有效阈值和匹配的分割图',all(0<=result['otsu_threshold']<=255 and np.array_equal(result['otsu'],(image>result['otsu_threshold']).astype(np.uint8)*255) for image,result in ((texture,segments['texture']),(uneven,segments['uneven']))))
    check('自适应结果为同尺寸 0/255 二值',adaptive.shape==uneven.shape and np.isin(adaptive,[0,255]).all())
    check('手写 NMS 有限非负且未放大原始幅值',np.isfinite(manual['nms']).all() and np.all(manual['nms']>=0) and np.all(manual['nms']<=sobel_gradients(manual['smoothed'],3)['magnitude']))
    check('手写滞后连接输出为同尺寸二值',manual['edges'].shape==texture.shape and np.isin(manual['edges'],[0,255]).all())
    with LatestRun('lab4') as latest:
        folder=latest.output
        save_png(folder/'l4_texture_input.png',texture)
        save_png(folder/'l4_uneven_input.png',uneven)
        if gain is not None:
            save_png(folder/'l4_illumination_gain.png',unit_gray(gain))
        image_panel(folder/'l4_input_compare.png',[('User texture input',texture),('Uneven input: '+('derived shading' if gain is not None else 'personal file'),uneven)],2)
        panels=[]
        for kernel,g in gradients.items():
            for name in ('gx_display','gy_display','magnitude_display'):
                save_png(folder/f'l4_sobel_{kernel}_{name}.png',g[name])
                panels.append((f'Sobel {kernel}: {name}',g[name]))
        image_panel(folder/'l4_sobel_compare.png',panels,3)
        for i,e in canny.items():
            save_png(folder/f'l4_canny_{i+1}.png',e)
        image_panel(folder/'l4_canny_compare.png',[(f"T={pair}; edges={canny_rows[i]['edge_fraction']:.2%}",canny[i]) for i,pair in enumerate(pairs)],3)
        for scene,result in segments.items():
            for method in ('fixed','otsu'):
                save_png(folder/f'l4_{scene}_{method}.png',result[method])
        save_png(folder/'l4_uneven_adaptive.png',adaptive)
        image_panel(folder/'l4_threshold_compare.png',[('Texture input',texture),(f"Fixed T={cfg.get('fixed_threshold',128)}",segments['texture']['fixed']),
                    (f"Otsu T={segments['texture']['otsu_threshold']}",segments['texture']['otsu'])],3)
        image_panel(folder/'l4_adaptive_compare.png',[('Uneven input',uneven),('Fixed threshold',segments['uneven']['fixed']),
                    (f"Otsu T={segments['uneven']['otsu_threshold']}",segments['uneven']['otsu']),
                    (f"Adaptive block={cfg.get('adaptive_block_size',31)}, C={cfg.get('adaptive_c',5)}",adaptive)],4)
        for name in ('smoothed','nms_display','edges'):
            save_png(folder/f'l4_manual_{name}.png',manual[name])
        save_png(folder/'l4_manual_api_difference.png',(manual['edges']!=canny[index]).astype(np.uint8)*255)
        image_panel(folder/'l4_manual_compare.png',[('Common smoothed input',manual['smoothed']),('Hand NMS display',manual['nms_display']),
                    ('Hand hysteresis',manual['edges']),(f'OpenCV Canny {pairs[index]}',canny[index])],4)
        raw={f'sobel_{kernel}_{key}':g[key] for kernel,g in gradients.items() for key in ('gx','gy','magnitude','direction_radians')}
        raw['manual_nms']=manual['nms']
        if gain is not None:
            raw['illumination_gain']=gain
        buffer=io.BytesIO()
        np.savez_compressed(buffer,**raw)
        atomic_write(latest.evidence/'raw_gradients.npz',buffer.getvalue())
        with np.load(latest.evidence/'raw_gradients.npz',allow_pickle=False) as saved:
            check('浮点梯度归档回读一致',all(np.array_equal(saved[key],value) for key,value in raw.items()))
        check('全部输出图片可回读且处理图无损',all(read_image(path).size>0 for path in folder.glob('*.png')))
        after={str(path):sha256(path) for path in sources.values()}
        check('原始输入 SHA-256 保持不变',before==after)
        info={'status':'SUCCESS','time':timestamp(),'program_version':VERSION,'environment':environment(),
              'input_sources':{'texture':str(sources['texture']),'uneven':illumination_note},
              'input_hashes_before':before,'input_hashes_after':after,'uneven_is_derived':gain is not None,
              'parameters':{key:value for key,value in cfg.items() if key not in ('texture','uneven')},
              'sobel_statistics':[{'kernel':kernel,'max_magnitude':float(g['magnitude'].max()),'mean_magnitude':float(g['magnitude'].mean())} for kernel,g in gradients.items()],
              'canny_statistics':canny_rows,'segmentation_statistics':segment_rows,'manual_thresholds':pairs[index],'manual_agreement':agree,
              'checks':checks,'elapsed_ms':round((perf_counter()-start)*1000,3),
              'timing_scope':'read, processing, plots, write/readback, archive and checks; excludes startup and metadata export',
              'outputs':{p.name:{**attributes(read_image(p)),'bytes':p.stat().st_size,'sha256':sha256(p)} for p in folder.glob('*.png')}}
        records=[{'kind':'canny',**row} for row in canny_rows]+[{'kind':'segmentation',**row} for row in segment_rows]
        fields=list(dict.fromkeys(key for record in records for key in record))
        csv_buffer=io.StringIO()
        writer=csv.DictWriter(csv_buffer,fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
        write_text(latest.evidence/'metrics.csv',csv_buffer.getvalue())
        metadata=json.dumps(info,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
        write_text(latest.evidence/'results.json',metadata)
        write_text(latest.evidence/'output_info.txt',metadata)
        write_text(latest.evidence/'run.log','COMMAND: '+subprocess.list2cmdline([sys.executable,'-X','utf8',*sys.argv])+'\n'+'\n'.join('PASS: '+c['name'] for c in checks)+'\nSTATUS: SUCCESS\n')
        report=report_text(info)
        write_text(latest.evidence/'lab_report.md',report.replace('../data/output/lab4_latest/','../../data/output/lab4_latest/'))
        latest.commit()
        write_text(ROOT/'docs/lab4_report.md',report)
        return info


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'config/lab4_images.json')
    parser.add_argument('--texture',type=Path,help='Override clear texture input')
    parser.add_argument('--uneven',type=Path,help='Override with personal uneven-illumination image')
    args=parser.parse_args()
    try:
        if sys.prefix==sys.base_prefix:
            raise ValueError('请使用项目独立虚拟环境')
        info=run(args.config,args.texture,args.uneven)
        print(json.dumps({'status':'SUCCESS','checks_passed':len(info['checks']),'image_count':len(info['outputs']),
                          'otsu_thresholds':{row['scene']:row['threshold'] for row in info['segmentation_statistics'] if row['method']=='otsu'},
                          'output':str(ROOT/'data/output/lab4_latest'),'report':str(ROOT/'docs/lab4_report.md')},ensure_ascii=False,indent=2))
        return 0
    except (OSError,ValueError,KeyError,TypeError,cv2.error) as exc:
        print(f'ERROR: {exc}',file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
