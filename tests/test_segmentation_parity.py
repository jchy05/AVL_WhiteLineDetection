"""Component metadata must not silently alter the upstream ridge mask."""
import hashlib
import json
from pathlib import Path
import platform
import cv2
import numpy as np
import pytest
from avl_white_lines.config import Config
from avl_white_lines.detector import Detector
from avl_white_lines.tracking import Tracker
from avl_white_lines.ros_node import ground_cloud_points

ROOT=Path(__file__).resolve().parents[1]
REFERENCE=json.loads((Path(__file__).parent/'fixtures/marvin_rgb_reference.json').read_text())


def cfg(**kwargs):
    return Config(backend='marvin_ridge',camera=REFERENCE['camera'],processing_width=480,ground_live=False,**kwargs).validate()


@pytest.mark.parametrize('entry',REFERENCE['frames'],ids=lambda e:e['image'])
def test_default_mask_matches_ridge_before_component_checks(entry):
    path=ROOT/'examples/raw'/entry['image']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==entry['image_sha256']
    frame=cv2.imread(str(path)); detector=Detector(cfg())
    result=detector.detect(frame)
    reference_mask=detector.ridge.operator.detect(result.original)
    assert np.array_equal(result.mask>0,reference_mask)
    # Frozen masks were generated independently by the upstream checkout.
    # Cross-platform parity above uses the same running OpenCV kernel.
    if platform.system()==REFERENCE['platform'] and cv2.__version__==REFERENCE['opencv']:
        assert hashlib.sha256((result.mask>0).tobytes()).hexdigest()==entry['mask_sha256']
    assert result.diagnostics['component_policy']=='diagnostic'


@pytest.mark.parametrize('name,anchor',[('frame_000410.jpg',[.88,.79]),('frame_000474.jpg',[.70,.78])])
def test_previously_rejected_road_paint_can_confirm_as_track(name,anchor):
    image=cv2.imread(str(ROOT/'examples/raw'/name)); detector=Detector(cfg());tracker=Tracker(cfg())
    for i in range(3):
        result=detector.detect(image)
        tracks=tracker.update(result.observations,1+i/30)
    nearby=[t for t in tracks if min(np.linalg.norm(np.asarray(t['centerline_image'])-anchor,axis=1))<.04]
    assert nearby and any(t['valid'] for t in nearby)
    assert any('component_width_out_of_range' in t['quality_flags'] for t in nearby)
    # Questionable dimensions remain in image evidence, not costmap output.
    assert ground_cloud_points([dict(t,depth_confirmed=True) for t in nearby])==[]


def test_strict_policy_is_explicit_and_cannot_add_mask_pixels():
    image=cv2.imread(str(ROOT/'examples/raw/frame_000474.jpg'))
    normal=Detector(cfg()).detect(image)
    strict=Detector(cfg(component_policy='strict')).detect(image)
    assert np.any((normal.mask>0)&(strict.mask==0))
    assert not np.any((strict.mask>0)&(normal.mask==0))
    assert any(d.get('rejected') for d in strict.diagnostics['components'])


def test_component_policy_validation():
    with pytest.raises(ValueError): cfg(component_policy='invalid')


def test_diagnostic_policy_keeps_thin_evidence_but_flags_it():
    from test_physical_integration import scene,config
    image,_=scene('straight',.01)
    # The synthetic renderer uses the historical right camera, not the real-frame fixture's front preset.
    normal=Detector(config()).detect(image)
    strict=Detector(config(component_policy='strict')).detect(image)
    assert normal.mask.any() and not strict.mask.any()
    assert any('component_width_out_of_range' in o.quality_flags for o in normal.observations)
