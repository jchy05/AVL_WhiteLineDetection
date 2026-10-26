"""Rerun available Git snapshots in isolated processes; never approximate old code."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def snapshot(repo, revision, directory, tree):
    commit = git(repo, 'rev-parse', revision + '^{commit}').decode().strip()
    directory.mkdir(parents=True)
    archive = git(repo, 'archive', '--format=zip', commit, tree)
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        for item in bundle.infolist():
            if not (directory / item.filename).resolve().is_relative_to(directory.resolve()):
                raise ValueError('Unsafe archive path')
        bundle.extractall(directory)
    return commit


def worker(spec_path):
    spec = json.loads(Path(spec_path).read_text(encoding='utf-8'))
    source = Path(spec['source']).resolve()
    sys.path.insert(0, str(source))
    kind = spec['kind']
    cfg = None
    if kind == 'marvin':
        import white_line as module
        from white_line import WhiteLineDetector, PRESETS
        detector = WhiteLineDetector(PRESETS['marvin_front'], proc_width=480, ground_live=False)
    else:
        import avl_white_lines as module
        from avl_white_lines.config import load_config
        from avl_white_lines import detector as detection
        if kind == 'original':
            from avl_white_lines.original_viewer import process
        else:
            cfg = load_config(spec.get('config'))
            detector = detection.Detector(cfg) if hasattr(detection, 'Detector') else None
    if not Path(module.__file__).resolve().is_relative_to(source):
        raise RuntimeError('Imported installed code instead of the requested snapshot')
    output = Path(spec['output'])
    rows = []
    for path_text in spec['images']:
        path = Path(path_text)
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError('Cannot decode ' + str(path))
        h, w = image.shape[:2]
        reference = None
        if kind == 'original':
            stages, overlay, stats = process(image, spec['mode'], False)
            mask = np.any(stages[16] != 0, axis=2)
            ref = ROOT / 'examples/generated' / path.stem / ('article_hsl_white', 'previous_hsv', 'saved_hsl')[spec['mode']] / 'final.png'
            if ref.exists():
                reference = bool(np.array_equal(overlay, cv2.imread(str(ref))))
                if not reference:
                    raise RuntimeError('Original saved-reference mismatch: ' + path.name)
            processing_size = [w, h]
        else:
            if kind == 'marvin':
                mask = detector.detect(image)
                processing_size = [480, round(h * 480 / w)]
            else:
                result = detector.detect(image, debug=True) if detector else detection.detect(image, cfg, debug=True)
                processing_size = [result.original.shape[1], result.original.shape[0]]
                if kind == 'hough':
                    mask = np.any(result.stages['Fitted line mask'] != 0, axis=2)
                else:
                    mask = result.mask > 0
                mask = cv2.resize(mask.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST) > 0
            overlay = image.copy()
            overlay[mask] = (255, 255, 0)
        frame_dir = output / 'images' / path.stem
        frame_dir.mkdir(parents=True, exist_ok=True)
        # Lossless results, plus smaller JPEGs for contact sheets/browser previews.
        cv2.imwrite(str(frame_dir / (spec['id'] + '_overlay.png')), overlay)
        cv2.imwrite(str(frame_dir / (spec['id'] + '_mask.png')), mask.astype(np.uint8) * 255)
        rows.append(dict(frame=path.stem, image_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            mask_pixels_native=int(np.count_nonzero(mask)), processing_size=processing_size,
            original_reference_pixel_identical=reference))
    from dataclasses import asdict
    report = dict(id=spec['id'], title=spec['title'], commit=spec['commit'], kind=kind,
        config=asdict(cfg) if cfg else None, mode=spec.get('mode'),
        source_sha256={p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.rglob('*')) if p.is_file() and p.suffix in ('.py', '.json')},
        frames=rows, opencv=cv2.__version__, numpy=np.__version__, python=sys.version)
    (output / (spec['id'] + '_provenance.json')).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


def tile(picture, title, subtitle, width=480):
    h, w = picture.shape[:2]
    image = cv2.resize(picture, (width, round(h * width / w)), interpolation=cv2.INTER_AREA)
    panel = np.full((image.shape[0] + 54, width, 3), 25, np.uint8)
    panel[54:] = image
    cv2.putText(panel, title, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, .53, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(panel, subtitle, (8, 43), cv2.FONT_HERSHEY_SIMPLEX, .39, (180, 195, 210), 1, cv2.LINE_AA)
    return panel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--images', type=Path, default=ROOT / 'examples/raw')
    parser.add_argument('--frames', default='0,410,474,710,1077')
    parser.add_argument('--marvin-repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new output directory to preserve existing results')
    indices = list(dict.fromkeys(int(i) for i in args.frames.split(',')))
    images = [(args.images / f'frame_{i:06}.jpg').resolve() for i in indices]
    if not all(path.is_file() for path in images):
        parser.error('A requested raw image is unavailable; no substitutes will be made')
    out = args.output.resolve()
    out.mkdir(parents=True)
    specs = []
    unavailable = []
    definitions = [
        ('original_article', 'Original AVL / Article HSL', 'e23345a', 'original', None, 0),
        ('original_hsv', 'Original AVL / Previous HSV', 'e23345a', 'original', None, 1),
        ('original_saved_hsl', 'Original AVL / Saved HSL', 'e23345a', 'original', None, 2),
        ('early_hough', 'Early tracked AVL / Hough', 'e23345a', 'hough', None, None),
        ('marvin', 'Standalone Marvin', 'HEAD', 'marvin', None, None),
        ('initial_ridge', 'Initial AVL ridge integration', '8fb2b5e', 'ridge', 'config/marvin_ridge.json', None),
        ('corrected_ridge', 'Corrected full-frame AVL ridge', 'ea94083', 'ridge', 'config/marvin_ridge.json', None),
        ('review_480', 'Current AVL / road crop 480', '67b53a9', 'ridge', 'config/recording_review.json', None),
        ('detail_960', 'Newest AVL / detail 960', '67b53a9', 'ridge', 'config/recording_detail.json', None),
    ]
    # Git archives are immutable source copies, not checkout changes. Each worker
    # starts a fresh Python process so versions cannot share imported modules.
    snapshots = {}
    for identity, title, revision, kind, config_path, mode in definitions:
        repo = args.marvin_repo.resolve() if kind == 'marvin' else ROOT
        tree = 'white_line' if kind == 'marvin' else 'src'
        key = (str(repo), revision)
        try:
            if key not in snapshots:
                directory = out / 'sources' / ('marvin' if kind == 'marvin' else revision)
                commit = snapshot(repo, revision, directory, tree)
                snapshots[key] = (directory, commit)
            directory, commit = snapshots[key]
            spec = dict(id=identity, title=title, kind=kind, commit=commit, mode=mode,
                source=str(directory if kind == 'marvin' else directory / 'src'),
                output=str(out), images=[str(p) for p in images])
            if config_path:
                config_file = out / 'sources' / (identity + '.json')
                config_file.write_bytes(git(repo, 'show', commit + ':' + config_path))
                spec['config'] = str(config_file)
            spec_file = out / (identity + '_run.json')
            spec_file.write_text(json.dumps(spec, indent=2), encoding='utf-8')
            subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker', str(spec_file)], check=True)
            specs.append(spec)
            print('Reproduced ' + title + ' @ ' + commit[:7], flush=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as error:
            unavailable.append(dict(id=identity, title=title, reason=str(error)))
            print('UNAVAILABLE; omitted: ' + title, flush=True)
    if not specs:
        raise RuntimeError('No version could be reproduced')
    frame_info = []
    for path in images:
        raw = cv2.imread(str(path))
        frame_dir = out / 'images' / path.stem
        shutil.copyfile(path, frame_dir / 'raw.jpg')
        for view in ('overlay', 'mask'):
            panels = [tile(raw, 'Raw / ' + path.stem, 'Unmodified source JPEG')]
            for spec in specs:
                picture = cv2.imread(str(frame_dir / (spec['id'] + '_' + view + '.png')))
                panels.append(tile(picture, spec['title'], spec['commit'][:7] + (' / fitted line raster' if spec['kind'] in ('original', 'hough') else ' / ridge segmentation')))
            while len(panels) % 3:
                panels.append(np.zeros_like(panels[0]))
            sheet = np.vstack([np.hstack(panels[i:i + 3]) for i in range(0, len(panels), 3)])
            cv2.imwrite(str(out / (path.stem + '_' + view + '_all.jpg')), sheet, [cv2.IMWRITE_JPEG_QUALITY, 95])
        newest = next((s for s in specs if s['id'] == 'detail_960'), None)
        if newest:
            overlay = cv2.imread(str(frame_dir / 'detail_960_overlay.png'))
            pair = np.hstack([tile(raw, 'Raw / ' + path.stem, 'Unmodified source JPEG', 640), tile(overlay, 'Newest AVL / detail 960', newest['commit'][:7] + ' / single-frame candidates', 640)])
            cv2.imwrite(str(out / (path.stem + '_raw_latest.jpg')), pair, [cv2.IMWRITE_JPEG_QUALITY, 95])
        frame_info.append(dict(id=path.stem, image_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    manifest = dict(versions=[{k: s[k] for k in ('id', 'title', 'commit', 'kind')} for s in specs],
        unavailable=unavailable, frames=frame_info,
        note='Actual code reruns from archived Git commits, current Python/OpenCV. Not historical screenshots or original execution environments. No depth, live ground fitting or temporal tracking. All ridge profiles assume marvin_front, unverified for this footage. Original outputs preserve original rendering; other overlays use cyan to display actual detected segmentation or fitted-line raster. Fits are not semantic masks. No reviewed accuracy scores or ranking. No separate version is invented for documentation-only commits.')
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    template = Path(__file__).with_name('version_gallery.html').read_text(encoding='utf-8')
    (out / 'index.html').write_text(template.replace('/*MANIFEST*/{}', json.dumps(manifest).replace('<', '\\u003c')), encoding='utf-8')
    print(f'Gallery: {out / "index.html"}; {len(specs)} real configurations, {len(images)} raw frames.', flush=True)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
    else:
        main()
