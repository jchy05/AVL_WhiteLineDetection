"""Export raw image / actual ridge mask / candidate overlay, without invented tracks."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import shutil
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from avl_white_lines.config import load_config
from avl_white_lines.detector import Detector


def panel(image, title):
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    shown = cv2.resize(image, (560, round(image.shape[0] * 560 / image.shape[1])), interpolation=cv2.INTER_NEAREST)
    result = np.full((shown.shape[0] + 36, 560, 3), 24, np.uint8)
    result[36:] = shown
    cv2.putText(result, title, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, .55, (255, 255, 255), 1, cv2.LINE_AA)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--images', type=Path, default=ROOT / 'examples/raw')
    parser.add_argument('--config', type=Path, default=ROOT / 'config/recording_detail.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new output directory to preserve existing work')
    files = sorted(p for p in args.images.iterdir() if p.suffix.lower() in ('.jpg', '.jpeg', '.png'))
    if not files:
        parser.error('No images found')
    cfg = load_config(args.config)
    if cfg.backend != 'marvin_ridge':
        parser.error('This view requires a marvin_ridge profile with a segmentation mask')
    args.output.mkdir(parents=True)
    detector = Detector(cfg)
    records = []
    sheets = []
    for index, file in enumerate(files):
        raw = cv2.imread(str(file))
        if raw is None:
            raise ValueError('Cannot decode ' + str(file))
        result = detector.detect(raw)
        h, w = raw.shape[:2]
        # Preserve binary values when mapping the true processing mask back to
        # source coordinates; no fitting, interpolation blur or temporal replay.
        mask = cv2.resize(result.mask, (w, h), interpolation=cv2.INTER_NEAREST)
        overlay = raw.copy()
        overlay[mask > 0] = (255, 255, 0)
        folder = args.output / f'{index:03d}_{file.stem}'
        folder.mkdir()
        shutil.copyfile(file, folder / ('raw' + file.suffix.lower()))
        cv2.imwrite(str(folder / 'original.png'), raw)
        cv2.imwrite(str(folder / 'processing_mask.png'), result.mask)
        cv2.imwrite(str(folder / 'mask.png'), mask)
        cv2.imwrite(str(folder / 'overlay.png'), overlay)
        sheet = np.hstack([panel(raw, 'Original / ' + file.stem), panel(mask, 'Final candidate mask'), panel(overlay, 'Current ridge / candidate overlay')])
        cv2.imwrite(str(folder / 'three_panel.png'), sheet)
        sheets.append(sheet)
        records.append(dict(image=file.name, folder=folder.name, image_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
            processing_size=[result.original.shape[1], result.original.shape[0]],
            mask_sha256=hashlib.sha256(result.mask.tobytes()).hexdigest(), diagnostics=result.diagnostics))
    cv2.imwrite(str(args.output / 'all_frames.png'), np.vstack(sheets))
    metadata = dict(config=asdict(cfg), opencv=cv2.__version__, frames=records,
        source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT / 'src/avl_white_lines').glob('*.py'))},
        note='Actual per-image ridge segmentation. Cyan marks candidate pixels; no temporal tracking, synthetic confirmation, depth or accuracy labels. Native mask uses nearest-neighbor resizing of the saved processing mask. The copied source file and original.png preserve the original image/file and decoded pixels respectively.')
    (args.output / 'metadata.json').write_text(json.dumps(metadata, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    html = '''<!doctype html><meta charset="utf-8"><title>Original / mask / overlay</title>
<style>body{background:#151b24;color:#eee;font:16px system-ui;margin:24px}button,select{font:inherit;padding:8px}img{max-width:100%;display:block;margin:20px 0}a{color:#9cd5ff}</style>
<h1>Original / final mask / overlay</h1><p>Current detailed ridge pipeline. Cyan is detected candidate evidence, without temporal tracking. White mask pixels are candidates; black pixels are rejected.</p>
<button id="prev">A / ← Previous</button> <select id="frame" aria-label="Frame"></select> <button id="next">D / → Next</button>
<img id="result" alt="Original image, actual binary mask and candidate overlay"><p id="links"></p><p><a href="metadata.json">Settings, hashes and diagnostics</a> · <a href="all_frames.png">All frames</a></p>
<script>const frames=FRAMES;let index=0;const sel=document.getElementById('frame');for(const f of frames)sel.add(new Option(f.image,f.folder));
function paint(){const f=frames[index];sel.selectedIndex=index;document.getElementById('result').src=f.folder+'/three_panel.png';const p=document.getElementById('links');p.replaceChildren();for(const name of ['original','mask','overlay']){const a=document.createElement('a');a.href=f.folder+'/'+name+'.png';a.textContent=name+' (full resolution)';a.style.marginRight='20px';p.append(a);}}
function move(d){index=(index+d+frames.length)%frames.length;paint();}document.getElementById('prev').onclick=()=>move(-1);document.getElementById('next').onclick=()=>move(1);sel.onchange=()=>{index=sel.selectedIndex;paint();};document.addEventListener('keydown',e=>{if(e.target.tagName==='SELECT'||e.ctrlKey||e.metaKey||e.altKey)return;const k=e.key.toLowerCase();if(['a','d','arrowleft','arrowright'].includes(k))e.preventDefault();if(k==='a'||k==='arrowleft')move(-1);if(k==='d'||k==='arrowright')move(1);});paint();</script>'''
    (args.output / 'index.html').write_text(html.replace('FRAMES', json.dumps(records).replace('<', '\\u003c')), encoding='utf-8')
    print(f'Exported {len(records)} frames to {args.output / "index.html"}')


if __name__ == '__main__':
    main()
