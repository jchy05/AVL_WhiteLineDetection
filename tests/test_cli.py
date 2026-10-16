import json
import cv2
import numpy as np
from avl_white_lines.cli import main

def paint():
    img=np.full((360,640,3),70,np.uint8)
    cv2.line(img,(20,359),(270,180),(255,255,255),7)
    cv2.line(img,(620,359),(390,180),(255,255,255),7)
    return img

def test_headless_sequence_writes_valid_contract_and_benchmark(tmp_path):
    images=tmp_path/'images'; images.mkdir()
    for i in range(6): cv2.imwrite(str(images/f'{i:03}.png'),paint())
    log=tmp_path/'detections.jsonl'; bench=tmp_path/'timing.json'
    main(['--images',str(images),'--headless','--jsonl',str(log),'--benchmark',str(bench)])
    rows=[json.loads(x) for x in log.read_text().splitlines()]
    assert len(rows)==6
    assert not rows[0]['detected'] and not rows[1]['detected']
    assert all(row['detected'] for row in rows[2:])
    assert json.loads(bench.read_text())['frames']==6

def test_video_decode_and_tracking_path(tmp_path):
    video=tmp_path/'input.avi'
    writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'MJPG'),30,(640,360))
    assert writer.isOpened()
    for _ in range(8): writer.write(paint())
    writer.release()
    log=tmp_path/'detections.jsonl'
    main(['--video',str(video),'--headless','--jsonl',str(log)])
    rows=[json.loads(x) for x in log.read_text().splitlines()]
    assert len(rows)==8 and rows[-1]['detected']

def test_frame_limit_does_not_process_entire_sequence(tmp_path):
    images=tmp_path/'images'; images.mkdir()
    for i in range(4): cv2.imwrite(str(images/f'{i}.png'),paint())
    log=tmp_path/'detections.jsonl'
    main(['--images',str(images),'--headless','--frames','2','--jsonl',str(log)])
    assert len(log.read_text().splitlines())==2
