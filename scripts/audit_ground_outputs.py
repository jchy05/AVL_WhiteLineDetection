"""Sparse recording audit + sequential runtime smoke; not a labeled accuracy benchmark."""
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
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from avl_white_lines.config import load_config
from avl_white_lines.detector import Detector
from avl_white_lines.tracking import Tracker
from avl_white_lines.navigation import navigation_output,inspection_overlay

CHECKPOINTS={'000000':[.22,.74],'000410':[.88,.79],'000474':[.70,.78],'000710':[.80,.85],'001077':[.73,.85]}


def panel(image,title):
    if image.ndim==2:image=cv2.cvtColor(image,cv2.COLOR_GRAY2BGR)
    image=cv2.resize(image,(480,round(image.shape[0]*480/image.shape[1])))
    output=np.full((image.shape[0]+32,480,3),24,np.uint8);output[32:]=image
    cv2.putText(output,title,(8,22),cv2.FONT_HERSHEY_SIMPLEX,.46,(255,255,255),1,cv2.LINE_AA)
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--sequence',type=Path);p.add_argument('--sequence-frames',type=int,default=120)
    p.add_argument('--repeat',type=int,default=5);args=p.parse_args()
    if args.repeat<1 or args.sequence_frames<1:p.error('Counts must be positive')
    out=args.output;out.mkdir(parents=True,exist_ok=True)
    full=load_config(ROOT/'config/marvin_ridge.json');review=load_config(ROOT/'config/recording_review.json')
    detectors=[Detector(full),Detector(review)];timings=[[],[]];rows=[];pictures=[]
    for stem,anchor in CHECKPOINTS.items():
        path=ROOT/'examples/raw'/('frame_'+stem+'.jpg');frame=cv2.imread(str(path));results={}
        for detector in detectors:detector.detect(frame)
        for rep in range(args.repeat):
            for i in np.roll(np.arange(2),rep%2):
                start=time.perf_counter();results[int(i)]=detectors[i].detect(frame)
                timings[i].append((time.perf_counter()-start)*1000)
        a,b=results[0],results[1];h,w=b.mask.shape
        # The upper 15%-45% band is a sparse visual background audit region.
        # The paint anchor is only a local checkpoint, not full lane ground truth.
        band=slice(round(.15*h),round(.45*h))
        distance=cv2.distanceTransform((b.mask==0).astype(np.uint8),cv2.DIST_L2,cv2.DIST_MASK_PRECISE)
        x,y=np.rint(np.array(anchor)*[w-1,h-1]).astype(int)
        nav=navigation_output(b,Tracker(review).update(b.observations,1),review)
        row=dict(frame=path.name,image_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            full_candidate_pixels=int(np.count_nonzero(a.mask)),review_candidate_pixels=int(np.count_nonzero(b.mask)),
            background_band_before=int(np.count_nonzero(a.mask[band])),background_band_after=int(np.count_nonzero(b.mask[band])),
            paint_checkpoint=anchor,checkpoint_distance_px=float(distance[y,x]),navigation_eligible=bool(nav.tracks),navigation_reasons=nav.reasons)
        rows.append(row)
        before=a.original.copy();before[a.mask>0]=(255,255,0)
        after=b.original.copy();after[b.mask>0]=(255,255,0)
        sheet=np.hstack([panel(b.original,'Raw / '+stem),panel(before,'Full-frame ridge candidates'),panel(after,'Recording crop / candidates'),panel(inspection_overlay(b,nav),'Navigation / blocked without inputs')])
        cv2.imwrite(str(out/('frame_'+stem+'.jpg')),sheet);pictures.append(sheet)
    cv2.imwrite(str(out/'five_frames.jpg'),np.vstack(pictures))
    sequence=dict(available=False,note='No reviewed moving-sequence labels; distinct IDs are not identity-switch accuracy.')
    if args.sequence and args.sequence.is_dir():
        files=sorted(args.sequence.glob('*.jpg'))[:args.sequence_frames]
        detector=Detector(review);tracker=Tracker(review);latencies=[];ids=set();navigation_frames=0;counts=[];previews=[]
        for idx,path in enumerate(files):
            frame=cv2.imread(str(path))
            if frame is None:raise ValueError('Unreadable sequence frame '+path.name)
            start=time.perf_counter();result=detector.detect(frame);tracks=tracker.update(result.observations,idx/30)
            nav=navigation_output(result,tracks,review);latencies.append((time.perf_counter()-start)*1000)
            ids.update(t['id'] for t in tracks);navigation_frames+=bool(nav.tracks)
            counts.append(sum(t['valid'] for t in tracks))
            if idx in {0,len(files)//4,len(files)//2,3*len(files)//4,len(files)-1}:
                picture=result.original.copy();picture[result.mask>0]=(255,255,0)
                previews.append(np.hstack([panel(result.original,path.name+' raw'),panel(picture,'Recording profile candidates')]))
        if previews:cv2.imwrite(str(out/'sequential_preview.jpg'),np.vstack(previews))
        sequence.update(available=bool(files),frames=len(files),first=files[0].name if files else None,last=files[-1].name if files else None,
            mean_pipeline_ms=float(np.mean(latencies)),p95_pipeline_ms=float(np.percentile(latencies,95)),distinct_track_ids=len(ids),
            frames_with_confirmed_candidates=sum(n>0 for n in counts),navigation_eligible_frames=navigation_frames,
            replay_clock_fps=30,clock_note='Nominal 30Hz replay clock, not measured acquisition timestamps.')
    report=dict(note='Recording-specific crop excludes the upper 55% and can remove far paint. Background-band counts and five sparse near-paint checkpoints are not full-frame precision/recall. Navigation blocked by default unverified model and absent registered depth.',
        platform=platform.platform(),opencv=cv2.__version__,profiles=dict(full=asdict(full),recording_review=asdict(review)),frames=rows,
        timing={name:dict(mean_ms=float(np.mean(t)),p95_ms=float(np.percentile(t,95)),samples=len(t)) for name,t in zip(('full','recording_review'),timings)},
        sequential_smoke=sequence,source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src/avl_white_lines').glob('*.py')})
    (out/'audit.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    html='<!doctype html><meta charset="utf-8"><title>AVL road-region and navigation audit</title><style>body{background:#15191f;color:#eee;font:16px system-ui;margin:24px}img{width:100%;margin:12px 0}a{color:#9cd5ff}</style><h1>Road-region and navigation audit</h1><p>Raw / full-frame ridge / recording crop / gated navigation. The crop is an inspection profile for this recording, not proof of ground. Navigation remains blocked without verified calibration and matching depth.</p><img src="five_frames.jpg">'
    if sequence['available']:html+='<h2>Sequential playback inspection</h2><p>Candidate masks only; no reviewed labels or navigation authorization.</p><img src="sequential_preview.jpg">'
    html+='<p><a href="audit.json">Measurements and settings</a></p>'
    (out/'index.html').write_text(html,encoding='utf-8')
    print(json.dumps(dict(timing=report['timing'],frames=rows,sequential_smoke=sequence),indent=2))
if __name__=='__main__':main()
