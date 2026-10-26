"""Reviewed centerline evaluation; no accuracy scores from unreviewed drafts."""
import hashlib
import math
from pathlib import Path
import cv2
import numpy as np


def polyline(points):
    p=np.asarray(points,dtype=float)
    if p.ndim!=2 or p.shape[1]!=2 or len(p)<2 or not np.isfinite(p).all():raise ValueError('Expected >=2 finite [x,y] points')
    p=p[np.r_[True,np.linalg.norm(np.diff(p,axis=0),axis=1)>1e-9]]
    if len(p)<2:raise ValueError('Polyline has no length')
    return p


def validate_dataset(data,root,verify_images=True):
    root=Path(root).resolve()
    if type(data.get('schema_version')) is not int or data.get('schema_version')!=1 or data.get('coordinate_system')!='native_image_pixels' or not isinstance(data.get('frames'),list) or not data['frames']:
        raise ValueError('Invalid boundary dataset schema')
    ids=set()
    for f in data['frames']:
        if not isinstance(f.get('id'),str) or not f['id'] or f['id'] in ids:raise ValueError('Duplicate/missing frame ID')
        ids.add(f['id'])
        if not isinstance(f.get('condition','unknown'),str):raise ValueError('Condition must be a string')
        if type(f.get('reviewed')) is not bool:raise ValueError('reviewed must be an explicit boolean')
        if f['reviewed'] and (not isinstance(f.get('reviewed_by'),str) or not f['reviewed_by'].strip()):raise ValueError('Reviewed frame needs reviewer identity')
        if f['reviewed'] and f.get('draft_points'):raise ValueError('Reviewed frame has an unfinished draft')
        size=f.get('image_size')
        if not isinstance(size,list) or len(size)!=2 or any(type(v) is not int or v<2 for v in size):raise ValueError('Invalid native image size')
        image=f.get('image')
        if not isinstance(image,str) or not image or Path(image).is_absolute():raise ValueError('Expected dataset-relative image path')
        path=(root/image).resolve()
        if not path.is_relative_to(root):raise ValueError('Image path escapes dataset directory')
        boundaries=f.get('boundaries')
        if not isinstance(boundaries,list):raise ValueError('Missing boundary list')
        if f['reviewed'] and not boundaries and f.get('negative') is not True:raise ValueError('Reviewed negative must be explicitly marked negative=true')
        if boundaries and f.get('negative'):raise ValueError('Negative frame contains paint labels')
        bids=set()
        for b in boundaries:
            if not isinstance(b.get('id'),str) or not b['id'] or b['id'] in bids:raise ValueError('Duplicate/missing boundary ID')
            bids.add(b['id']);p=polyline(b['points'])
            if np.any(p<0) or np.any(p[:,0]>size[0]-1) or np.any(p[:,1]>size[1]-1):raise ValueError('Label point outside native image')
        if verify_images:
            if hashlib.sha256(path.read_bytes()).hexdigest()!=f.get('image_sha256'):raise ValueError('Source image hash mismatch: '+f['id'])
            img=cv2.imread(str(path))
            if img is None or [img.shape[1],img.shape[0]]!=size:raise ValueError('Source dimensions mismatch')
    return data


def samples(points,count=64):
    p=polyline(points);lengths=np.linalg.norm(np.diff(p,axis=0),axis=1);arc=np.r_[0,np.cumsum(lengths)]
    t=np.linspace(0,arc[-1],count);seg=np.minimum(np.searchsorted(arc,t,side='right')-1,len(p)-2)
    f=(t-arc[seg])/lengths[seg]
    q=p[seg]+f[:,None]*(p[seg+1]-p[seg])
    headings=np.arctan2((p[seg+1]-p[seg])[:,1],(p[seg+1]-p[seg])[:,0])
    return q,headings


def nearest_segments(points,headings,line):
    p=polyline(line);v=p[1:]-p[:-1]
    delta=points[:,None,:]-p[:-1][None,:,:]
    t=np.clip(np.sum(delta*v[None,:,:],axis=2)/np.sum(v*v,axis=1),0,1)
    closest=p[:-1][None,:,:]+t[:,:,None]*v[None,:,:]
    distances=np.linalg.norm(points[:,None,:]-closest,axis=2);minimum=distances.min(axis=1)
    angles=np.abs((headings[:,None]-np.arctan2(v[:,1],v[:,0])[None,:]+np.pi/2)%np.pi-np.pi/2)
    # At shared corners, either tied segment is geometrically valid.
    angles=np.where(distances<=minimum[:,None]+1e-6,angles,np.inf).min(axis=1)
    return minimum,np.degrees(angles)


def boundary_error(predicted,truth,position_limit=10.,angle_limit=2.,coverage_limit=.6):
    gt,heading=samples(truth);pred,pheading=samples(predicted)
    distance,angle=nearest_segments(gt,heading,predicted)
    reverse,_=nearest_segments(pred,pheading,truth)
    pos=float(np.mean(distance));ang=float(np.mean(angle))
    coverage=float(np.mean(distance<position_limit));pred_coverage=float(np.mean(reverse<position_limit))
    return dict(position_error_px=pos,angle_error_deg=ang,truth_coverage=coverage,prediction_coverage=pred_coverage,
                correct=bool(pos<position_limit and ang<angle_limit and min(coverage,pred_coverage)>=coverage_limit))


def match_boundaries(predictions,truths,**thresholds):
    errors=[[boundary_error(p,t,**thresholds) for t in truths] for p in predictions]
    adjacency=[sorted([j for j,e in enumerate(row) if e['correct']],key=lambda j:(row[j]['position_error_px'],row[j]['angle_error_deg'],j)) for row in errors]
    owner={}
    def augment(i,seen):
        for j in adjacency[i]:
            if j in seen:continue
            seen.add(j)
            if j not in owner or augment(owner[j],seen):owner[j]=i;return True
        return False
    for i in range(len(predictions)):augment(i,set())
    matched=[dict(prediction=i,truth=j,**errors[i][j]) for j,i in sorted(owner.items())]
    return dict(true_positives=len(matched),false_positives=len(predictions)-len(matched),false_negatives=len(truths)-len(matched),matches=matched,pair_errors=errors)


def aggregate(rows):
    tp=sum(r['true_positives'] for r in rows);fp=sum(r['false_positives'] for r in rows);fn=sum(r['false_negatives'] for r in rows)
    matched=[m for r in rows for m in r['matches']]
    return dict(mean_matched_position_error_px=float(np.mean([m['position_error_px'] for m in matched])) if matched else None,
        mean_matched_angle_error_deg=float(np.mean([m['angle_error_deg'] for m in matched])) if matched else None,
        frames=len(rows),true_positives=tp,false_positives=fp,false_negatives=fn,
        precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None,
        f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,false_positives_per_frame=fp/len(rows) if rows else None)


def score_dataset(data,predictions,position_limit=10.,angle_limit=2.,coverage_limit=.6):
    if not all(math.isfinite(x) and x>0 for x in (position_limit,angle_limit)) or not 0<coverage_limit<=1:raise ValueError('Invalid evaluation thresholds')
    expected={f['id'] for f in data['frames']}
    if set(predictions)!=expected:raise ValueError('Prediction IDs must exactly match dataset')
    rows=[];conditions={}
    for f in data['frames']:
        if type(f.get('reviewed')) is not bool:raise ValueError('Explicit reviewed boolean required')
        if f['reviewed'] and (not isinstance(f.get('reviewed_by'),str) or not f['reviewed_by'].strip() or f.get('draft_points')):raise ValueError('Reviewed frame needs a reviewer and no unfinished draft')
        if f['reviewed'] and not f['boundaries'] and f.get('negative') is not True:raise ValueError('Reviewed negative must be explicit')
        if f.get('negative') and f['boundaries']:raise ValueError('Negative frame contains paint labels')
        predicted=[polyline(p) for p in predictions[f['id']]]
        if not f['reviewed']:continue
        result=match_boundaries(predicted,[b['points'] for b in f['boundaries']],position_limit=position_limit,angle_limit=angle_limit,coverage_limit=coverage_limit)
        row=dict(frame=f['id'],condition=f.get('condition','unknown'),**result);rows.append(row)
        conditions.setdefault(row['condition'],[]).append(row)
    return dict(status='scored_reviewed_subset' if rows else 'needs_reviewed_labels',frames_total=len(data['frames']),frames_reviewed=len(rows),
        frames_unreviewed=len(data['frames'])-len(rows),thresholds=dict(position_limit_px=position_limit,angle_limit_deg=angle_limit,minimum_bidirectional_coverage=coverage_limit),
        metrics=aggregate(rows) if rows else None,by_condition={k:aggregate(v) for k,v in conditions.items()},frames=rows,
        target='Visible painted centerline segments, not pixel segmentation or a drivable corridor. Unreviewed drafts excluded. Matching maximizes valid one-to-one pairs; thresholds are strict <10px and <2deg by default.')
