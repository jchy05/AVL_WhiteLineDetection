"""Reproducible CPU comparison. Synthetic labels are not real-world accuracy."""
import argparse
import hashlib
from dataclasses import asdict
import json
from pathlib import Path
import platform
import sys
import time
import tracemalloc
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from test_physical_integration import scene,config
from test_ridge import render,CAM
from avl_white_lines.detector import Detector
from avl_white_lines.tracking import Tracker


def counts(pred,gt):
    tp=int(np.count_nonzero(pred&gt)); fp=int(np.count_nonzero(pred&~gt)); fn=int(np.count_nonzero(~pred&gt))
    return dict(tp=tp,fp=fp,fn=fn,precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None)


def evaluate(cfg,frames,repeat):
    detector=Detector(cfg); times=[]; rows=[]
    for name,image,gt in frames:
        detector.detect(image)  # warm-up outside timer
        for _ in range(repeat):
            start=time.perf_counter(); result=detector.detect(image); times.append((time.perf_counter()-start)*1000)
        if gt is not None:
            pred=result.mask>0 if result.mask is not None else np.zeros(gt.shape,bool)
            if result.mask is None:
                # Rasterize legacy fitted centerlines for an explicitly named
                # comparison; Hough has no segmentation mask.
                from avl_white_lines.detector import draw_line
                pic=np.zeros_like(result.original)
                for o in result.observations: draw_line(pic,o,(255,255,255))
                pred=np.any(pic>0,axis=2)
            if pred.shape!=gt.shape: pred=cv2.resize(pred.astype(np.uint8),(gt.shape[1],gt.shape[0]),interpolation=cv2.INTER_NEAREST)>0
            matched=0; false=0; errors=[]; angles=[]
            expected=None
            if name in ('tape','curve'):
                X=np.linspace(2,7,500); Y=.6+.1*(X-4)**2 if name=='curve' else np.full_like(X,.6)
                t=np.radians(CAM.pitch_deg)
                optical=np.column_stack([-Y,-np.sin(t)*X+np.cos(t)*CAM.height_m,np.cos(t)*X+np.sin(t)*CAM.height_m])
                uv=optical@CAM.K_for(image.shape[1],image.shape[0]).T
                expected=uv[:,:2]/uv[:,2:]
            fit_errors=[]
            for o in result.observations:
                if gt.any():
                    ys,xs=np.nonzero(gt)
                    points=np.array(o.centerline_image)*[image.shape[1]-1,image.shape[0]-1] if o.centerline_image else np.column_stack([o.x(np.linspace(o.y_min,o.y_max,32))*(image.shape[1]-1),np.linspace(o.y_min,o.y_max,32)*(image.shape[0]-1)])
                    if expected is None:
                        false+=1; continue
                    distances=np.linalg.norm(points[:,None,:]-expected[None,:,:],axis=2)
                    nearest=distances.argmin(axis=1)
                    error=float(np.mean(distances.min(axis=1)))
                    # Span a few samples to avoid differentiating per-pixel bin jitter.
                    step=max(1,len(points)//8)
                    dp=points[step:]-points[:-step]
                    dg=expected[nearest[step:]]-expected[nearest[:-step]]
                    good=(np.linalg.norm(dp,axis=1)>1e-6)&(np.linalg.norm(dg,axis=1)>1e-6)
                    delta=np.arctan2(dp[good,1],dp[good,0])-np.arctan2(dg[good,1],dg[good,0])
                    angle=float(np.degrees(np.mean(np.abs((delta+np.pi/2)%np.pi-np.pi/2)))) if good.any() else 90.
                    errors.append(error); angles.append(angle)
                    coverage=float(np.ptp(nearest)/max(1,len(expected)-1))
                    if error<10 and angle<2 and coverage>=.6 and matched==0: matched+=1
                    else: false+=1
                else: false+=1
            rows.append(dict(scene=name,pixels=counts(pred,gt),components_predicted=len(result.observations),
                components_expected=int(gt.any()),components_matched=matched,false_components=false,false_positives_per_frame=false,
                component_precision=matched/len(result.observations) if result.observations else None,
                component_recall=matched if gt.any() else None,centerline_error_px=errors,mean_local_heading_error_deg=angles,
                component_match_rule='one synthetic marking; mean centerline error <10 px AND mean local angle error <2 degrees; at least 60% GT centerline coverage'))
        else: rows.append(dict(scene=name,components_predicted=len(result.observations),accuracy=None))
    tracemalloc.start()
    detector.detect(frames[0][1])
    _,peak=tracemalloc.get_traced_memory(); tracemalloc.stop()
    # Three independent camera instances processed serially, same images.
    detectors=[Detector(cfg) for _ in range(3)]
    begin=time.perf_counter()
    for detector in detectors:
        for _,image,_ in frames: detector.detect(image)
    elapsed=time.perf_counter()-begin
    image=frames[0][1]; tracker=Tracker(cfg); ids=[]
    detector=Detector(cfg)
    for i in range(12):
        tracks=tracker.update(detector.detect(image).observations,i/30)
        ids.append([t['id'] for t in tracks if t['valid']])
    return dict(config=asdict(cfg),mean_ms=float(np.mean(times)),p50_ms=float(np.percentile(times,50)),p95_ms=float(np.percentile(times,95)),
        python_traced_peak_bytes=peak,serial_three_camera_total_fps=3*len(frames)/elapsed,
        stationary_sequence_confirmed_ids=ids,scenes=rows)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,default=ROOT/'results/backend_benchmark.json'); parser.add_argument('--repeat',type=int,default=3);args=parser.parse_args()
    if args.repeat<1: parser.error('repeat must be positive')
    frames=[]
    for name,kwargs in [('tape',dict(tape=True)),('shadow',dict(tape=False,shadow=True))]:
        image,gt=render(**kwargs);frames.append((name,image,gt))
    for name,width in [('curve',.076),('crack',.03),('joint',.03),('narrow',.01),('oversize',.7)]:
        image,gt=scene(name if name not in ('narrow','oversize') else 'straight',width)
        if name in ('narrow','oversize'): gt[:]=False
        frames.append((name,image,gt))
    results={}
    for backend in ('legacy_hough','marvin_ridge','hybrid_fallback'):
        cfg=config(); cfg.backend=backend
        results[backend]=evaluate(cfg,frames,args.repeat)
    raw=[(file.name,cv2.imread(str(file)),None) for file in sorted((ROOT/'examples/raw').glob('*.jpg'))]
    smoke={}
    for backend in results:
        cfg=config(); cfg.backend=backend
        smoke[backend]=evaluate(cfg,raw,args.repeat)
    report=dict(source_sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((ROOT/'src/avl_white_lines').glob('*.py'))},raw_sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((ROOT/'examples/raw').glob('*.jpg'))},platform=platform.platform(),python=platform.python_version(),opencv=cv2.__version__,numpy=np.__version__,
        note='Local CPU only. Shared 480 px width. Memory is a separate tracemalloc pass and excludes some native allocations. Timings do not include tracemalloc, capture, ROS or rendering. Synthetic metrics are construction-label checks, not real accuracy. Real camera preset is ASSUMED, not calibrated. Three-camera test is serial duplicate streams, not robot throughput. No moving labeled sequence or ID-switch ground truth.',
        synthetic=results,unlabeled_real_smoke=smoke)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    for key,value in results.items(): print(key,round(value['mean_ms'],1),'ms',round(value['serial_three_camera_total_fps'],1),'serial aggregate FPS')
if __name__=='__main__': main()
