"""Navigation evidence is stricter than the inspection mask or a stable track."""
from dataclasses import dataclass
import math
import cv2
import numpy as np


@dataclass
class NavigationResult:
    tracks: list
    mask: np.ndarray
    points: list
    reasons: list
    calibration_id: str
    ground_frame_id: str

    def payload(self):
        return dict(eligible=bool(self.tracks),detected=bool(self.tracks),tracks=self.tracks,
                    reasons=self.reasons,calibration_id=self.calibration_id,ground_frame_id=self.ground_frame_id,
                    output_role='navigation_evidence_not_a_driving_authorization')


def navigation_output(result,tracks,cfg,status='ok',frame_age_seconds=None):
    blank=np.zeros(result.original.shape[:2],np.uint8); reasons=[]
    if status!='ok': reasons.append(status)
    if frame_age_seconds is not None and (not math.isfinite(frame_age_seconds) or not -.05<=frame_age_seconds<=cfg.max_frame_age_seconds): reasons.append('invalid_frame_age')
    if result.backend!='marvin_ridge': reasons.append('backend_not_metric_ridge')
    if not cfg.calibration_verified or not cfg.calibration_id.strip(): reasons.append('calibration_not_verified')
    if not cfg.ground_frame_id.strip(): reasons.append('ground_frame_not_configured')
    if not result.ground_estimate.get('depth_gate_applied'): reasons.append('no_registered_depth_gate')
    if result.component_labels is None or result.ground_confirmed_mask is None: reasons.append('no_depth_component_evidence')
    if reasons: return NavigationResult([],blank,[],reasons,cfg.calibration_id,cfg.ground_frame_id)
    eligible=[]; points=[]; core=np.zeros_like(blank)
    for track in tracks:
        label=track.get('component_label',0)
        if not track.get('valid') or track.get('status')!='measured' or track.get('backend')!='marvin_ridge': continue
        if track.get('quality_flags') or not track.get('depth_confirmed'): continue
        measured=np.asarray(result.depth_points.get(label,[]),dtype=float)
        if not label or measured.ndim!=2 or measured.shape[1]!=2 or not len(measured) or not np.isfinite(measured).all(): continue
        measured=measured[np.linalg.norm(measured,axis=1)<=cfg.maximum_range_m]
        if not len(measured): continue
        eligible.append(track); points.extend([(float(x),float(y),0.) for x,y in measured])
        core[result.component_labels==label]=255
    mask=cv2.dilate(core,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3)))
    mask=cv2.bitwise_and(mask,result.ground_confirmed_mask)
    if result.mask is not None: mask=cv2.bitwise_and(mask,result.mask)
    if not eligible: reasons.append('no_current_confirmed_ground_tracks')
    return NavigationResult(eligible,mask,points,reasons,cfg.calibration_id,cfg.ground_frame_id)


def inspection_overlay(result,navigation):
    image=result.original.copy(); image[navigation.mask>0]=(0,255,0)
    text='NAV EVIDENCE: '+str(len(navigation.tracks)) if navigation.tracks else 'NAV BLOCKED: '+', '.join(navigation.reasons)
    cv2.putText(image,text[:85],(8,20),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,220,0) if navigation.tracks else (0,100,255),1,cv2.LINE_AA)
    return image


def populate_navigation_stages(result,navigation):
    if 'Navigation mask' in result.stages:
        result.stages['Navigation mask']=navigation.mask
        result.stages['Navigation overlay']=inspection_overlay(result,navigation)
    result.diagnostics['navigation']=dict(eligible=bool(navigation.tracks),reasons=navigation.reasons)


def navigation_message_available(message,now,receipt_age,max_frame_age=.25):
    """Receiver-side watchdog check for the ROS navigation JSON contract.

    Return availability, not a motion command. Call again as time passes even
    if no new messages arrive; empty/blocked evidence is unknown, not clear road.
    """
    if not isinstance(message,dict): return False
    if message.get('output_role')!='navigation_evidence_not_a_driving_authorization': return False
    if message.get('eligible') is not True or message.get('status')!='ok' or not message.get('tracks'): return False
    source=message.get('source_stamp_sec');published=message.get('published_stamp_sec');ttl=message.get('valid_for_seconds')
    values=(source,published,ttl,now,receipt_age,max_frame_age)
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in values): return False
    if source<=0 or ttl<=0 or max_frame_age<=0 or receipt_age<0: return False
    return bool(-.05<=now-source<=max_frame_age and -.05<=now-published<=ttl and receipt_age<=ttl)
