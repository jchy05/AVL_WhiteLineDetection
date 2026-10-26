"""Compare recording profiles without treating candidate area as accuracy."""
import argparse
from dataclasses import asdict
import hashlib
from html import escape
import json
from pathlib import Path
import platform
import sys
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from avl_white_lines.config import load_config
from avl_white_lines.detector import Detector
from avl_white_lines.navigation import navigation_output
from avl_white_lines.tracking import Tracker


def panel(result, title):
    image = result.original.copy()
    image[result.mask > 0] = (255, 255, 0)
    image = cv2.resize(image, (640, round(image.shape[0] * 640 / image.shape[1])))
    cv2.putText(image, title, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 0, 255), 2)
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--images', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New output directory; existing work is preserved')
    parser.add_argument('--baseline', type=Path, default=ROOT / 'config/recording_review.json')
    parser.add_argument('--detail', type=Path, default=ROOT / 'config/recording_detail.json')
    parser.add_argument('--gallery-every', type=int, default=50)
    args = parser.parse_args()
    if args.gallery_every < 1:
        parser.error('--gallery-every must be positive')
    if args.output.exists():
        parser.error('Choose a new output directory to preserve existing work')
    files = sorted(args.images.glob('*.jpg'))
    if not files:
        parser.error('No JPG images found')
    configs = [load_config(args.baseline), load_config(args.detail)]
    detectors = [Detector(c) for c in configs]
    trackers = [Tracker(c) for c in configs]
    args.output.mkdir(parents=True)
    (args.output / 'previews').mkdir()
    names = ['baseline', 'detail']
    rows = []
    cards = []
    for index, path in enumerate(files):
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError('Cannot decode ' + str(path))
        results = [None, None]
        row = dict(index=index, image=path.name, image_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        # Alternate order to reduce systematic ordering bias. Capture/decode,
        # tracking, navigation checks and gallery rendering are excluded from ms.
        for i in ((0, 1) if index % 2 == 0 else (1, 0)):
            start = time.perf_counter()
            result = results[i] = detectors[i].detect(image)
            elapsed = (time.perf_counter() - start) * 1000
            tracks = trackers[i].update(result.observations, index / 30)
            nav = navigation_output(result, tracks, configs[i])
            row[names[i]] = dict(candidate_pixels=int(np.count_nonzero(result.mask)),
                candidate_fraction=float(np.mean(result.mask > 0)), components=len(result.observations),
                confirmed_candidates=sum(t['valid'] for t in tracks), navigation_eligible=bool(nav.tracks),
                processing_ms=elapsed, gate_pixels=result.diagnostics.get('gate_pixels', {}))
        a, b = row['baseline'], row['detail']
        row['empty_to_nonempty'] = a['candidate_pixels'] == 0 and b['candidate_pixels'] > 0
        row['nonempty_to_empty'] = a['candidate_pixels'] > 0 and b['candidate_pixels'] == 0
        rows.append(row)
        if index % args.gallery_every == 0 or index == len(files) - 1 or row['empty_to_nonempty'] or row['nonempty_to_empty'] or path.stem in ('frame_000386', 'frame_000814'):
            preview = np.hstack([panel(results[0], f'Baseline / {configs[0].processing_width} profile'), panel(results[1], f'Detail / {configs[1].processing_width} profile')])
            target = 'previews/' + path.stem + '.jpg'
            cv2.imwrite(str(args.output / target), preview)
            cards.append('<section><h2>' + escape(path.name) + '</h2><img src="' + target + '"></section>')
        if (index + 1) % 100 == 0:
            print(f'Compared {index + 1}/{len(files)}', flush=True)
    summary = dict(frames=len(rows), platform=platform.platform(), opencv=cv2.__version__,
        numpy=np.__version__, python=platform.python_version(), replay_clock_fps=30,
        source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT / 'src/avl_white_lines').glob('*.py'))},
        configs={name: asdict(c) for name, c in zip(names, configs)}, profiles={},
        empty_to_nonempty=sum(r['empty_to_nonempty'] for r in rows),
        nonempty_to_empty=sum(r['nonempty_to_empty'] for r in rows),
        note='Unlabeled output/CPU review, not accuracy. Nonempty masks can be false positives. Pixel counts across processing sizes are not directly comparable. Nominal replay timestamps; no physical throughput claim. Full-frame filters precede the configured crop. Gallery includes uniform frames and all empty/nonempty transitions; not an unbiased accuracy sample.')
    for name in names:
        times = [r[name]['processing_ms'] for r in rows]
        summary['profiles'][name] = dict(empty_masks=sum(r[name]['candidate_pixels'] == 0 for r in rows),
            frames_with_confirmed_candidates=sum(r[name]['confirmed_candidates'] > 0 for r in rows),
            navigation_eligible_frames=sum(r[name]['navigation_eligible'] for r in rows),
            mean_detector_ms=float(np.mean(times)), p95_detector_ms=float(np.percentile(times, 95)))
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    (args.output / 'frames.jsonl').write_text(''.join(json.dumps(r, allow_nan=False) + '\n' for r in rows), encoding='utf-8')
    html = '<!doctype html><meta charset="utf-8"><title>Recording detail review</title><style>body{background:#171b22;color:#eee;font:16px system-ui;margin:24px}img{max-width:100%}a{color:#9cd5ff}</style><h1>Baseline / detail candidates</h1><p>These are unlabeled inspection outputs, not accuracy scores. Cyan can include non-paint objects. <a href="summary.json">Summary</a> / <a href="frames.jsonl">Per-frame trace</a>.</p>'
    (args.output / 'index.html').write_text(html + ''.join(cards), encoding='utf-8')
    print(json.dumps(summary['profiles'], indent=2), flush=True)


if __name__ == '__main__':
    main()
