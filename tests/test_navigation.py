from dataclasses import asdict,replace
from pathlib import Path
import json
import cv2
import numpy as np
import pytest
from test_ridge import CAM,render,ground_depth,W,H
from test_physical_integration import config
from avl_white_lines.detector import Detector
from avl_white_lines.tracking import Tracker
from avl_white_lines.navigation import navigation_output
from avl_white_lines.calibration import camera_from_rectified_info,depth_registration_reason
from avl_white_lines.region import image_region
from avl_white_lines.config import load_config,Config


def measured():
    return config(calibration_verified=True,calibration_id='synthetic-known-plane',ground_frame_id='test_ground')


def confirmed(cfg,depth=True):
    image,_=render();detector=Detector(cfg);tracker=Tracker(cfg)
    for i in range(3):
        result=detector.detect(image,depth=ground_depth() if depth else None)
        tracks=tracker.update(result.observations,1+i/30)
    return result,tracks


def test_depth_measured_navigation_points_and_mask():
    cfg=measured(); result,tracks=confirmed(cfg)
    output=navigation_output(result,tracks,cfg,frame_age_seconds=.03)
    assert output.tracks and output.points and output.mask.any()
    assert not np.any((output.mask>0)&(result.ground_confirmed_mask==0))
    assert not np.any((output.mask>0)&(result.mask==0))
    p=np.array(output.points)
    assert np.all(p[:,2]==0) and abs(np.median(p[:,1])-.6)<.03
    assert np.linalg.norm(p[:,:2],axis=1).max()<=cfg.maximum_range_m
    assert output.payload()['eligible']


@pytest.mark.parametrize('change,reason',[
    ({'calibration_verified':False},'calibration_not_verified'),
    ({'ground_frame_id':''},'ground_frame_not_configured'),
    ({'calibration_id':''},'calibration_not_verified')])
def test_calibration_assertions_required(change,reason):
    cfg=measured(); result,tracks=confirmed(cfg)
    output=navigation_output(result,tracks,replace(cfg,**change))
    assert not output.tracks and not output.points and not output.mask.any()
    assert reason in output.reasons


def test_no_depth_no_navigation_even_when_rgb_tracks_confirm():
    cfg=measured();result,tracks=confirmed(cfg,False)
    assert any(t['valid'] for t in tracks)
    output=navigation_output(result,tracks,cfg)
    assert not output.tracks and 'no_registered_depth_gate' in output.reasons


@pytest.mark.parametrize('age',[.3,-.2,float('nan'),float('inf')])
def test_old_future_or_nonfinite_age_rejected(age):
    cfg=measured(); result,tracks=confirmed(cfg)
    output=navigation_output(result,tracks,cfg,frame_age_seconds=age)
    assert not output.points and 'invalid_frame_age' in output.reasons


@pytest.mark.parametrize('alter',[
    {'valid':False},{'status':'held'},{'status':'tentative'},
    {'backend':'legacy_hough_fallback'},{'quality_flags':['uncertain_width']},
    {'depth_confirmed':False},{'component_label':99999}])
def test_unsafe_track_categories_never_produce_navigation(alter):
    cfg=measured(); result,tracks=confirmed(cfg)
    output=navigation_output(result,[dict(t,**alter) for t in tracks],cfg)
    assert not output.tracks and not output.points and not output.mask.any()


def test_explicit_stale_status_blocks_everything():
    cfg=measured();result,tracks=confirmed(cfg)
    output=navigation_output(result,tracks,cfg,status='stale')
    assert output.reasons==['stale'] and not output.points


def test_raised_bright_object_below_image_roi_cannot_navigate():
    cfg=measured(); cfg.image_roi=[[0,.55],[1,.55],[1,1],[0,1]]
    from test_ridge import homography
    canvas=np.full((950,800,3),120,np.uint8); label=np.zeros((950,800),np.uint8)
    # Near stripe at X=1.0..2.5m, Y=.3m remains below the recording ROI.
    cv2.rectangle(canvas,(366,750),(374,900),(235,235,235),-1)
    cv2.rectangle(label,(366,750),(374,900),1,-1)
    image=cv2.warpPerspective(canvas,homography(CAM),(W,H),flags=cv2.INTER_AREA,borderValue=(150,170,200))
    gt=cv2.warpPerspective(label,homography(CAM),(W,H),flags=cv2.INTER_NEAREST)>0
    d=ground_depth()
    assert Detector(cfg).detect(image).mask.any()
    d[cv2.dilate(gt.astype(np.uint8),np.ones((9,9),np.uint8))>0]*=.7
    result=Detector(cfg).detect(image,depth=d)
    tracks=Tracker(replace(cfg,confirm_hits=1)).update(result.observations,1)
    assert not navigation_output(result,tracks,cfg).points


def test_camera_info_updates_intrinsics_preserving_measured_mount():
    mount=asdict(CAM);P=np.array([[300.,0,240,0],[0,301,150,0],[0,0,1,0]])
    camera=camera_from_rectified_info(mount,480,300,P)
    assert camera['fx']==300 and camera['fy']==301 and camera['height_m']==CAM.height_m
    assert camera['pitch_deg']==CAM.pitch_deg


@pytest.mark.parametrize('kwargs',[
    {'binning':(2,2)},{'roi':(10,0,400,300)},
    {'projection':[0]*12},{'projection':[float('nan')]*12},
    {'projection':np.eye(3)}, {'width':0}])
def test_unsupported_or_invalid_camera_info_rejected(kwargs):
    args=dict(mount=asdict(CAM),width=480,height=300,projection=[300,0,240,0,0,300,150,0,0,0,1,0]);args.update(kwargs)
    with pytest.raises(ValueError): camera_from_rectified_info(**args)


def test_registration_checks_shape_and_frame_names():
    assert depth_registration_reason((300,480,3),(300,480),'left_optical','left_optical') is None
    assert depth_registration_reason((300,480,3),(150,240),'a','a')=='depth_size_mismatch'
    assert depth_registration_reason((300,480,3),(300,480),'a','b')=='depth_frame_id_mismatch'
    assert depth_registration_reason((300,480,3),(300,480),'','')=='depth_frame_id_missing'


@pytest.mark.parametrize('roi',[[[0,0],[1,1]],[[0,0],[1,1],[0,1],[1,0]],[[0,0],[2,0],[1,1]],[[0,0],[0,0],[0,0]]])
def test_invalid_roi_rejected(roi):
    with pytest.raises(ValueError): config(image_roi=roi)


def test_presets_cannot_be_marked_measured_without_explicit_fields():
    with pytest.raises(ValueError): Config(backend='marvin_ridge',camera='marvin_front',calibration_verified=True,calibration_id='x',ground_frame_id='ground').validate()


@pytest.mark.parametrize('stem,anchor',[
    ('000000',[.22,.74]),('000410',[.88,.79]),('000474',[.70,.78]),
    ('000710',[.80,.85]),('001077',[.73,.85])])
def test_recording_profile_excludes_upper_background_retains_paint_checkpoints(stem,anchor):
    root=Path(__file__).resolve().parents[1];cfg=load_config(root/'config/recording_review.json')
    frame=cv2.imread(str(root/'examples/raw'/('frame_'+stem+'.jpg')))
    result=Detector(cfg).detect(frame);mask=result.mask>0;h,w=mask.shape
    assert not mask[:round(.45*h)].any()
    distance=cv2.distanceTransform((~mask).astype(np.uint8),cv2.DIST_L2,cv2.DIST_MASK_PRECISE)
    x,y=np.rint(np.asarray(anchor)*[w-1,h-1]).astype(int)
    assert distance[y,x]<10
    assert not navigation_output(result,Tracker(cfg).update(result.observations,1),cfg).points


@pytest.mark.parametrize('change',[
    {'eligible':False},{'status':'blocked'},{'tracks':[]},{'output_role':'inspection_candidates'},
    {'valid_for_seconds':0},{'source_stamp_sec':0},{'source_stamp_sec':101},
    {'valid_for_seconds':float('nan')}])
def test_receiver_watchdog_rejects_blocked_or_malformed_messages(change):
    from avl_white_lines.navigation import navigation_message_available
    msg=dict(output_role='navigation_evidence_not_a_driving_authorization',status='ok',eligible=True,
             tracks=[{'id':1}],source_stamp_sec=99.99,published_stamp_sec=100.,valid_for_seconds=.24)
    assert navigation_message_available(msg,100.02,.02)
    msg.update(change)
    assert not navigation_message_available(msg,100.02,.02)


def test_receiver_watchdog_expires_without_new_messages():
    from avl_white_lines.navigation import navigation_message_available
    msg=dict(output_role='navigation_evidence_not_a_driving_authorization',status='ok',eligible=True,
             tracks=[{'id':1}],source_stamp_sec=99.99,published_stamp_sec=100.,valid_for_seconds=.24)
    assert navigation_message_available(msg,100.02,.02)
    assert not navigation_message_available(msg,100.30,.30)
    assert not navigation_message_available(msg,100.02,1.)


def test_navigation_pixels_respect_measured_depth_range_limit():
    cfg=measured();cfg.maximum_range_m=3.
    image,_=render();depth=ground_depth()*1.01;detector=Detector(cfg);tracker=Tracker(cfg)
    for i in range(3):
        result=detector.detect(image,depth=depth);tracks=tracker.update(result.observations,1+i/30)
    output=navigation_output(result,tracks,cfg)
    assert output.mask.any()
    ys,xs=np.nonzero(output.mask)
    K=CAM.K_for(W,H);t=np.radians(CAM.pitch_deg);z=depth[ys,xs]
    X=z*(np.cos(t)-np.sin(t)*(ys-K[1,2])/K[1,1]);Y=-z*(xs-K[0,2])/K[0,0]
    assert np.hypot(X,Y).max()<=cfg.maximum_range_m+1e-5
