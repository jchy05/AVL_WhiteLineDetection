import hashlib
import json
from pathlib import Path
import cv2

ROOT=Path(__file__).resolve().parents[1]/'examples'

def test_exact_requested_raw_images_and_hashes():
    manifest=json.loads((ROOT/'manifest.json').read_text())
    assert [frame['frame'] for frame in manifest['frames']]==[0,410,474,710,1077]
    assert len(list((ROOT/'raw').glob('*.jpg')))==5
    for frame in manifest['frames']:
        raw=ROOT/frame['raw']
        assert hashlib.sha256(raw.read_bytes()).hexdigest()==frame['sha256']
        assert cv2.imread(str(raw)).shape==(720,1280,3)

def test_all_result_links_and_stage_previews_exist():
    manifest=json.loads((ROOT/'manifest.json').read_text())
    assert len(manifest['stage_names'])==17
    for frame in manifest['frames']:
        assert (ROOT/frame['comparison']).is_file()
        assert [m['key'] for m in frame['modes']]==['article_hsl_white','previous_hsv','saved_hsl']
        for mode in frame['modes']:
            assert cv2.imread(str(ROOT/mode['final'])).shape==(720,1280,3)
            assert len(mode['stages'])==17
            assert all((ROOT/path).is_file() for path in mode['stages'])

def test_offline_gallery_manifest_matches_json():
    js=(ROOT/'manifest.js').read_text(encoding='utf-8')
    data=json.loads(js.removeprefix('const EXAMPLES = ').strip().removesuffix(';'))
    assert data==json.loads((ROOT/'manifest.json').read_text())
