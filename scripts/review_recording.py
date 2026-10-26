"""Review every frame and select diverse frames for manual labels. No accuracy claims."""
import argparse
from dataclasses import asdict
import hashlib
from html import escape
from urllib.parse import quote
import json
from pathlib import Path
import shutil
import sys
import time
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from avl_white_lines.config import load_config
from avl_white_lines.detector import Detector
from avl_white_lines.tracking import Tracker
from avl_white_lines.navigation import navigation_output


def choose_review_frames(rows,count):
    if not rows:return []
    known={f'frame_{n:06}.jpg' for n in (0,410,474,710,1077)}
    selected=set([i for i,r in enumerate(rows) if r['image'] in known][:count])
    for i in np.linspace(0,len(rows)-1,min(8,count),dtype=int).tolist():
        if len(selected)>=count:break
        selected.add(i)
    ranked=sorted(range(2,len(rows)),key=lambda i:(-rows[i]['review_priority'],i))
    for separation in (20,10,0):
        for i in ranked:
            if len(selected)>=count:break
            if i not in selected and all(abs(i-j)>=separation for j in selected):selected.add(i)
    return sorted(selected)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--images',type=Path,required=True)
    p.add_argument('--config',type=Path,default=ROOT/'config/recording_review.json');p.add_argument('--output',type=Path,required=True)
    p.add_argument('--fps',type=float,default=30);p.add_argument('--review-count',type=int,default=24)
    args=p.parse_args()
    if args.fps<=0 or not np.isfinite(args.fps) or args.review_count<1:p.error('Positive finite fps/review count required')
    if args.output.exists() and (args.output/'labeling/labels.json').exists():p.error('Output already contains labels; choose a new folder to preserve work')
    files=sorted(args.images.glob('*.jpg'))
    if not files:p.error('No JPG frames found')
    out=args.output;out.mkdir(parents=True,exist_ok=True)
    cfg=load_config(args.config);detector=Detector(cfg);tracker=Tracker(cfg)
    source={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in (ROOT/'src/avl_white_lines').glob('*.py')}
    rows=[];previous=None;prev_ids=set();prev_count=0;prev_valid=0;all_ids=set();started=time.perf_counter()
    for idx,file in enumerate(files):
        image=cv2.imread(str(file))
        if image is None:raise ValueError('Cannot decode '+file.name)
        begin=time.perf_counter();result=detector.detect(image);tracks=tracker.update(result.observations,idx/args.fps)
        nav=navigation_output(result,tracks,cfg);compute=(time.perf_counter()-begin)*1000
        mask=result.mask>0 if result.mask is not None else np.zeros(result.original.shape[:2],bool)
        pixels=int(mask.sum());ids={t['id'] for t in tracks};valid=sum(t['valid'] for t in tracks)
        if previous is not None and previous.shape==mask.shape:
            union=int(np.count_nonzero(previous|mask));iou=float(np.count_nonzero(previous&mask)/union) if union else None
        else:iou=None
        change=abs(pixels-prev_count)/max(pixels,prev_count,50) if idx else 0.
        new_ids=ids-prev_ids;reasons=[]
        if iou is not None and iou<.5:reasons.append('mask_overlap_changed')
        if prev_valid and not valid:reasons.append('confirmed_candidates_disappeared')
        if pixels==0:reasons.append('empty_candidate_mask')
        if change>.35:reasons.append('candidate_area_changed')
        if idx>2 and new_ids:reasons.append('new_track_ids')
        priority=float((1-iou if iou is not None else 0)+change+(1 if prev_valid and not valid else 0)+min(len(new_ids),3)*.1)
        rows.append(dict(index=idx,image=file.name,candidate_pixels=pixels,components=len(result.observations),
            confirmed_candidates=valid,tentative=sum(t['status']=='tentative' for t in tracks),held=sum(t['status']=='held' for t in tracks),
            new_track_ids=sorted(new_ids),mask_iou_previous=iou,relative_area_change=change,review_priority=priority,
            review_reasons=reasons,navigation_eligible=bool(nav.tracks),processing_ms=compute))
        all_ids.update(ids);previous=mask.copy();prev_ids=ids;prev_count=pixels;prev_valid=valid
        if (idx+1)%100==0:print(f'Reviewed {idx+1}/{len(files)} frames',flush=True)
    chosen=choose_review_frames(rows,min(args.review_count,len(rows)))
    label_dir=out/'labeling';(label_dir/'images').mkdir(parents=True,exist_ok=True);(out/'previews').mkdir(exist_ok=True)
    dataset=dict(schema_version=1,name='manual_boundary_review',coordinate_system='native_image_pixels',frames=[])
    cards=[]
    for i in chosen:
        path=files[i];image=cv2.imread(str(path));h,w=image.shape[:2];shutil.copyfile(path,label_dir/'images'/path.name)
        dataset['frames'].append(dict(id=path.stem,image='images/'+path.name,image_size=[w,h],image_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            reviewed=False,reviewed_by='',condition='unknown',boundaries=[],draft_points=[],selection_reasons=rows[i]['review_reasons']))
        result=Detector(cfg).detect(image);overlay=result.original.copy()
        if result.mask is not None:overlay[result.mask>0]=(255,255,0)
        raw=cv2.resize(image,(overlay.shape[1],overlay.shape[0]),interpolation=cv2.INTER_AREA)
        preview=np.hstack([raw,overlay]);cv2.imwrite(str(out/'previews'/(path.stem+'.jpg')),preview)
        cards.append(f'<section><h2>{escape(path.name)}</h2><p>Review priority {rows[i]["review_priority"]:.2f}: '+', '.join(rows[i]['review_reasons'])+f'</p><img src="previews/{quote(path.stem)}.jpg"></section>')
    (label_dir/'labels.json').write_text(json.dumps(dataset,indent=2)+'\n',encoding='utf-8')
    (label_dir/'dataset.js').write_text('window.initialDataset='+json.dumps(dataset).replace('<','\u003c')+';\n',encoding='utf-8')
    for name in ('index.html','editor.js'):shutil.copyfile(ROOT/'scripts/label_editor'/name,label_dir/name)
    times=[r['processing_ms'] for r in rows]
    summary=dict(frames=len(rows),config=asdict(cfg),source_sha256=source,replay_clock_fps=args.fps,
        mean_pipeline_ms=float(np.mean(times)),p95_pipeline_ms=float(np.percentile(times,95)),wall_seconds=time.perf_counter()-started,
        frames_with_confirmed_candidates=sum(r['confirmed_candidates']>0 for r in rows),empty_masks=sum(r['candidate_pixels']==0 for r in rows),
        distinct_track_ids=len(all_ids),navigation_eligible_frames=sum(r['navigation_eligible'] for r in rows),selected_review_indices=chosen,
        reviewed_labels=0,note='Change scores prioritize human inspection, not proven detection failures. Motion/exposure/scene changes can alter overlap and IDs. Distinct IDs are not labeled identity switches. Nominal replay clock; no measured acquisition timestamps. No depth/calibration or accuracy claims.')
    (out/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    (out/'frames.jsonl').write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in rows),encoding='utf-8')
    html='<!doctype html><meta charset="utf-8"><title>Full recording review</title><style>body{background:#15191f;color:#eee;font:16px system-ui;margin:24px}img{max-width:100%}a{color:#9cd5ff}section{margin:28px 0}</style><h1>Full recording review</h1><p>Raw / current cropped candidates. Changes may be legitimate camera motion or scene changes; these are review priorities, not scored failures.</p><p><a href="labeling/index.html">Open raw-image labeling tool</a> · <a href="summary.json">Summary</a> · <a href="frames.jsonl">Every frame</a></p>'
    (out/'index.html').write_text(html+''.join(cards),encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':main()
