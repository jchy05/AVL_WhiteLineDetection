"""Explain removed evidence without changing segmentation or navigation gates."""
from dataclasses import asdict, replace
from pathlib import Path

import cv2
import numpy as np

from avl_white_lines.config import load_config
from avl_white_lines.detector import Detector
from avl_white_lines.navigation import navigation_output
from avl_white_lines.tracking import Tracker
from test_physical_integration import config
from test_ridge import render

ROOT = Path(__file__).resolve().parents[1]
FILTERS = ('ridge_candidates', 'side_darkness', 'color', 'width', 'hysteresis', 'shade', 'length', 'depth')


def test_gate_counts_are_sequential_and_debug_does_not_change_output():
    image, _ = render()
    det = Detector(config())
    result = det.detect(image)
    counts = result.diagnostics['gate_pixels']
    assert all(counts[a] >= counts[b] for a, b in zip(FILTERS, FILTERS[1:]))
    assert counts['depth'] > 0
    assert counts['final_dilated'] == np.count_nonzero(result.mask)
    mask, debug = det.ridge.operator.detect(result.original, return_debug=True)
    assert np.array_equal(mask, det.ridge.operator.detect(result.original))
    assert np.all(debug['length_mask'] <= debug['shade_mask'])
    assert np.all(debug['shade_mask'] <= debug['hysteresis_mask'])


def test_diagnostics_distinguish_length_rejection_from_missing_ridges():
    image, _ = render()
    result = Detector(config(minimum_length_m=100)).detect(image)
    counts = result.diagnostics['gate_pixels']
    assert counts['ridge_candidates'] > 0 and counts['shade'] > 0
    assert counts['length'] == 0 and not result.mask.any()
    blank = Detector(config()).detect(np.full_like(image, 100))
    assert all(value == 0 for value in blank.diagnostics['gate_pixels'].values())


def test_detail_profile_changes_only_resolution_and_remains_navigation_blocked():
    base = load_config(ROOT / 'config/recording_review.json')
    detail = load_config(ROOT / 'config/recording_detail.json')
    assert detail.processing_width == 960
    assert asdict(replace(detail, processing_width=base.processing_width)) == asdict(base)
    image = cv2.imread(str(ROOT / 'examples/raw/frame_000000.jpg'))
    detector = Detector(detail)
    tracker = Tracker(detail)
    for index in range(3):
        result = detector.detect(image)
        tracks = tracker.update(result.observations, 1 + index / 30)
    assert result.mask.shape == (540, 960) and result.mask.any()
    assert not navigation_output(result, tracks, detail).tracks
