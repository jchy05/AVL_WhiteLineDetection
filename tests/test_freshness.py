import time
import numpy as np
from avl_white_lines.capture import LatestCapture
from avl_white_lines.ros_node import fresh_stamp

def test_ros_stamp_rejects_old_zero_future_and_nan():
    assert fresh_stamp(10,10.1,.25)
    assert not fresh_stamp(10,11,.25)
    assert not fresh_stamp(0,0,.25)
    assert not fresh_stamp(11,10,.25)
    assert not fresh_stamp(float('nan'),10,.25)

def test_capture_overwrites_old_frames_and_signals_failure(monkeypatch):
    class FakeCapture:
        def __init__(self,source): self.index=0; self.released=False
        def isOpened(self): return True
        def set(self,*args): pass
        def read(self):
            self.index+=1
            return (True,np.full((2,2,3),self.index,np.uint8)) if self.index<=5 else (False,None)
        def release(self): self.released=True
    monkeypatch.setattr('avl_white_lines.capture.cv2.VideoCapture',FakeCapture)
    capture=LatestCapture(0)
    capture.thread.join(timeout=1)
    packet=capture.get(0)
    assert packet[0]==5 and int(packet[2][0,0,0])==5
    assert capture.get(5,timeout=.01) is None
    assert capture.failed
    capture.close()
    assert capture.capture.released
