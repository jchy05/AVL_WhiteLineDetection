import json
import cv2
import numpy as np
from avl_white_lines.cli import main

def test_tracked_viewer_uppercase_controls_browsing_and_snapshot(tmp_path,monkeypatch):
    images=tmp_path/'images'; images.mkdir()
    for i in range(2):
        frame=np.full((180,320,3),70,np.uint8)
        cv2.line(frame,(10,179),(140,95),(255,255,255),6)
        cv2.imwrite(str(images/f'frame_{i}.png'),frame)
    monkeypatch.chdir(tmp_path)
    events=iter(map(ord,['O','M','D','R','S','Q']))
    rendered=[]
    monkeypatch.setattr(cv2,'namedWindow',lambda *a:None)
    monkeypatch.setattr(cv2,'resizeWindow',lambda *a:None)
    monkeypatch.setattr(cv2,'imshow',lambda title,image:rendered.append(image))
    monkeypatch.setattr(cv2,'waitKeyEx',lambda *a:next(events))
    monkeypatch.setattr(cv2,'getWindowProperty',lambda *a:1)
    monkeypatch.setattr(cv2,'destroyAllWindows',lambda:None)
    main(['--images',str(images)])
    saved=list((tmp_path/'results').glob('*_metadata.json'))
    assert len(saved)==1 and len(rendered)>=5
    payload=json.loads(saved[0].read_text())
    assert payload['mode']=='previous_hsv'
    assert payload['source']=='frame_1.png'
    stem=str(saved[0]).replace('_metadata.json','')
    assert cv2.imread(stem+'_final.png') is not None
    assert cv2.imread(stem+'_stage.png') is not None
    assert json.loads((tmp_path/'results'/'effective_config.json').read_text())['roi_shape']=='article'
