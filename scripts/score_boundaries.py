"""Score reviewed native-image centerlines, preserving unreviewed status."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from avl_white_lines.evaluation import validate_dataset,score_dataset,polyline
from avl_white_lines.config import load_config
from avl_white_lines.detector import Detector
from avl_white_lines.original_viewer import process


def original_centerlines(image,mode):
    stages,_,_=process(image,mode,False);fits=stages[16];lines=[]
    for color in ((255,110,40),(60,230,80),(70,100,255)):
        mask=np.linalg.norm(fits.astype(float)-color,axis=2)<25
        rows=np.flatnonzero(mask.any(axis=1))
        if len(rows)<2:continue
        ys=rows[np.linspace(0,len(rows)-1,min(64,len(rows))).astype(int)]
        lines.append([[float(np.median(np.flatnonzero(mask[y]))),float(y)] for y in ys])
    return lines


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--labels',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--config',type=Path,default=ROOT/'config/recording_review.json');p.add_argument('--original',action='store_true')
    p.add_argument('--original-mode',type=int,choices=(0,1,2),default=0)
    p.add_argument('--predictions',type=Path,help='Re-score frozen native-pixel predictions after labels are reviewed')
    args=p.parse_args();data=validate_dataset(json.loads(args.labels.read_text(encoding='utf-8')),args.labels.parent)
    metadata={};predictions={};snapshot=[]
    if args.predictions:
        frozen=json.loads(args.predictions.read_text(encoding='utf-8'))
        if frozen.get('schema_version')!=1:raise ValueError('Unsupported predictions schema')
        by_id={f['id']:f for f in frozen['frames']}
        if len(by_id)!=len(frozen['frames']) or set(by_id)!={f['id'] for f in data['frames']}:raise ValueError('Prediction frame identities mismatch')
        for f in data['frames']:
            row=by_id[f['id']]
            if row['image_sha256']!=f['image_sha256'] or row['image_size']!=f['image_size']:raise ValueError('Prediction source identity mismatch')
            predictions[f['id']]=[polyline(b['points']).tolist() for b in row['boundaries']]
        metadata=dict(source='frozen_predictions',prediction_sha256=hashlib.sha256(args.predictions.read_bytes()).hexdigest())
    else:
        cfg=load_config(args.config);detector=Detector(cfg)
        for f in data['frames']:
            image=cv2.imread(str(args.labels.parent/f['image']));w,h=f['image_size']
            if args.original:lines=original_centerlines(image,args.original_mode)
            else:
                result=detector.detect(image)
                lines=[]
                for o in result.observations:
                    if o.centerline_image:points=(np.array(o.centerline_image)*[w-1,h-1]).tolist()
                    else:
                        y=np.linspace(o.y_min,o.y_max,64);points=np.column_stack([o.x(y)*(w-1),y*(h-1)]).tolist()
                    lines.append(points)
            predictions[f['id']]=lines
            snapshot.append(dict(id=f['id'],image_sha256=f['image_sha256'],image_size=f['image_size'],boundaries=[dict(id=f'prediction_{i+1}',points=p) for i,p in enumerate(lines)]))
        metadata=dict(source='original_avl_fitted_centerlines' if args.original else 'avl_per_frame_centerlines',original_mode=args.original_mode if args.original else None,
                      config=asdict(cfg) if not args.original else None,note='Per-frame hypotheses before temporal confirmation. Original fitted-line raster is converted to centerlines; upstream Marvin does not expose equivalent centerlines through its public mask API.')
        prediction_path=args.output.with_name(args.output.stem+'_predictions.json');prediction_path.parent.mkdir(parents=True,exist_ok=True)
        prediction_path.write_text(json.dumps(dict(schema_version=1,metadata=metadata,frames=snapshot),indent=2,allow_nan=False)+'\n',encoding='utf-8')
    report=score_dataset(data,predictions)
    report.update(metadata=metadata,labels_sha256=hashlib.sha256(args.labels.read_bytes()).hexdigest())
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],frames_reviewed=report['frames_reviewed'],metrics=report['metrics']),indent=2))
if __name__=='__main__':main()
