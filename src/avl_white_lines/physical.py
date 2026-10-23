"""Persistent calibrated adapter around Marvin's ridge operator."""
from collections import deque
import time
import cv2
import numpy as np
from .camera import camera_from_config
from .ridge import WhiteRidgeDetector
from .ground import fit_ground
from .components import extract_components
from .detector import FrameResult
from .region import image_region

RIDGE_STAGES=('Original','Log luminance','Ground region','Configured image region','Ridge response','Selected ridge scale','Ridge orientation',
              'Width gate','Side-darkness gate','Color gate','Length gate','Depth/object gate','Connected components',
              'Tracked components','Final mask','Final overlay','Navigation mask','Navigation overlay')

class PhysicalDetector:
    def __init__(self,cfg):
        self.cfg=cfg; self.camera=camera_from_config(cfg.camera)
        self.history=deque(maxlen=5); self.frames=0; self.estimate=None; self.key=None; self.operator=None

    def detect(self,frame,depth=None,debug=False):
        start=time.perf_counter(); cfg=self.cfg
        if frame is None or frame.dtype!=np.uint8 or frame.ndim!=3 or frame.shape[2]!=3: raise ValueError('Expected uint8 BGR frame')
        H,W=frame.shape[:2]
        if min(H,W)<8: raise ValueError('Frame too small')
        w=min(W,cfg.processing_width); h=round(H*w/W)
        img=cv2.resize(frame,(w,h),interpolation=cv2.INTER_AREA) if w!=W else frame
        d=None
        if depth is not None:
            depth=np.asarray(depth)
            if depth.shape!=(H,W) or not np.issubdtype(depth.dtype,np.floating): raise ValueError('Depth must be registered HxW floating optical-axis metres')
            d=cv2.resize(depth.astype(np.float32),(w,h),interpolation=cv2.INTER_NEAREST)
        height,pitch=self.estimate or (self.camera.height_m,self.camera.pitch_deg)
        fit_accepted=False
        if d is not None and cfg.ground_live and self.frames%cfg.ground_every==0:
            fit=fit_ground(d,self.camera.K_for(w,h),pitch,h_ref=self.camera.height_m)
            if fit is not None:
                self.history.append(fit[:2]); target=np.median(self.history,axis=0)
                self.estimate=tuple(target if self.estimate is None else .8*np.array(self.estimate)+.2*target)
                height,pitch=self.estimate; fit_accepted=True
        self.frames+=1
        key=(w,h,height,pitch)
        if key!=self.key:
            self.operator=WhiteRidgeDetector(self.camera.K_for(w,h),height,pitch,w,h,
                w_min=cfg.line_width_min_m,w_max=cfg.line_width_max_m,min_len_m=cfg.minimum_length_m,
                max_range_m=cfg.maximum_range_m,t_high=cfg.ridge_threshold_high,t_low=cfg.ridge_threshold_low,side_log=cfg.side_log_threshold)
            self.key=key
        det=self.operator
        use_depth=d if cfg.use_depth_gate else None
        mask,info=det.detect(img,depth=use_depth,depth_margin=cfg.object_height_m/height,
                            depth_vote=cfg.depth_vote,depth_confirm=cfg.depth_confirm,return_debug=True)
        # Component geometry uses the undilated accepted ridge core. Display mask
        # includes upstream's one-pixel dilation and can contain several fragments.
        region=image_region((h,w),cfg.image_roi)
        ungated_pixels=int(np.count_nonzero(mask))
        mask &= region>0
        region_core=info['depth_mask'] & (region>0)
        observations,labels,valid_labels,component_diagnostics=extract_components(region_core,det,info,cfg.component_policy)
        confirmed=np.zeros((h,w),bool); depth_points={}
        if use_depth is not None:
            confirmed=np.isfinite(use_depth)&(use_depth>0)&(np.abs(use_depth-det.z_ground)<=det.z_ground*cfg.object_height_m/height)&(region>0)
            gy,gx=np.nonzero(confirmed)
            z=use_depth[gy,gx]; ry=(gy-det.cy)/det.fy; rx=(gx-det.cx)/det.fx
            actual_range=np.hypot(z*(det.zc[0]+ry*det.yc[0]),-z*rx)
            confirmed[gy,gx] &= actual_range<=cfg.maximum_range_m
        for o,label in zip(observations,valid_labels):
            o.component_label=label
            if use_depth is not None:
                # Core gate has already voted on ground support before creating observations.
                pixels=labels==label
                o.depth_confirmed=bool(np.mean(confirmed[pixels])>=max(cfg.depth_confirm,.01))
                vy,vx=np.nonzero(pixels & confirmed)
                if len(vx):
                    keep=np.linspace(0,len(vx)-1,min(100,len(vx))).astype(int)
                    vy,vx=vy[keep],vx[keep]; z=use_depth[vy,vx]
                    ry=(vy-det.cy)/det.fy; rx=(vx-det.cx)/det.fx
                    # Coordinates from measured optical depth, not a guessed floor intersection.
                    depth_points[label]=np.column_stack([z*(det.zc[0]+ry*det.yc[0]),-z*rx]).astype(float).tolist()
            else: o.confidence*=.85
        core=np.isin(labels,valid_labels)&(labels>0)
        if cfg.component_policy=='strict':
            mask=cv2.dilate(core.astype(np.uint8),cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3)))>0
            mask &= det.ground & (region>0)
        # Otherwise retain the ridge operator's segmentation unchanged. The
        # optional component measurements cannot silently delete image evidence.
        stages={}
        if debug:
            gray=lambda a: cv2.normalize(np.nan_to_num(a).astype(np.float32),None,0,255,cv2.NORM_MINMAX).astype(np.uint8)
            binary=lambda a: a.astype(np.uint8)*255
            colors=np.zeros_like(img)
            from .detector import line_color
            for i in valid_labels: colors[labels==i]=line_color(i)
            overlay=img.copy(); overlay[mask]=(255,255,0)
            values=[img,gray(info['logL']),binary(det.ground),region,gray(info['best']),gray(info['best_s']),
                cv2.applyColorMap(gray(np.arctan2(info['ny'],info['nx'])),cv2.COLORMAP_HSV),
                binary(info['width_gate']),binary(info['side_gate']),binary(info['color_gate']),binary(info['length_mask']),
                binary(region_core),colors,np.zeros_like(img),binary(mask),overlay,np.zeros((h,w),np.uint8),img.copy()]
            stages=dict(zip(RIDGE_STAGES,values))
        estimate=dict(height_m=float(height),pitch_deg=float(pitch),live=self.estimate is not None,fit_accepted=fit_accepted,
                      depth_available=d is not None,depth_gate_applied=use_depth is not None,
                      coordinates='X forward, Y left, Z up; metres')
        return FrameResult(img,observations,stages,((det.ground & (region>0)).astype(np.uint8)*255),(time.perf_counter()-start)*1000,0,
                           mask.astype(np.uint8)*255,'marvin_ridge',estimate,
                           dict(component_policy=cfg.component_policy,components=component_diagnostics,image_roi_applied=bool(cfg.image_roi),roi_removed_mask_pixels=ungated_pixels-int(np.count_nonzero(mask))),
                           labels,confirmed.astype(np.uint8)*255,depth_points)
