import numpy as np
from avl_white_lines.config import Config
from avl_white_lines.detector import Observation
from avl_white_lines.tracking import Tracker

def obs(b=.2,a=.3): return Observation(a,b,.5,.95,.9,8)

def test_confirm_requires_consecutive_frames():
    t=Tracker(Config())
    assert not t.update([obs()],0)[0]['valid']
    assert not t.update([obs()],.03)[0]['valid']
    assert t.update([obs()],.06)[0]['valid']

def test_misses_are_explicitly_invalid_and_expire():
    t=Tracker(Config(confirm_hits=1))
    first=t.update([obs()],0)[0]
    held=t.update([],.03)[0]
    assert first['valid'] and held['status']=='held' and not held['valid']
    assert held['confidence']<first['confidence']
    assert t.update([],.2)==[]

def test_missing_tentative_breaks_confirmation_streak():
    t=Tracker(Config())
    t.update([obs()],0); t.update([obs()],.02); t.update([],.04)
    assert not t.update([obs()],.06)[0]['valid']

def test_id_follows_geometry_across_old_bin_boundary():
    t=Tracker(Config(confirm_hits=1))
    ids=[]
    for i,b in enumerate(np.linspace(.23,.32,8)):
        tracks=t.update([obs(float(b),0)],i/30)
        ids.append(next(x['id'] for x in tracks if x['valid']))
    assert len(set(ids))==1

def test_one_to_one_assignment_does_not_merge_parallel_markings():
    t=Tracker(Config(confirm_hits=1))
    initial=t.update([obs(.2),obs(.55)],0)
    updated=t.update([obs(.56),obs(.21)],.03)
    assert {x['id'] for x in initial}=={x['id'] for x in updated}
    assert len(updated)==2 and all(x['valid'] for x in updated)

def test_large_jump_does_not_drag_old_line():
    t=Tracker(Config(confirm_hits=1))
    old=t.update([obs(.1)],0)[0]
    new=t.update([obs(.7)],.03)
    assert next(x for x in new if x['id']==old['id'])['status']=='held'
    assert len([x for x in new if x['status']=='measured'])==1

def test_smoothing_reduces_injected_jitter():
    t=Tracker(Config(confirm_hits=1))
    raw=[]; filtered=[]
    for i in range(80):
        b=.3+(.01 if i%2 else -.01)
        raw.append(b); filtered.append(t.update([obs(b)],i/30)[0]['b'])
    assert np.std(np.diff(filtered[10:]))<.5*np.std(np.diff(raw[10:]))

def test_backward_and_long_gap_reset_state_without_reusing_ids():
    t=Tracker(Config(confirm_hits=1))
    first=t.update([obs()],1)[0]['id']
    second=t.update([obs()],.5)[0]['id']
    third=t.update([obs()],2)[0]['id']
    assert len({first,second,third})==3

def test_no_observations_never_invents_tracks():
    t=Tracker(Config())
    assert t.update([],0)==[]
    assert t.update([],1)==[]
