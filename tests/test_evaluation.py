import copy
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
import pytest
from avl_white_lines.evaluation import boundary_error,match_boundaries,score_dataset,validate_dataset

LINE=[[10,10],[10,90]]


def frame(reviewed=True,boundaries=None):
    return dict(id='a',image='images/a.jpg',image_size=[100,100],image_sha256='unused',reviewed=reviewed,
                reviewed_by='human-test' if reviewed else '',condition='test',boundaries=boundaries if boundaries is not None else [dict(id='left',points=LINE)],draft_points=[])


def data(f=None):return dict(schema_version=1,coordinate_system='native_image_pixels',frames=[f or frame()])


def test_exact_reversed_and_curved_polylines_have_zero_error():
    for line in (LINE,[[10,10],[20,35],[40,60],[70,80]]):
        assert boundary_error(line,line)['correct']
        assert boundary_error(line[::-1],line)['position_error_px']<1e-10
        assert boundary_error(line[::-1],line)['angle_error_deg']<1e-10


@pytest.mark.parametrize('shift,correct',[(9.9,True),(10.,False),(10.1,False)])
def test_strict_position_threshold(shift,correct):
    p=(np.array(LINE)+[shift,0]).tolist()
    assert boundary_error(p,LINE)['correct'] is correct


@pytest.mark.parametrize('angle,correct',[(1.9,True),(2.1,False)])
def test_angle_limit(angle,correct):
    p=np.array(LINE,dtype=float);a=np.radians(angle);R=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
    p=(p-p[0])@R.T+p[0]
    assert boundary_error(p,LINE)['correct'] is correct


def test_short_fragment_and_unsupported_extension_fail_coverage():
    assert not boundary_error([[10,40],[10,50]],LINE)['correct']
    assert not boundary_error([[10,-100],[10,200]],LINE)['correct']


def test_duplicates_are_false_positives():
    r=match_boundaries([LINE,LINE],[LINE])
    assert (r['true_positives'],r['false_positives'],r['false_negatives'])==(1,1,0)


def test_matching_reassigns_to_maximize_valid_pairs():
    # p0 can match either GT; p1 can only match g0.
    p0=[[15,10],[15,90]];p1=[[5,10],[5,90]];g1=[[24,10],[24,90]]
    r=match_boundaries([p0,p1],[LINE,g1])
    assert r['true_positives']==2


def test_unreviewed_frames_never_produce_accuracy_scores():
    r=score_dataset(data(frame(False)),{'a':[LINE]})
    assert r['status']=='needs_reviewed_labels' and r['metrics'] is None and not r['frames']


def test_reviewed_negative_and_missing_detection():
    negative=frame(boundaries=[]);negative['negative']=True
    r=score_dataset(data(negative),{'a':[LINE]})
    assert r['metrics']['false_positives']==1 and r['metrics']['recall'] is None
    r=score_dataset(data(),{'a':[]})
    assert r['metrics']['false_negatives']==1 and r['metrics']['recall']==0


@pytest.mark.parametrize('mutate',[
    lambda f:f.update(reviewed_by=''),lambda f:f.update(reviewed_by=None),
    lambda f:f.update(reviewed_by=True),lambda f:f.update(reviewed_by=0),lambda f:f.update(negative=True),
    lambda f:f.update(draft_points=[[1,2]]),
    lambda f:f.update(boundaries=[]),lambda f:f.update(reviewed='true')])
def test_invalid_review_states_rejected(mutate):
    f=frame();mutate(f)
    with pytest.raises(ValueError):score_dataset(data(f),{'a':[LINE]})


def test_hash_dimensions_and_paths_are_checked(tmp_path):
    (tmp_path/'images').mkdir();image=np.zeros((100,100,3),np.uint8);path=tmp_path/'images/a.jpg';cv2.imwrite(str(path),image)
    f=frame();f['image_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();d=data(f)
    validate_dataset(d,tmp_path)
    bad=copy.deepcopy(d);bad['frames'][0]['image']='../outside.jpg'
    with pytest.raises(ValueError,match='escapes'):validate_dataset(bad,tmp_path)
    bad=copy.deepcopy(d);bad['frames'][0]['image_size']=[101,100]
    with pytest.raises(ValueError,match='dimensions'):validate_dataset(bad,tmp_path)
    bad=copy.deepcopy(d);bad['frames'][0]['image_sha256']='wrong'
    with pytest.raises(ValueError,match='hash'):validate_dataset(bad,tmp_path)


def test_duplicate_ids_and_out_of_bounds_labels_rejected(tmp_path):
    d=data();d['frames'].append(copy.deepcopy(d['frames'][0]))
    with pytest.raises(ValueError,match='Duplicate'):validate_dataset(d,tmp_path,False)
    d=data();d['frames'][0]['boundaries'][0]['points']=[[0,0],[101,40]]
    with pytest.raises(ValueError,match='outside'):validate_dataset(d,tmp_path,False)


def test_prediction_frame_identity_mismatch_rejected():
    with pytest.raises(ValueError,match='IDs'):score_dataset(data(),{'other':[LINE]})


def test_matched_error_means_are_reported_without_hiding_counts():
    r=score_dataset(data(),{'a':[(np.array(LINE)+[1,0]).tolist()]})
    assert r['metrics']['true_positives']==1
    assert r['metrics']['mean_matched_position_error_px']==pytest.approx(1)
    assert r['metrics']['mean_matched_angle_error_deg']==pytest.approx(0)


def test_review_selection_keeps_known_examples_and_target_count():
    from scripts.review_recording import choose_review_frames
    rows=[dict(image=f'frame_{i:06}.jpg',review_priority=float(i%19)) for i in range(1078)]
    selected=choose_review_frames(rows,24)
    assert len(selected)==24 and selected==sorted(set(selected))
    assert {0,410,474,710,1077}<=set(selected)
    assert len(choose_review_frames(rows,3))==3
