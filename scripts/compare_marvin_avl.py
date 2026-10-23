"""Compare upstream Marvin and AVL on identical 480px frames, no tuning."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from avl_white_lines.config import Config
from avl_white_lines.detector import Detector,draw_line
from test_physical_integration import scene
from test_ridge import render,ground_depth,CAM

NAMES=('Marvin standalone','AVL ridge','AVL legacy Hough')


def measure_mask(mask,gt):
    tp=int(np.count_nonzero(mask & gt)); fp=int(np.count_nonzero(mask & ~gt)); fn=int(np.count_nonzero(~mask & gt))
    return dict(tp=tp,fp=fp,fn=fn,precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--marvin-repo',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--repeat',type=int,default=7)
    args=p.parse_args()
    if args.repeat<1: p.error('repeat must be positive')
    sys.path.insert(0,str(args.marvin_repo.resolve()))
    from white_line import WhiteLineDetector,CameraModel,PRESETS
    args.output.mkdir(parents=True,exist_ok=True)
    groups={}
    raw=[]
    for path in sorted((ROOT/'examples/raw').glob('*.jpg')):
        original=cv2.imread(str(path)); H,W=original.shape[:2]
        image=cv2.resize(original,(480,round(H*480/W)),interpolation=cv2.INTER_AREA)
        raw.append((path.stem,image,None,None))
    groups['real_unlabeled']=(raw,PRESETS['marvin_front'])
    synth=[]
    for name,kw in [('tape',dict(tape=True)),('shadow',dict(tape=False,shadow=True))]:
        image,gt=render(**kw); synth.append((name,image,gt,None))
    for name,width in [('curve',.076),('crack',.03),('joint',.03),('narrow',.01),('oversize',.7)]:
        image,gt=scene(name if name not in ('narrow','oversize') else 'straight',width)
        if name in ('narrow','oversize'): gt[:]=False
        synth.append((name,image,gt,None))
    groups['synthetic']=(synth,CameraModel(**asdict(CAM)))
    image,gt=render(); depth=ground_depth()
    raised=depth.copy(); raised[cv2.dilate(gt.astype(np.uint8),np.ones((9,9),np.uint8))>0]*=.7
    farther=depth*1.5
    groups['synthetic_depth']=([('on_ground',image,gt,depth),('raised_white_object',image,np.zeros_like(gt),raised),('behind_ground_plane',image,np.zeros_like(gt),farther)],CameraModel(**asdict(CAM)))
    report=dict(note='Identical externally resized 480px BGR input, same calibration, no live fitting, no tuning. Real preset assumed, not verified; real accuracy unknown. Legacy is an Article HSL fitted-line raster, not a semantic paint mask. Detection timing excludes resizing, rendering, tracking, capture and ROS. Algorithm order rotates every repeat.',
                python=platform.python_version(),opencv=cv2.__version__,platform=platform.platform(),groups={})
    for group,(frames,camera) in groups.items():
        upstream=WhiteLineDetector(camera,proc_width=480,ground_live=False)
        cfg=Config(backend='marvin_ridge',camera=asdict(camera),processing_width=480,ground_live=False).validate()
        avl=Detector(cfg)
        oldcfg=Config(backend='legacy_hough',processing_width=480)
        legacy=Detector(oldcfg)
        def run(index,img,depth):
            if index==0: return upstream.detect(img,depth)
            return (avl if index==1 else legacy).detect(img,depth=depth)
        times=[[],[],[]]; rows=[]; pictures=[]
        for name,img,gt,depth in frames:
            for i in range(3): run(i,img,depth)
            results={}
            for rep in range(args.repeat):
                for i in np.roll(np.arange(3),rep%3):
                    start=time.perf_counter(); result=run(int(i),img,depth)
                    times[i].append((time.perf_counter()-start)*1000);results[int(i)]=result
            masks=[results[0]]
            masks.append(results[1].mask>0)
            raster=np.zeros_like(img)
            for o in results[2].observations: draw_line(raster,o,(255,255,255))
            masks.append(np.any(raster>0,axis=2))
            data=dict(name=name,mask_pixels={NAMES[i]:int(m.sum()) for i,m in enumerate(masks)},
                      avl_components=len(results[1].observations),legacy_lines=len(results[2].observations),
                      avl_retained_marvin_pixels=int(np.count_nonzero(masks[0]&masks[1])),
                      avl_removed_marvin_pixels=int(np.count_nonzero(masks[0]&~masks[1])),
                      avl_added_pixels=int(np.count_nonzero(~masks[0]&masks[1])))
            if gt is not None: data['pixel_metrics']={NAMES[i]:measure_mask(mask,gt) for i,mask in enumerate(masks)}
            rows.append(data)
            row=[]
            for i in range(4):
                picture=img.copy()
                title=name+' / Original' if i==0 else NAMES[i-1]+f' / {masks[i-1].sum()} px'
                if i: picture[masks[i-1]]=(255,255,0)
                panel=np.full((img.shape[0]+32,480,3),24,np.uint8);panel[32:]=picture
                cv2.putText(panel,title,(8,22),cv2.FONT_HERSHEY_SIMPLEX,.47,(255,255,255),1,cv2.LINE_AA)
                row.append(panel)
            sheet=np.hstack(row);pictures.append(sheet)
            cv2.imwrite(str(args.output/(group+'_'+name+'.jpg')),sheet)
            for i,mask in enumerate(masks): cv2.imwrite(str(args.output/(group+'_'+name+f'_mask_{i}.png')),mask.astype(np.uint8)*255)
        cv2.imwrite(str(args.output/(group+'_comparison.jpg')),np.vstack(pictures))
        summary={NAMES[i]:dict(mean_ms=float(np.mean(values)),p50_ms=float(np.median(values)),p95_ms=float(np.percentile(values,95)),samples=len(values)) for i,values in enumerate(times)}
        report['groups'][group]=dict(camera=asdict(camera),timing=summary,frames=rows)
        print(group, {k:round(v['mean_ms'],1) for k,v in summary.items()})
    report['avl_source_sha256']={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (ROOT/'src/avl_white_lines').glob('*.py')}
    report['marvin_source_sha256']={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (args.marvin_repo/'white_line').glob('*.py')}
    (args.output/'comparison.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    html='<!doctype html><meta charset="utf-8"><title>Marvin vs AVL</title><style>body{background:#16191f;color:#eee;font:16px system-ui;margin:24px}img{width:100%;margin:12px 0}a{color:#90c8ff}</style><h1>Marvin vs AVL</h1><p>Left to right: original, upstream Marvin, AVL ridge, AVL legacy Hough. Cyan shows current-frame evidence, before tracking confirmation. Same 480px input and camera model. The five real frames have no verified calibration or labels; removed pixels are not automatically errors.</p>'
    for group in groups: html+=f'<h2>{group}</h2><img src="{group}_comparison.jpg">'
    html+='<p><a href="comparison.json">Raw measurements and configuration</a></p>'
    (args.output/'index.html').write_text(html,encoding='utf-8')
if __name__=='__main__': main()
