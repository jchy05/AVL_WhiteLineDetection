"""Metric components. Ground axes: X forward, Y left, Z up (metres)."""
import cv2
import numpy as np
from .detector import Observation
from .ridge import _sample


def extract_components(mask, det, debug, policy='diagnostic'):
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    observations = []; kept_labels=[]; diagnostics=[]
    # This full-frame geometry is shared by every component.
    perp_full,_=det._per_px(debug['nx'],debug['ny'])
    for identity in range(1,count):
        left,top,bw,bh,area=stats[identity]
        ys,xs = np.nonzero(labels[top:top+bh,left:left+bw]==identity)
        ys+=top; xs+=left
        flags=[]
        if len(xs)<3:
            diagnostics.append(dict(label=identity,flags=['insufficient_geometry'],pixels=int(area)))
            continue
        gx,gy,_ = det._ray(xs,ys)
        ground = np.column_stack([gx,gy])
        # Local PCA orders samples even for markings across the image. Bin across
        # the long axis; median transverse position suppresses strip thickness.
        center = np.median(ground,axis=0)
        axis = np.linalg.svd(ground-center,full_matrices=False)[2][0]
        if axis[0]<0: axis=-axis
        along = (ground-center)@axis
        span = np.ptp(along)
        bins = np.clip(((along-along.min())/max(span,1e-9)*min(79,max(2,int(span/.05)))).astype(int),0,79)
        gp=[]; ip=[]
        for b in np.unique(bins):
            take=bins==b
            gp.append(np.median(ground[take],axis=0))
            ip.append([float(np.median(xs[take])/(det.W-1)),float(np.median(ys[take])/(det.H-1))])
        gp=np.asarray(gp)
        if len(gp)<2:
            diagnostics.append(dict(label=identity,flags=['insufficient_geometry'],pixels=int(area)))
            continue
        # Local quadratic smoothing suppresses pixel-grid stair steps without
        # replacing curved components by a single global line. Project the
        # smoothed metric samples back into the same camera for consistency.
        if len(gp)>=7:
            arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(gp,axis=0),axis=1))]
            starts=np.clip(np.arange(len(gp))-3,0,len(gp)-7)
            ids=starts[:,None]+np.arange(7)[None,:]
            t=arc[ids]-arc[:,None]
            t/=np.maximum(np.max(np.abs(t),axis=1,keepdims=True),1e-9)
            design=np.stack([np.ones_like(t),t,t*t],axis=-1)
            weights=np.linalg.pinv(design)[:,0,:]
            gp=np.einsum('ij,ijk->ik',weights,gp[ids])
        world=np.column_stack([gp,np.full(len(gp),-det.h)])
        optx=world@det.xc; opty=world@det.yc; optz=world@det.zc
        ip=np.column_stack([(det.fx*optx/optz+det.cx)/(det.W-1),(det.fy*opty/optz+det.cy)/(det.H-1)]).tolist()
        length=float(np.linalg.norm(np.diff(gp,axis=0),axis=1).sum())
        # Width is diagnostic by default. Estimate it on well-resolved core
        # samples only; evaluating the whole image once per component added
        # unnecessary cost and the far samples were discarded anyway.
        perpendicular=perp_full[ys,xs]
        selected=np.flatnonzero(perpendicular<=np.quantile(perpendicular,.30))
        if len(selected)>192: selected=selected[np.linspace(0,len(selected)-1,192).astype(int)]
        wy,wx=ys[selected],xs[selected]
        normal_x=debug['nx'][wy,wx]; normal_y=debug['ny'][wy,wx]
        scales=debug['best_s'][wy,wx]
        offsets=np.linspace(-3,3,49)[:,None]*np.maximum(scales,.9)[None,:]
        profile=_sample(debug['logL'],wx[None,:]+normal_x[None,:]*offsets,wy[None,:]+normal_y[None,:]*offsets).reshape(offsets.shape)
        floor=np.maximum(profile[0],profile[-1]); peak=profile.max(axis=0)
        above=profile>(floor+.5*(peak-floor))[None,:]
        measured_px=above.sum(axis=0)*(6/48)*np.maximum(scales,.9)
        width=float(np.median(measured_px*perpendicular[selected]))
        if not det.p['w_min']<=width<=det.p['w_max']: flags.append('component_width_out_of_range')
        # A component indistinguishable from a straight strip at its measured
        # width has no evidence for pixel-grid bends. Keep a straight polyline
        # in that case; curved strips retain their local quadratic samples.
        c0=gp.mean(axis=0)
        direction=np.linalg.svd(gp-c0,full_matrices=False)[2][0]
        normal=np.array([-direction[1],direction[0]])
        residual=np.abs((gp-c0)@normal)
        if np.median(residual)<=max(.005,.1*width) and np.quantile(residual,.9)<=max(.015,.25*width):
            gp=c0+np.outer((gp-c0)@direction,direction)
            world=np.column_stack([gp,np.full(len(gp),-det.h)])
            optx=world@det.xc; opty=world@det.yc; optz=world@det.zc
            ip=np.column_stack([(det.fx*optx/optz+det.cx)/(det.W-1),(det.fy*opty/optz+det.cy)/(det.H-1)]).tolist()
            length=float(np.linalg.norm(np.diff(gp,axis=0),axis=1).sum())
        if length<det.p['min_len_m']: flags.append('component_length_below_minimum')
        diagnostics.append(dict(label=identity,flags=flags.copy(),pixels=int(area),width_m=width,length_m=length,bbox=[int(left),int(top),int(bw),int(bh)],rejected=bool(flags and policy=='strict')))
        if flags and policy=='strict': continue
        a,b=np.polyfit(np.asarray(ip)[:,1],np.asarray(ip)[:,0],1) if np.ptp(np.asarray(ip)[:,1])>1e-5 else (0,float(np.mean(np.asarray(ip)[:,0])))
        delta=gp[-1]-gp[0]
        strength=float(np.median(debug['best'][ys,xs]))
        confidence=float(np.clip(.35+.35*min(1,strength/det.p['t_high'])+.2*min(1,length),0, .9))
        if flags: confidence*=.75
        kept_labels.append(identity)
        observations.append(Observation(float(a),float(b),min(q[1] for q in ip),max(q[1] for q in ip),confidence,len(xs),
            backend='marvin_ridge',centerline_ground=gp.tolist(),centerline_image=ip,length_m=length,width_m=width,
            heading_rad=float(np.arctan2(delta[1],delta[0])),quality_flags=flags))
    return observations, labels, kept_labels, diagnostics


def component_dict(o,identity):
    points=np.asarray(o.centerline_ground)
    headings=np.arctan2(np.gradient(points,axis=0)[:,1],np.gradient(points,axis=0)[:,0]).tolist() if len(points)>1 else []
    return dict(id=identity,component_label=o.component_label,quality_flags=o.quality_flags.copy(),local_headings_rad=headings,backend=o.backend,confidence=o.confidence,length_m=o.length_m,width_m=o.width_m,
                heading_rad=o.heading_rad,centerline_ground=o.centerline_ground,centerline_image=o.centerline_image,
                depth_confirmed=o.depth_confirmed)


def metric_cost(a,b,gate):
    if a.backend!=b.backend: return None
    p,q=np.asarray(a.centerline_ground),np.asarray(b.centerline_ground)
    angle=abs((a.heading_rad-b.heading_rad+np.pi/2)%np.pi-np.pi/2)
    ratio=min(a.length_m,b.length_m)/max(a.length_m,b.length_m,1e-9)
    center_distance=float(np.linalg.norm(np.mean(p,axis=0)-np.mean(q,axis=0)))
    if angle>.6 or ratio<.25 or center_distance>max(a.length_m,b.length_m)*.6+gate: return None
    separation=np.maximum(np.maximum(p.min(axis=0)-q.max(axis=0),q.min(axis=0)-p.max(axis=0)),0)
    if np.linalg.norm(separation)>=gate: return None
    distances=np.linalg.norm(p[:,None,:]-q[None,:,:],axis=2)
    da,db=distances.min(axis=1),distances.min(axis=0)
    overlap=min(float(np.mean(da<gate)),float(np.mean(db<gate)))
    distance=float((np.median(da)+np.median(db))/2)
    if distance>=gate or overlap<.4: return None
    return distance+.1*angle+.05*(1-overlap)+.03*(1-ratio)+.02*(1-b.confidence)


def smooth_points(old,new,alpha):
    def sampled(points):
        points=np.asarray(points)
        s=np.r_[0,np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))]
        return np.column_stack([np.interp(np.linspace(0,s[-1],32),s,points[:,i]) for i in range(2)])
    a,b=sampled(old),sampled(new)
    if np.linalg.norm(a[0]-b[-1])<np.linalg.norm(a[0]-b[0]): a=a[::-1]
    return ((1-alpha)*a+alpha*b).tolist()
