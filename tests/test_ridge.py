# Adapted upstream fixtures/tests: arassal/Marvin_White_Line d6aa919
"""Offline tests: numpy + opencv + pytest only.

    PYTHONPATH=. python3 -m pytest tests -q

Scenes are rendered with the real camera geometry: a top-down ground canvas
(1 cm/px) is projected into the camera with the ground-plane homography.
"""
import numpy as np
import cv2
import pytest

from avl_white_lines.camera import PRESETS
from avl_white_lines.physical import PhysicalDetector
from avl_white_lines.ground import fit_ground
from avl_white_lines.config import Config
from dataclasses import asdict

class WhiteLineDetector:
    def __init__(self,cam,ground_live=False,ground_every=15):
        self.det=PhysicalDetector(Config(backend="marvin_ridge",camera=asdict(cam),processing_width=480,ground_live=ground_live,ground_every=ground_every))
    def detect(self,img,depth=None):
        mask=self.det.detect(img,depth).mask
        return cv2.resize(mask,(img.shape[1],img.shape[0]),interpolation=cv2.INTER_NEAREST)>0
    def geometry(self): return self.det.estimate or (self.det.camera.height_m,self.det.camera.pitch_deg)

CAM = PRESETS['marvin_right_2026_09_17']
W, H = 480, 300
RES = 0.01                       # m per canvas px
X0, X1, Y0, Y1 = 0.5, 10.0, -4.0, 4.0


def homography(cam):
    """Ground (X fwd, Y left, Z=0) -> image, via canvas pixel coordinates."""
    t = np.radians(cam.pitch_deg)
    R = np.array([[0.0, -1.0, 0.0],                          # camera x (right) in world
                  [-np.sin(t), 0.0, -np.cos(t)],             # camera y (down)
                  [np.cos(t), 0.0, -np.sin(t)]])             # camera z (forward)
    C = np.array([0.0, 0.0, cam.height_m])
    G = np.column_stack([R[:, 0], R[:, 1], -R @ C])          # [r1 r2 t] for Z=0
    # canvas pixel (u, v) -> ground (X, Y): column u runs along -Y, row v along -X
    A = np.array([[0.0, -RES, X1], [-RES, 0.0, Y1], [0.0, 0.0, 1.0]])
    return cam.K_for(W, H) @ G @ A


def render(tape=True, shadow=False, seed=0):
    rng = np.random.default_rng(seed)
    ch, cw = int((X1 - X0) / RES), int((Y1 - Y0) / RES)
    base = 120 + 12 * rng.standard_normal((ch, cw))           # concrete-ish texture
    base = cv2.GaussianBlur(base.astype(np.float32), (0, 0), 1.5)
    canvas = np.repeat(base[:, :, None], 3, axis=2)
    label = np.zeros((ch, cw), np.uint8)
    if tape:   # 7.6 cm tape along X at Y = 0.6 m, from 2 to 7 m
        u = int((Y1 - 0.6) / RES)
        v0, v1 = int((X1 - 7.0) / RES), int((X1 - 2.0) / RES)
        canvas[v0:v1, u - 4:u + 4] = 235
        label[v0:v1, u - 4:u + 4] = 1
    if shadow:   # hard straight shadow edge across the ground
        canvas[:, : cw // 2] *= 0.45
    Hm = homography(CAM)
    img = cv2.warpPerspective(np.clip(canvas, 0, 255).astype(np.uint8), Hm, (W, H),
                              flags=cv2.INTER_AREA, borderValue=(150, 170, 200))
    gt = cv2.warpPerspective(label, Hm, (W, H), flags=cv2.INTER_NEAREST) > 0
    return img, gt


def ground_depth(cam=CAM):
    """Optical-axis depth of the ground plane at every pixel (NaN above horizon)."""
    K = cam.K_for(W, H)
    v, u = np.mgrid[0:H, 0:W].astype(np.float64)
    y = (v - K[1, 2]) / K[1, 1]
    t = np.radians(cam.pitch_deg)
    den = np.cos(t) * y + np.sin(t)
    return np.where(den > 1e-6, cam.height_m / np.maximum(den, 1e-6), np.nan).astype(np.float32)


def test_finds_tape():
    img, gt = render(tape=True)
    m = WhiteLineDetector(CAM).detect(img)
    near = cv2.dilate(gt.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    assert (m & near).sum() > 0.5 * gt.sum(), 'tape not found'
    assert (m & ~near).sum() < 0.05 * gt.sum(), 'false detections off the tape'


def test_ignores_plain_ground_and_shadow_edge():
    img, _ = render(tape=False, shadow=True)
    assert WhiteLineDetector(CAM).detect(img).sum() < 20


def test_any_input_size():
    img, _ = render(tape=True)
    big = cv2.resize(img, (960, 600), interpolation=cv2.INTER_CUBIC)
    m = WhiteLineDetector(CAM).detect(big)
    assert m.shape == (600, 960) and m.dtype == bool and m.sum() > 0


def test_depth_keeps_tape_on_ground_and_drops_raised_stripe():
    img, gt = render(tape=True)
    det = WhiteLineDetector(CAM)
    zg = ground_depth()
    on_ground = det.detect(img, zg)
    raised = zg.copy()
    raised[cv2.dilate(gt.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0] *= 0.7   # well above ground
    lifted = det.detect(img, raised)
    assert on_ground.sum() > 0.5 * det.detect(img).sum()
    assert lifted.sum() == 0


def test_ground_fit_recovers_mount():
    r = fit_ground(ground_depth(), CAM.K_for(W, H), 18.0, h_ref=0.6)
    assert r is not None
    assert abs(r[0] - CAM.height_m) < 0.01 and abs(r[1] - CAM.pitch_deg) < 0.3


def test_ground_live_corrects_wrong_height():
    import dataclasses
    wrong = dataclasses.replace(CAM, height_m=CAM.height_m + 0.15)   # e.g. robot on a hoist
    det = WhiteLineDetector(wrong, ground_live=True, ground_every=1)
    img, _ = render(tape=True)
    det.detect(img, ground_depth())
    assert abs(det.geometry()[0] - CAM.height_m) < 0.01


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
