"""Lab-seven image IO and a local, offline human-annotation page."""
from __future__ import annotations
import csv
import io
import json
from pathlib import Path
import cv2
import numpy as np
from baseline_pipeline import read_image
from common import ROOT,atomic_write,sha256,write_text
from lab7_annotations import FIELDS


def source_path(value):
    path=Path(value)
    path=(path if path.is_absolute() else ROOT/path).resolve()
    if any(path.is_relative_to((ROOT/folder).resolve()) for folder in ('data/output','evidence','docs')):
        raise ValueError('图片/持久标签不能位于输出、证据或文档目录，请保存在data/input或data/annotations')
    return path


def load_photo(value,max_side=1600):
    path=source_path(value)
    digest=sha256(path)
    image=read_image(path)
    shape=list(image.shape)
    if image.dtype!=np.uint8 or min(image.shape[:2])<16:
        raise ValueError('实验七照片要求uint8且宽高至少16')
    if image.ndim==2:
        image=cv2.cvtColor(image,cv2.COLOR_GRAY2BGR)
    elif image.shape[2]==4:
        image=image[:,:,:3].copy()
    h,w=image.shape[:2]
    scale=min(1.0,max_side/max(h,w)) if max_side else 1.0
    if scale<1:
        width,height=round(w*scale),round(h*scale)
        if min(width,height)<16:
            raise ValueError('等比缩放后最短边不足16，请提高max_input_side或设0')
        image=cv2.resize(image,(width,height),interpolation=cv2.INTER_AREA)
    sx,sy=image.shape[1]/w,image.shape[0]/h
    return image,{'path':str(path),'sha256':digest,'original_shape':shape,'working_shape':list(image.shape),
                  'source_to_work_pixel_centers':[[sx,0,(sx-1)/2],[0,sy,(sy-1)/2]],'resize':'INTER_AREA' if scale<1 else 'none'}


def save_png(path,image):
    ok,encoded=cv2.imencode('.png',image)
    if not ok:
        raise OSError(f'PNG编码失败: {path}')
    atomic_write(path,encoded.tobytes())
    if not np.array_equal(read_image(path),image):
        raise OSError(f'PNG回读不一致: {path}')


def write_csv(path,fields,rows):
    buffer=io.StringIO(newline='')
    writer=csv.DictWriter(buffer,fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    write_text(path,buffer.getvalue())


def crop_pair(image1,image2,record,size=160,radius=64):
    patches=[]
    for image,key in ((image1,'xy1'),(image2,'xy2')):
        x,y=record[key]
        patch=cv2.getRectSubPix(image,(2*radius,2*radius),(float(x),float(y)))
        patch=cv2.resize(patch,(size,size),interpolation=cv2.INTER_LINEAR)
        cv2.drawMarker(patch,(size//2,size//2),(255,0,255),cv2.MARKER_CROSS,15,1)
        patches.append(patch)
    return np.hstack(patches)


def annotation_artifacts(folder,evidence,manifest,image1,image2,labels):
    records=manifest['pairs']
    template=[]
    for record in records:
        prior=labels.get(record['pair_id'],{})
        template.append({'dataset_id':manifest['dataset_id'],'pair_id':record['pair_id'],
                         'query_index':record['query_index'],'train_index':record['train_index'],
                         'label':prior.get('label',''),'reviewer':prior.get('reviewer',''),'note':prior.get('note','')})
    write_csv(folder/'labels_template.csv',FIELDS,template)
    write_text(evidence/'annotation_manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False))
    by_id={row['pair_id']:row for row in records}
    # Ten evenly sized cards per page; pages include every sampled pair, not only best scores.
    for group in manifest['groups']:
        for offset in range(0,len(group['pair_ids']),10):
            ids=group['pair_ids'][offset:offset+10]
            sheet=np.full((5*200,2*340,3),245,np.uint8)
            for index,pid in enumerate(ids):
                x,y=(index%2)*340,(index//2)*200
                record=by_id[pid]
                patch=crop_pair(image1,image2,record)
                sheet[y+32:y+192,x+10:x+330]=patch
                label=labels.get(pid,{}).get('label','') or 'unlabeled'
                cv2.putText(sheet,f"{offset+index+1}: q{record['query_index']} t{record['train_index']} {label}",(x+5,y+21),cv2.FONT_HERSHEY_SIMPLEX,0.4,(30,30,30),1,cv2.LINE_AA)
            save_png(folder/f"sample_{group['threshold']:g}_{offset//10+1:02d}.png",sheet)
    payload={'dataset_id':manifest['dataset_id'],'groups':manifest['groups'],'pairs':records,'labels':template}
    # Escape '<' so even a future human note cannot terminate the JSON script element.
    encoded=json.dumps(payload,ensure_ascii=False,allow_nan=False).replace('<','\\u003c')
    write_text(folder/'annotate.html',HTML.replace('__DATA__',encoded))


HTML=r'''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><title>实验七 人工匹配标注</title>
<style>body{font:16px system-ui;margin:24px auto;max-width:1200px;padding:0 18px;background:#f4f6f8;color:#152334}button,input,select{font:inherit;padding:8px;margin:4px}button{cursor:pointer}canvas{width:46%;background:#ddd;border:1px solid #aaa}#info{white-space:pre-wrap;background:white;padding:14px}label{display:inline-block}textarea{width:95%;height:50px}h1{font-size:24px}.toolbar{background:white;padding:12px;margin:12px 0}</style>
<h1>实验七 人工匹配标注</h1><p>判断两个紫色十字是否对应同一实际场景点。紫色仅标位置，不表示误匹配。重复窗格、反射、移动人物需仔细判断，不确定时保留“不确定”，不要按连线或ratio自动判正确。</p>
<div class="toolbar"><label>阈值组 <select id="group"></select></label><label>样本 <select id="sample"></select></label><label>真实标注者 <input id="reviewer" placeholder="请填写"></label><button id="export">导出CSV</button><label>导入CSV <input type="file" id="import" accept=".csv"></label></div>
<p id="progress"></p><div id="info"></div><p><label>局部观察半径 <input type="range" id="radius" min="24" max="400" value="96"></label><label><input type="checkbox" id="full">全图定位</label> <a href="image1_work.png" target="_blank">打开图1</a> · <a href="image2_work.png" target="_blank">打开图2</a></p>
<canvas id="left" width="560" height="560"></canvas> <canvas id="right" width="560" height="560"></canvas>
<div class="toolbar"><button id="previous">上一对</button><button data-label="correct">正确 Y</button><button data-label="incorrect">错误 N</button><button data-label="uncertain">不确定 U</button><button data-label="">清空</button><button id="next">下一对</button><p>备注 <textarea id="note"></textarea></p></div>
<p>每个阈值随机抽取50对（不足50则全部），不同组共用的配对只需标一次。CSV下载后保存到项目 <code>data/annotations/</code>，再用 <code>run_lab7.py --labels 实际CSV路径</code> 计算误匹配率。当前页面修改不会自行写入项目文件。重跑前先导出备份；只在你明确告知后更新个人任务状态。</p>
<script id="payload" type="application/json">__DATA__</script><script>
const data=JSON.parse(document.getElementById('payload').textContent),$=id=>document.getElementById(id);
const pairs=new Map(data.pairs.map(p=>[p.pair_id,p])), labels=new Map(data.labels.map(p=>[p.pair_id,{...p}]));
const key='lab7-labels-'+data.dataset_id, pics=[new Image(),new Image()];
let group=0,index=0,storage=true;
try{const saved=JSON.parse(localStorage.getItem(key)||'null');if(saved)for(const row of saved)if(labels.has(row.pair_id)&&row.dataset_id===data.dataset_id)labels.set(row.pair_id,row)}catch(e){storage=false}
function persist(){try{localStorage.setItem(key,JSON.stringify([...labels.values()]))}catch(e){storage=false}}
function current(){return data.groups[group]?.pair_ids[index]}
function draw(canvas,img,xy){const c=canvas.getContext('2d');c.fillStyle='#ddd';c.fillRect(0,0,560,560);if(!img.complete||!img.naturalWidth)return;let x,y;
if($('full').checked){const scale=Math.min(560/img.naturalWidth,560/img.naturalHeight),w=img.naturalWidth*scale,h=img.naturalHeight*scale;c.drawImage(img,0,0,w,h);x=xy[0]*scale;y=xy[1]*scale}else{const r=Number($('radius').value);c.drawImage(img,xy[0]-r,xy[1]-r,2*r,2*r,0,0,560,560);x=y=280}
c.strokeStyle='#ff00ff';c.lineWidth=2;c.beginPath();c.moveTo(x-12,y);c.lineTo(x+12,y);c.moveTo(x,y-12);c.lineTo(x,y+12);c.stroke()}
function render(){const g=data.groups[group],pid=current(),p=pairs.get(pid),row=labels.get(pid);$('sample').replaceChildren(...(g?.pair_ids||[]).map((v,i)=>new Option(String(i+1),String(i))));$('sample').value=String(index);
if(!p){$('info').textContent='该组无匹配，无法进行人工抽样。';return}
const decisive=g.pair_ids.filter(id=>['correct','incorrect'].includes(labels.get(id).label)).length;
$('progress').textContent=`阈值 ${g.threshold}：已明确判断 ${decisive}/${g.pair_ids.length}，总体匹配 ${g.population_count}。`+(storage?' 页面会尝试保存本机浏览器进度。':' 浏览器未允许保存，请及时导出CSV。');
$('info').textContent=`${index+1}/${g.pair_ids.length} · ${pid}\n图1 (${p.xy1.map(v=>v.toFixed(2)).join(', ')}) → 图2 (${p.xy2.map(v=>v.toFixed(2)).join(', ')})\n当前标签：${row.label||'未标注'}；原始ratio=${p.ratio.toFixed(4)}（只是筛选指标）`;
$('note').value=row.note||'';if(row.reviewer&&!$('reviewer').value)$('reviewer').value=row.reviewer;draw($('left'),pics[0],p.xy1);draw($('right'),pics[1],p.xy2)}
function move(step){index=Math.max(0,Math.min((data.groups[group]?.pair_ids.length||1)-1,index+step));render()}
function label(value){const row=labels.get(current());if(!row)return;const name=$('reviewer').value.trim();if(value&&!name){alert('请先填写真实标注者');return}row.label=value;row.reviewer=value?name:'';row.note=$('note').value;persist();render();if(value)move(1)}
$('group').replaceChildren(...data.groups.map((g,i)=>new Option(String(g.threshold),String(i))));$('group').onchange=()=>{group=Number($('group').value);index=0;render()};$('sample').onchange=()=>{index=Number($('sample').value);render()};$('radius').oninput=render;$('full').onchange=render;
$('previous').onclick=()=>move(-1);$('next').onclick=()=>move(1);for(const button of document.querySelectorAll('[data-label]'))button.onclick=()=>label(button.dataset.label);
$('note').onchange=()=>{if(labels.has(current())){labels.get(current()).note=$('note').value;persist()}};
document.onkeydown=e=>{if(['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName))return;const k=e.key.toLowerCase();if(k==='y')label('correct');else if(k==='n')label('incorrect');else if(k==='u')label('uncertain');else if(k==='arrowright')move(1);else if(k==='arrowleft')move(-1)};
const fields=['dataset_id','pair_id','query_index','train_index','label','reviewer','note'];
function quote(value){return '"'+String(value??'').replaceAll('"','""')+'"'}
$('export').onclick=()=>{const csv='\ufeff'+[fields,...[...labels.values()].map(row=>fields.map(f=>row[f]))].map(row=>row.map(quote).join(',')).join('\r\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));a.download='lab7_labels_'+data.dataset_id.slice(0,16)+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)};
function parseCSV(text){text=text.replace(/^\uFEFF/,'');const rows=[];let row=[],cell='',quoted=false;for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){cell+='"';i++}else quoted=!quoted}else if(c===','&&!quoted){row.push(cell);cell=''}else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell);if(row.some(v=>v!==''))rows.push(row);row=[];cell=''}else cell+=c}if(quoted)throw Error('CSV引号未闭合');row.push(cell);if(row.some(v=>v!==''))rows.push(row);return rows}
$('import').onchange=async()=>{try{const rows=parseCSV(await $('import').files[0].text());if(JSON.stringify(rows[0])!==JSON.stringify(fields))throw Error('表头不匹配');const updates=new Map();for(const values of rows.slice(1)){if(values.length!==fields.length)throw Error('CSV列数不匹配');const row=Object.fromEntries(fields.map((f,i)=>[f,values[i]]));const known=labels.get(row.pair_id);if(row.dataset_id!==data.dataset_id)throw Error('图片/提取配置不匹配');if(!known)throw Error('当前样本不存在该配对');if(String(known.query_index)!==row.query_index||String(known.train_index)!==row.train_index)throw Error('配对索引不匹配');if(!['','correct','incorrect','uncertain'].includes(row.label))throw Error('无效标签');if(row.label&&!row.reviewer.trim())throw Error('请填写真实标注者');if(updates.has(row.pair_id))throw Error('配对重复');updates.set(row.pair_id,row)}for(const [id,row]of updates)labels.set(id,row);persist();render();alert('已导入，尚未自行写入项目文件')}catch(e){alert(e.message)}};
pics[0].src='image1_work.png';pics[1].src='image2_work.png';pics.forEach(img=>img.onload=render);render();
</script></html>'''
