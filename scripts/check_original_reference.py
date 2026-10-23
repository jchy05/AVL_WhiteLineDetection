"""Verify original final images without modifying source or reference assets."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from avl_white_lines.original_viewer import process

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--report',type=Path); p.add_argument('--strict-bytes',action='store_true'); args=p.parse_args()
    rows=[]
    for number in (0,410,474,710,1077):
        stem=f'frame_{number:06}'; image=cv2.imread(str(ROOT/'examples/raw'/(stem+'.jpg')))
        for mode,name in enumerate(('article_hsl_white','previous_hsv','saved_hsl')):
            _,final,_=process(image,mode,False)
            reference=ROOT/'examples/generated'/stem/name/'final.png'
            ok,encoded=cv2.imencode('.png',final)
            rows.append({'frame':number,'mode':name,'pixel_identical':bool(np.array_equal(final,cv2.imread(str(reference)))),
                         'byte_identical':bool(ok and encoded.tobytes()==reference.read_bytes()),
                         'reference_sha256':hashlib.sha256(reference.read_bytes()).hexdigest()})
    report={'opencv':cv2.__version__,'cases':rows,'all_pixels_identical':all(r['pixel_identical'] for r in rows),
            'all_bytes_identical':all(r['byte_identical'] for r in rows)}
    if args.report:
        args.report.parent.mkdir(exist_ok=True,parents=True); args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(f"Original: 15 cases; pixels identical={report['all_pixels_identical']}; PNG bytes identical={report['all_bytes_identical']}")
    if not report['all_pixels_identical'] or (args.strict_bytes and not report['all_bytes_identical']): raise SystemExit(1)

if __name__=='__main__': main()
