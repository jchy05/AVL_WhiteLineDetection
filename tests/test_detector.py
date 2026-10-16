import json
import cv2
import numpy as np
import pytest
from avl_white_lines.config import Config,MODES,load_config,save_config
from avl_white_lines.detector import STAGES,detect,extract_observations

def test_packaged_settings_round_trip(tmp_path):
    cfg=load_config(); target=tmp_path/'settings.json'; save_config(cfg,target)
    assert cfg==load_config(target)

@pytest.mark.parametrize('kwargs',[{'mode':'yellow'},{'roi_top':.8},{'blur_kernel':4},{'confirm_hits':0},{'canny_low':180,'canny_high':80}])
def test_bad_config_fails(kwargs):
    with pytest.raises(ValueError): Config(**kwargs).validate()

@pytest.mark.parametrize('mode',MODES)
def test_exact_mask_sources_and_filtered_image(mode):
    rng=np.random.default_rng(32)
    image=rng.integers(0,256,(180,320,3),dtype=np.uint8)
    r=detect(image,Config(mode=mode,processing_width=320),debug=True)
    assert tuple(r.stages)==STAGES and len(STAGES)==17
    source={'article_hsl_white':'Article white mask','previous_hsv':'Previous HSV mask','saved_hsl':'Saved HSL mask'}[mode]
    assert np.array_equal(r.stages['Active color mask'],r.stages[source])
    assert np.array_equal(r.stages['Filtered original'],cv2.bitwise_and(image,image,mask=r.stages[source]))
    assert not r.stages['ROI edges'][:72].any()

def test_empty_frame_has_no_line_and_no_debug_allocation():
    result=detect(np.zeros((540,960,3),np.uint8),Config())
    assert result.observations==[] and result.stages=={}

def test_independent_lines_do_not_share_a_fixed_right_group():
    # Two long parallel markings would both land on the old right-hand bin.
    segments=np.array([[600,300,800,520],[603,300,803,520],[750,300,950,520],[753,300,953,520]])
    observations,accepted=extract_observations(segments,1000,540,Config())
    assert len(observations)==2
    assert abs(observations[0].x(.8)-observations[1].x(.8))>.1
    assert sum(len(x) for x in accepted)==4

def test_bright_small_foreground_object_not_a_supported_lane():
    segments=np.array([[400,450,410,470],[402,450,412,470]])
    assert extract_observations(segments,960,540,Config())[0]==[]

def test_synthetic_paint_yields_line_observations():
    image=np.full((540,960,3),70,np.uint8)
    cv2.line(image,(30,539),(400,280),(255,255,255),9)
    cv2.line(image,(900,539),(600,280),(255,255,255),9)
    result=detect(image,Config())
    assert len(result.observations)>=2
    assert all(np.isfinite([o.a,o.b,o.confidence]).all() for o in result.observations)

def test_reject_wrong_image_type():
    with pytest.raises(ValueError): detect(np.zeros((10,10),np.uint8),Config())
