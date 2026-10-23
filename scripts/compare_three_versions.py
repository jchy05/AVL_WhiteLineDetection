"""Compare Marvin, the original AVL viewer, and the updated AVL ridge backend."""
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
sys.path.insert(0,str(ROOT/'src'))
from avl_white_lines.config import Config
from avl_white_lines.detector import Detector
from avl_white_lines.original_viewer import process

NAMES=('Marvin','Old AVL original','New AVL ridge')
MODES=('Article HSL white','Previous HSV','Saved HSL')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--marvin-repo',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--repeat',type=int,default=7);args=p.parse_args()
    if args.repeat<1: p.error('repeat must be positive')
    sys.path.insert(0,str(args.marvin_repo.resolve()))
    from white_line import WhiteLineDetector,PRESETS
    out=args.output;out.mkdir(parents=True,exist_ok=True)
    camera=PRESETS['marvin_front']
    cfg=Config(backend='marvin_ridge',camera=asdict(camera),processing_width=480,ground_live=False).validate()
    marvin=WhiteLineDetector(camera,proc_width=480,ground_live=False); avl=Detector(cfg)
    def run(index,image):
        if index==0: return marvin.detect(image)
        if index==1: return process(image,0,False)
        return avl.detect(image)
    times={kind:[[],[],[]] for kind in ('native_inputs','shared_480_inputs')}
    frames=[];sheets={m:[] for m in range(3)}
    for file in sorted((ROOT/'examples/raw').glob('*.jpg')):
        image=cv2.imread(str(file));H,W=image.shape[:2]
        small=cv2.resize(image,(480,round(H*480/W)),interpolation=cv2.INTER_AREA)
        results={}
        for kind,img in [('native_inputs',image),('shared_480_inputs',small)]:
            for i in range(3):run(i,img)
            for rep in range(args.repeat):
                for i in np.roll(np.arange(3),rep%3):
                    start=time.perf_counter();result=run(int(i),img)
                    times[kind][i].append((time.perf_counter()-start)*1000)
                    if kind=='native_inputs':results[int(i)]=result
        masks=[results[0],None,cv2.resize(results[2].mask,(W,H),interpolation=cv2.INTER_NEAREST)>0]
        overlays=[image.copy(),None,image.copy()]
        overlays[0][masks[0]]=(255,255,0);overlays[2][masks[2]]=(255,255,0)
        row=dict(frame=file.stem,input_size=[W,H],source_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
                 marvin_mask_pixels=int(masks[0].sum()),new_avl_mask_pixels=int(masks[2].sum()),new_avl_components=len(results[2].observations),old_modes=[])
        for mode in range(3):
            stages,final,stats=results[1] if mode==0 else process(image,mode,False)
            ref=ROOT/'examples/generated'/file.stem/('article_hsl_white','previous_hsv','saved_hsl')[mode]/'final.png'
            identical=bool(np.array_equal(final,cv2.imread(str(ref))))
            if not identical: raise RuntimeError(f'Original parity failed: {file.stem} mode {mode}')
            masks[1]=np.any(stages[15]>0,axis=2)|np.any(stages[16]>0,axis=2)
            overlays[1]=final
            row['old_modes'].append(dict(mode=MODES[mode],reference_pixel_identical=identical,**stats))
            for view in ('overlay','mask'):
                panels=[]
                for i,picture in enumerate([image]+overlays):
                    if view=='mask' and i: picture=cv2.cvtColor(masks[i-1].astype(np.uint8)*255,cv2.COLOR_GRAY2BGR)
                    shown=cv2.resize(picture,(480,round(H*480/W)),interpolation=cv2.INTER_AREA)
                    panel=np.full((shown.shape[0]+32,480,3),24,np.uint8);panel[32:]=shown
                    title=file.stem+' / RAW' if i==0 else NAMES[i-1]+(' / '+MODES[mode] if i==2 else '')
                    cv2.putText(panel,title,(8,22),cv2.FONT_HERSHEY_SIMPLEX,.47,(255,255,255),1,cv2.LINE_AA)
                    panels.append(panel)
                composite=np.hstack(panels)
                cv2.imwrite(str(out/f'{file.stem}_mode{mode}_{view}.jpg'),composite)
                if view=='overlay':sheets[mode].append(composite)
        frames.append(row)
    for mode,rows in sheets.items():cv2.imwrite(str(out/f'all_five_mode{mode}.jpg'),np.vstack(rows))
    summary={kind:{NAMES[i]:dict(mean_ms=float(np.mean(t)),p50_ms=float(np.median(t)),p95_ms=float(np.percentile(t,95)),samples=len(t)) for i,t in enumerate(values)} for kind,values in times.items()}
    report=dict(note='Primary views use original 1280x720 input, original AVL unchanged at native resolution, both ridge backends internally width 480. No depth or tracking, no live fitting, same unverified marvin_front calibration. Secondary timing sends identical 480px images to all three, changing original AVL pixel-scale behavior. Original process always constructs its 17 stages and overlay; workloads differ. No real ground truth or camera calibration: no accuracy ranking.',
        python=platform.python_version(),opencv=cv2.__version__,platform=platform.platform(),camera=asdict(camera),timing=summary,frames=frames,
        original_viewer_sha256=hashlib.sha256((ROOT/'src/avl_white_lines/original_viewer.py').read_bytes()).hexdigest())
    (out/'comparison.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    stems=json.dumps([f['frame'] for f in frames])
    html="""<!doctype html><meta charset="utf-8"><title>Marvin / Old AVL / New AVL</title>
<style>body{background:#15191f;color:#eee;font:16px system-ui;margin:24px}button,select{font:inherit;padding:8px;background:#283444;color:#fff;border:1px solid #8292a6;border-radius:5px}img{width:100%;margin-top:12px}p{max-width:1100px;line-height:1.5}a{color:#9cd5ff}</style>
<h1>Marvin / Old AVL / New AVL</h1>
<p>Columns: raw, standalone Marvin, original AVL program, new AVL ridge. Old AVL runs at its original native resolution and reproduces the saved references. Both ridge backends process at width 480. Same unverified camera preset; no depth. These are single-frame outputs before track confirmation, not an accuracy ranking.</p>
<p>Old AVL retains its group colors and ROI outline. Cyan in Marvin/new AVL marks segmentation. The mask view shows old AVL's accepted/fitted drawings rather than semantic paint segmentation.</p>
<button onclick="move(-1)">A: previous image</button> <button onclick="move(1)">D: next image</button>
<button onclick="toggle()">I / O: overlay or mask</button> <button onclick="mode=(mode+1)%3;paint()">M: old AVL filter</button>
<p id="label"></p><img id="result"><p><a href="comparison.json">Measurements/configuration</a></p>
<script>
const frames=STEMS,modes=['Article HSL white','Previous HSV','Saved HSL'];let index=0,mode=0,view='overlay';
function paint(){document.getElementById('result').src=frames[index]+'_mode'+mode+'_'+view+'.jpg';document.getElementById('label').textContent=frames[index]+' | '+modes[mode]+' | '+view;}
function move(d){index=(index+d+frames.length)%frames.length;paint();}function toggle(){view=view==='overlay'?'mask':'overlay';paint();}
document.addEventListener('keydown',e=>{if(e.target.tagName==='SELECT')return;const k=e.key.toLowerCase();if(['a','d','arrowleft','arrowright','i','o','m'].includes(k))e.preventDefault();if(k==='a'||k==='arrowleft')move(-1);if(k==='d'||k==='arrowright')move(1);if(k==='i'||k==='o')toggle();if(k==='m'){mode=(mode+1)%3;paint();}});paint();
</script>"""
    (out/'index.html').write_text(html.replace('STEMS',stems),encoding='utf-8')
    print(json.dumps(summary,indent=2)); print('Original references: all 15 pixel-identical')
if __name__=='__main__':main()
