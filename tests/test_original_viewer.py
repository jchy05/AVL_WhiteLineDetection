import json
import sys
import cv2
import numpy as np
from avl_white_lines import original_viewer as original

def test_original_stage_order_and_native_resolution():
    image=np.full((720,1280,3),70,np.uint8)
    cv2.line(image,(40,719),(550,360),(255,255,255),9)
    stages,final,_=original.process(image)
    assert len(stages)==17
    assert [title for title,_ in original.STAGES]==[
        'Original','HSV saturation','HSV value','HSL lightness','HSL saturation',
        'Article white mask','Previous HSV mask','Saved HSL mask','Active color mask',
        'Filtered original','Grayscale','Gaussian blur','Canny edges','ROI edges',
        'Raw Hough segments','Accepted segments','Fitted line mask']
    assert all(stage.shape[:2]==(720,1280) for stage in stages)
    assert final.shape==image.shape
    assert not stages[13][:288].any()

def test_original_modes_and_uppercase_navigation():
    state=original.State()
    for _ in range(17): state.key(ord('O'),5)
    assert state.stage==8
    state.key(ord('I'),5); assert state.stage==7
    state.key(ord('A'),5); assert state.index==4
    state.key(ord('D'),5); assert state.index==0
    for _ in range(3): state.key(ord('M'),5)
    assert state.mode==0
    state.key(ord('R'),5); assert state.article_roi

def test_original_export_includes_every_stage_and_final(tmp_path,monkeypatch):
    image_dir=tmp_path/'images'; image_dir.mkdir()
    cv2.imwrite(str(image_dir/'frame.png'),np.full((180,320,3),210,np.uint8))
    output=tmp_path/'export'
    monkeypatch.setattr(sys,'argv',['original',str(image_dir),'--export','--output-dir',str(output)])
    original.main()
    assert len(list((output/'preview').glob('[0-9][0-9]_*.png')))==17
    assert (output/'preview'/'final.png').is_file()
    assert (output/'preview'/'viewer.jpg').is_file()
    assert 'fitted_groups' in json.loads((output/'preview'/'details.json').read_text())
