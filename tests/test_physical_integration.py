from dataclasses import asdict, replace
import json
import cv2
import numpy as np
import pytest
from test_ridge import CAM,W,H,RES,X1,Y1,homography,render,ground_depth
from avl_white_lines.config import Config
from avl_white_lines.detector import Detector,legacy_detect,render as overlay
from avl_white_lines.tracking import Tracker
from avl_white_lines.components import metric_cost
from avl_white_lines.physical import RIDGE_STAGES
from avl_white_lines.ros_node import depth_metres
from avl_white_lines.cli import compose


def config(**kw):
    return Config(backend='marvin_ridge',camera=asdict(CAM),processing_width=480,ground_live=False,**kw).validate()


def scene(kind='curve',width=.076):
    canvas=np.full((950,800,3),120,np.uint8); label=np.zeros(canvas.shape[:2],np.uint8)
    xs=np.linspace(2,7,300); ys=.6+.10*(xs-4)**2 if kind=='curve' else np.full_like(xs,.6)
    pts=np.column_stack([(Y1-ys)/RES,(X1-xs)/RES]).astype(np.int32)
    color=(20,20,20) if kind in ('crack','joint') else (235,235,235)
    cv2.polylines(canvas,[pts],False,color,max(1,round(width/RES)))
    if kind not in ('crack','joint'): cv2.polylines(label,[pts],False,1,max(1,round(width/RES)))
    hm=homography(CAM)
    return (cv2.warpPerspective(canvas,hm,(W,H),flags=cv2.INTER_AREA,borderValue=(150,170,200)),
            cv2.warpPerspective(label,hm,(W,H),flags=cv2.INTER_NEAREST)>0)


@pytest.mark.parametrize('kind',['crack','joint'])
def test_dark_strips_rejected(kind):
    image,_=scene(kind,.03)
    assert Detector(config()).detect(image).mask.sum()==0


@pytest.mark.parametrize('width',[.01,.7])
def test_strict_policy_out_of_band_bright_objects(width):
    image,_=scene('straight',width)
    assert np.count_nonzero(Detector(config(component_policy='strict')).detect(image).mask)<25


def test_curves_have_physical_geometry_and_visible_debug():
    image,gt=scene()
    result=Detector(config()).detect(image,debug=True)
    assert tuple(result.stages)==RIDGE_STAGES
    assert result.observations
    curve=max(result.observations,key=lambda o:o.length_m)
    assert len(curve.centerline_ground)>8 and curve.length_m>.3 and 0<curve.width_m<.3
    p=np.array(curve.centerline_ground)
    assert np.ptp(p[:,1])>.1
    tracks=Tracker(config(confirm_hits=1)).update(result.observations,1)
    for stage in range(len(RIDGE_STAGES)): assert compose(result,tracks,stage,config()).ndim==3
    assert overlay(result,tracks).shape==image.shape
    json.dumps(tracks,allow_nan=False)


def test_depth_units_alignment_and_missing_depth():
    image,_=render()
    detector=Detector(config())
    assert detector.detect(image).observations
    with pytest.raises(ValueError): detector.detect(image,depth=np.ones((2,2),np.float32))
    with pytest.raises(ValueError): detector.detect(image,depth=np.ones((H,W),np.uint16))
    assert np.isnan(depth_metres(np.array([[0]],np.uint16),'16UC1')).all()
    assert depth_metres(np.array([[1200]],np.uint16),'16UC1')[0,0]==pytest.approx(1.2)
    assert not detector.detect(image,depth=np.full((H,W),np.nan,np.float32)).observations
    assert not detector.detect(image,depth=ground_depth()*1.5).observations
    assert detector.detect(image,depth=ground_depth()).observations[0].depth_confirmed
    assert not detector.detect(image).observations[0].depth_confirmed


def test_isolated_bad_depth_does_not_remove_component():
    image,_=render(); d=ground_depth()
    d[::10,::10]*=.5
    assert Detector(config()).detect(image,depth=d).observations


def test_curved_metric_association_reorder_and_lifecycle():
    image,_=scene(); observations=Detector(config()).detect(image).observations
    o=max(observations,key=lambda o:o.length_m)
    tracker=Tracker(config())
    identities=[]
    for i in range(6):
        moved=replace(o,centerline_ground=(np.array(o.centerline_ground)+[0,.01*(-1)**i]).tolist())
        ts=tracker.update([moved],i/30); identities.append(ts[0]['id'])
    assert len(set(identities))==1 and ts[0]['valid']
    assert not tracker.update([],.20)[0]['valid']
    assert tracker.update([],.40)==[]
    a=Tracker(config(confirm_hits=1)); a.update([o],1)
    assert a.update([o],.5)[0]['id']!=1
    far=replace(o,centerline_ground=(np.array(o.centerline_ground)+[0,2]).tolist())
    assert metric_cost(o,far,.35) is None
    other=replace(o,backend='legacy_hough_fallback')
    assert metric_cost(o,other,.35) is None


def test_metric_smoothing_reduces_ground_jitter():
    image,_=scene(); o=max(Detector(config()).detect(image).observations,key=lambda o:o.length_m)
    tracker=Tracker(config(confirm_hits=1)); raw=[]; smoothed=[]
    for i in range(30):
        d=.05*(-1)**i
        shifted=replace(o,centerline_ground=(np.array(o.centerline_ground)+[0,d]).tolist())
        raw.append(np.mean(shifted.centerline_ground,axis=0)[1])
        smoothed.append(np.mean(tracker.update([shifted],i/30)[0]['centerline_ground'],axis=0)[1])
    assert np.std(np.diff(smoothed[5:])) < np.std(np.diff(raw[5:]))*.5


def test_backend_selection_and_explicit_fallback(monkeypatch):
    image,_=render()
    cfg=config(); cfg.backend='legacy_hough'
    baseline=legacy_detect(image,cfg,True); selected=Detector(cfg).detect(image,True)
    for stage in baseline.stages: assert np.array_equal(baseline.stages[stage],selected.stages[stage])
    cfg.backend='hybrid_fallback'
    from avl_white_lines.physical import PhysicalDetector
    original=PhysicalDetector.detect
    def empty(self,*a,**kw):
        result=original(self,*a,**kw); result.observations=[]; return result
    monkeypatch.setattr(PhysicalDetector,'detect',empty)
    result=Detector(cfg).detect(image)
    assert result.backend=='legacy_hough_fallback'
    assert all(o.backend==result.backend and o.confidence<=.5 for o in result.observations)


def test_camera_requires_explicit_calibration_and_bad_configs_fail():
    with pytest.raises(ValueError): Config(backend='marvin_ridge').validate()
    for kw in ({'minimum_length_m':0},{'depth_vote':2},{'line_width_min_m':.2},{'tracking_enabled':1}):
        with pytest.raises(ValueError): config(**kw)


def test_live_estimate_smoothing_and_corrupt_depth_rejection():
    image,_=render()
    cfg=config(); cfg.ground_live=True; cfg.ground_every=1
    detector=Detector(cfg)
    first=detector.detect(image,depth=ground_depth())
    modified=replace(CAM,height_m=CAM.height_m+.06)
    result=detector.detect(image,depth=ground_depth(modified))
    assert first.ground_estimate['live']
    assert CAM.height_m<result.ground_estimate['height_m']<modified.height_m
    result2=detector.detect(image,depth=np.zeros((H,W),np.float32))
    assert not result2.ground_estimate['fit_accepted']
    assert result2.ground_estimate['height_m']==result.ground_estimate['height_m']


def test_costmap_cloud_excludes_held_fallback_and_unconfirmed_depth():
    from avl_white_lines.ros_node import ground_cloud_points
    good=dict(valid=True,backend='marvin_ridge',depth_confirmed=True,centerline_ground=[[2,.5],[3,.6]])
    assert len(ground_cloud_points([good]))==2
    assert ground_cloud_points([dict(good,valid=False)])==[]
    assert ground_cloud_points([dict(good,backend='legacy_hough_fallback')])==[]
    assert ground_cloud_points([dict(good,depth_confirmed=False)])==[]
    assert len(ground_cloud_points([dict(good,depth_confirmed=False)],False))==2


def test_camera_projection_round_trip_and_horizon():
    p=np.array([[2,.6],[4,-.2],[7,.4]])
    uv=CAM.ground_to_pixel(p,W,H)
    assert np.allclose(CAM.pixel_to_ground(uv[:,0],uv[:,1],W,H),p)
    assert np.isnan(CAM.pixel_to_ground(240,CAM.horizon_for(W,H)-2,W,H)).all()


@pytest.mark.parametrize('backend',['marvin_ridge','legacy_hough','hybrid_fallback'])
def test_cli_backends_output_additive_contract_and_export(tmp_path,backend):
    from avl_white_lines.cli import main
    from avl_white_lines.config import save_config
    images=tmp_path/'images'; images.mkdir()
    image,_=scene()
    for i in range(3): cv2.imwrite(str(images/f'{i}.png'),image)
    cfg=config(); cfg.backend=backend
    path=tmp_path/'config.json'; save_config(cfg,path)
    log=tmp_path/'out.jsonl'; export=tmp_path/'export'
    main(['--images',str(images),'--config',str(path),'--headless','--jsonl',str(log),'--export-dir',str(export)])
    rows=[json.loads(line) for line in log.read_text().splitlines()]
    assert len(rows)==3 and all(row['schema_version']==1 and row['status']=='ok' for row in rows)
    assert all('components' in row and 'backend' in row and 'processing_image_size' in row for row in rows)
    assert (export/'0'/'tracked_overlay.png').exists()
    if backend=='marvin_ridge':
        assert rows[-1]['detected']
        assert len(list((export/'0').glob('*.png')))==len(RIDGE_STAGES)+1
        assert rows[-1]['tracks'][0]['local_headings_rad']


@pytest.mark.parametrize('kind',['straight','curve'])
def test_known_geometry_meets_user_position_and_angle_limits(kind):
    image,_=scene(kind)
    o=max(Detector(config()).detect(image).observations,key=lambda x:x.length_m)
    X=np.linspace(2,7,500); Y=.6+.1*(X-4)**2 if kind=='curve' else np.full_like(X,.6)
    expected=CAM.ground_to_pixel(np.column_stack([X,Y]),W,H)
    actual=np.array(o.centerline_image)*[W-1,H-1]
    ds=np.linalg.norm(actual[:,None,:]-expected[None,:,:],axis=2)
    nearest=ds.argmin(axis=1)
    assert np.mean(ds.min(axis=1))<10
    step=max(1,len(actual)//8)
    dp=actual[step:]-actual[:-step]; dg=expected[nearest[step:]]-expected[nearest[:-step]]
    good=(np.linalg.norm(dp,axis=1)>1e-6)&(np.linalg.norm(dg,axis=1)>1e-6)
    delta=np.arctan2(dp[good,1],dp[good,0])-np.arctan2(dg[good,1],dg[good,0])
    assert np.degrees(np.mean(np.abs((delta+np.pi/2)%np.pi-np.pi/2)))<2
