import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import sys
import time
import cv2
import numpy as np
from .config import MODES,load_config,save_config
from .detector import STAGES,Detector,render
from .components import component_dict
from .tracking import Tracker
from .capture import LatestCapture
from .original_viewer import STAGES as ORIGINAL_STAGE_INFO

def panel(image,title,width=560):
    if image.ndim==2: image=cv2.cvtColor(image,cv2.COLOR_GRAY2BGR)
    h=round(image.shape[0]*width/image.shape[1])
    out=np.zeros((h+32,width,3),np.uint8)
    out[32:]=cv2.resize(image,(width,h))
    cv2.putText(out,title,(8,22),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1,cv2.LINE_AA)
    return out

def compose(result,tracks,stage,cfg,source=''):
    final=render(result,tracks)
    stages=tuple(result.stages); stage=stage%len(stages)
    inspected=result.stages[stages[stage]]
    if stages[stage]=='Tracked components': inspected=render(result,tracks)
    top=np.hstack([panel(result.original,'Original / '+source),panel(inspected,f'{stage+1}/{len(stages)} {stages[stage]}'),panel(final,'Tracked / '+result.backend)])
    footer=np.zeros((100,top.shape[1],3),np.uint8)
    description=dict(ORIGINAL_STAGE_INFO).get(stages[stage],stages[stage]+' / '+result.backend)
    if stages[stage]=='Active color mask': description=f'Current mask: {cfg.mode}. M changes the mask used by following stages.'
    if stages[stage]=='Accepted segments': description='Experimental geometric consensus: independent hypotheses, then temporal association; differs from original grouping.'
    texts=["I/O: stage | M: mask | R: ROI | A/D or arrows: image | Space: play/pause | T: reset tracks | S: snapshot | Q/Esc: quit",
           description,
           f"{result.processing_ms:.1f} ms detection | tracks {len(tracks)} | valid {sum(t['valid'] for t in tracks)} | gray dashed = held, invalid"]
    for i,text in enumerate(texts): cv2.putText(footer,text,(8,25+i*28),cv2.FONT_HERSHEY_SIMPLEX,.5,(230,230,230),1)
    return np.vstack([top,footer])

def main(argv=None):
    p=argparse.ArgumentParser(description="AVL white-line detection: camera, video, image sequence, or ROS adapter via avl-lines-ros")
    inputs=p.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--images',type=Path); inputs.add_argument('--video',type=Path)
    inputs.add_argument('--camera',help="Camera index, /dev/videoN, or stream URL. ZED X uses the ROS adapter.")
    p.add_argument('--backend',choices=('marvin_ridge','legacy_hough','hybrid_fallback'))
    p.add_argument('--camera-model',help='Camera JSON file or explicit Marvin preset name')
    p.add_argument('--depth-dir',type=Path,help='Aligned float metre .npy files matching image stems')
    p.add_argument('--config',type=Path); p.add_argument('--mode',choices=MODES)
    p.add_argument('--headless',action='store_true'); p.add_argument('--play',action='store_true')
    p.add_argument('--fps',type=float,default=30,help='Image-sequence replay rate, not measured camera FPS')
    p.add_argument('--frames',type=int,default=0,help='Limit processed frames; 0 means all')
    p.add_argument('--export-dir',type=Path,help='Save every debug stage, mask and overlay without a display')
    p.add_argument('--jsonl',type=Path,help='Per-frame structured output (can grow large)')
    p.add_argument('--benchmark',type=Path,help='Save local timing summary; not a robot-speed claim')
    p.add_argument('--save-config',type=Path,help='Write effective settings at startup')
    args=p.parse_args(argv)
    if not math.isfinite(args.fps) or args.fps<=0 or args.frames<0: p.error('fps must be finite and positive and frames must be nonnegative')
    cfg=load_config(args.config)
    if args.mode: cfg.mode=args.mode
    if args.backend: cfg.backend=args.backend
    if args.camera_model:
        model=Path(args.camera_model)
        cfg.camera=json.loads(model.read_text()) if model.is_file() else args.camera_model
    cfg.validate()
    if args.depth_dir and not args.images: p.error('--depth-dir requires --images')
    if args.save_config: save_config(cfg,args.save_config)
    detector=Detector(cfg)
    tracker=Tracker(cfg); source=None; cap=None
    files=[]
    if args.images:
        files=sorted(x for x in args.images.rglob('*') if x.suffix.lower() in {'.jpg','.jpeg','.png','.bmp','.tif','.tiff','.webp'})
        if not files: p.error('No images found')
    elif args.video:
        cap=cv2.VideoCapture(str(args.video))
        if not cap.isOpened(): p.error(f'Cannot open video: {args.video}')
        rate=cap.get(cv2.CAP_PROP_FPS)
        if rate>0: args.fps=rate
    else:
        camera=int(args.camera) if args.camera.isdigit() else args.camera
        source=LatestCapture(camera)
    log=None
    if args.jsonl:
        args.jsonl.parent.mkdir(parents=True,exist_ok=True); log=args.jsonl.open('w',encoding='utf-8')
    stage=8; idx=0; processed=0; sequence=0; dropped=0; times=[]; wall_start=time.perf_counter()
    playing=args.play or args.headless or not files
    dirty=True; current=None; tracks=[]; result=None; frame_source=''; timestamp=0; painted=None
    if not args.headless:
        cv2.namedWindow('AVL WhiteLineDetection',cv2.WINDOW_NORMAL)
        cv2.resizeWindow('AVL WhiteLineDetection',1500,520)
    try:
        while True:
            loop_start=time.perf_counter()
            if dirty:
                if files:
                    current=cv2.imread(str(files[idx])); timestamp=idx/args.fps; frame_source=files[idx].name
                elif cap:
                    ok,current=cap.read()
                    if not ok: break
                    timestamp=idx/args.fps; frame_source=str(args.video.name)
                else:
                    packet=source.get(sequence)
                    if packet is None:
                        tracker.reset()
                        if log:
                            log.write(json.dumps({'schema_version':1,'status':'stale','tracks':[],'detected':False})+'\n'); log.flush()
                        if source.failed: raise RuntimeError('Camera stopped delivering frames')
                        if not args.headless:
                            stale=np.zeros((360,960,3),np.uint8)
                            cv2.putText(stale,'NO FRESH FRAME - detections invalid',(25,180),cv2.FONT_HERSHEY_SIMPLEX,.8,(0,0,255),2)
                            cv2.imshow('AVL WhiteLineDetection',stale)
                            if cv2.waitKey(1) in (27,ord('q')): break
                        continue
                    new_seq,timestamp,current=packet
                    dropped+=max(0,new_seq-sequence-1); sequence=new_seq
                    frame_source=f'camera:{sequence}'
                    if time.monotonic()-timestamp>cfg.max_frame_age_seconds: tracker.reset(); continue
                if current is None: raise RuntimeError(f'Unreadable frame: {frame_source}')
                started=time.perf_counter()
                depth=None
                if args.depth_dir:
                    path=args.depth_dir/(files[idx].stem+'.npy')
                    if path.exists(): depth=np.load(path,allow_pickle=False)
                result=detector.detect(current,debug=not args.headless or args.export_dir is not None,depth=depth)
                stages=tuple(result.stages) if result.stages else STAGES
                stage%=len(stages)
                tracks=tracker.update(result.observations,timestamp)
                if 'Tracked components' in result.stages: result.stages['Tracked components']=render(result,tracks)
                deadline_missed=bool(source and time.monotonic()-timestamp>cfg.max_frame_age_seconds)
                if deadline_missed:
                    tracker.reset(); tracks=[]
                times.append((time.perf_counter()-started)*1000)
                processed+=1
                payload={'schema_version':1,'source':frame_source,'timestamp_seconds':timestamp,
                         'image_size':[current.shape[1],current.shape[0]],'mode':cfg.mode,
                         'status':'processing_deadline_missed' if deadline_missed else 'ok','detected':any(t['valid'] for t in tracks),'tracks':tracks,
                         'processing_image_size':[result.original.shape[1],result.original.shape[0]],
                         'backend':result.backend,'ground_estimate':result.ground_estimate,
                         'components':[component_dict(o,i+1) for i,o in enumerate(result.observations)],
                         'processing_ms':times[-1],'dropped_capture_frames':dropped}
                if args.export_dir:
                    out=args.export_dir/Path(frame_source).stem; out.mkdir(parents=True,exist_ok=True)
                    for name,picture in result.stages.items():
                        if name=='Tracked components': picture=render(result,tracks)
                        cv2.imwrite(str(out/(name.lower().replace('/','_').replace(' ','_')+'.png')),picture)
                    cv2.imwrite(str(out/'tracked_overlay.png'),render(result,tracks))
                if log: log.write(json.dumps(payload,allow_nan=False)+'\n'); log.flush()
                dirty=False
            if args.frames and processed>=args.frames: break
            if not args.headless:
                signature=(processed,stage,cfg.mode,cfg.roi_shape)
                if signature!=painted:
                    label=f'{idx+1}/{len(files)} {frame_source}' if files else frame_source
                    view=compose(result,tracks,stage,cfg,label)
                    cv2.imshow('AVL WhiteLineDetection',view)
                    painted=signature
                remaining_ms=1000/args.fps-(time.perf_counter()-loop_start)*1000
                key=cv2.waitKeyEx(max(1,round(remaining_ms)) if playing and not source else 20)
                if ord('A')<=key<=ord('Z'): key+=ord('a')-ord('A')
                if key in (27,ord('q')) or cv2.getWindowProperty('AVL WhiteLineDetection',cv2.WND_PROP_VISIBLE)<1: break
                if key==ord('i'): stage=(stage-1)%len(stages)
                if key==ord('o'): stage=(stage+1)%len(stages)
                if key in (ord('m'),ord('r')):
                    if key==ord('m'): cfg.mode=MODES[(MODES.index(cfg.mode)+1)%len(MODES)]
                    else: cfg.roi_shape='article' if cfg.roi_shape=='rectangle' else 'rectangle'
                    tracker.reset(); detector=Detector(cfg); dirty=True
                if key==ord('t'): tracker.reset(); dirty=True
                if key==32 and files: playing=not playing
                if key in (ord('a'),ord('d'),2424832,2555904,65361,65363) and files:
                    idx=(idx+(-1 if key in (ord('a'),2424832,65361) else 1))%len(files)
                    playing=False; tracker.reset(); dirty=True
                if key==ord('s'):
                    out=Path('results'); out.mkdir(exist_ok=True); stem=f'frame_{idx:06}_{cfg.mode}_{stage+1}'
                    cv2.imwrite(str(out/(stem+'.jpg')),view)
                    cv2.imwrite(str(out/(stem+'_stage.png')),result.stages[stages[stage]])
                    cv2.imwrite(str(out/(stem+'_final.png')),render(result,tracks))
                    (out/(stem+'_metadata.json')).write_text(json.dumps(payload,indent=2,allow_nan=False)+'\n')
                    save_config(cfg,out/'effective_config.json')
            if playing:
                if files or cap: idx+=1
                if files and idx>=len(files): break
                dirty=True
                # Headless replay is intentionally unpaced for benchmarking.
            elif not files: dirty=True
    finally:
        if source: source.close()
        if cap: cap.release()
        if log: log.close()
        if not args.headless: cv2.destroyAllWindows()
        if times:
            summary={'frames':processed,'mode':cfg.mode,'backend':cfg.backend,'debug':not args.headless or args.export_dir is not None,
                     'mean_compute_ms':float(np.mean(times)),'p50_compute_ms':float(np.percentile(times,50)),
                     'p95_compute_ms':float(np.percentile(times,95)),
                     'compute_fps':1000/float(np.mean(times)),
                     'wall_seconds':time.perf_counter()-wall_start,'capture_frames_dropped':dropped,
                     'note':'Compute includes detection + tracking and enabled debug construction; excludes decoding, export, logging and display. Not labeled accuracy.',
                     'config':asdict(cfg)}
            print(json.dumps(summary,indent=2))
            if args.benchmark:
                args.benchmark.parent.mkdir(parents=True,exist_ok=True)
                args.benchmark.write_text(json.dumps(summary,indent=2)+'\n')

if __name__=='__main__': main()
