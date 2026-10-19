"""Generate comparisons from the five checked-in raw frames, using the original detector."""
from pathlib import Path
import hashlib
import json
import sys
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from avl_white_lines import original_viewer as viewer

FRAMES=(0,410,474,710,1077)
MODES=('article_hsl_white','previous_hsv','saved_hsl')

def labeled(image,text,width=640):
    image=cv2.resize(image,(width,round(image.shape[0]*width/image.shape[1])))
    top=np.full((35,width,3),20,np.uint8)
    cv2.putText(top,text,(10,24),cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),1,cv2.LINE_AA)
    return np.vstack([top,image])

def main():
    examples=ROOT/'examples'; generated=examples/'generated'; generated.mkdir(exist_ok=True,parents=True)
    entries=[]
    for number in FRAMES:
        stem=f'frame_{number:06}'
        raw=examples/'raw'/(stem+'.jpg')
        image=cv2.imread(str(raw))
        if image is None: raise RuntimeError(f'Missing raw image: {raw}')
        folder=generated/stem; folder.mkdir(exist_ok=True)
        item={'frame':number,'raw':raw.relative_to(examples).as_posix(),
              'sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),
              'size':[image.shape[1],image.shape[0]],'modes':[]}
        panels=[labeled(image,f'{number} / Original raw image')]
        for mode,key in enumerate(MODES):
            stages,final,info=viewer.process(image,mode,False)
            output=folder/key; output.mkdir(exist_ok=True)
            cv2.imwrite(str(output/'final.png'),final)
            panels.append(labeled(final,f'{number} / {viewer.MODES[mode]}'))
            paths=[]
            for idx,stage in enumerate(stages):
                if idx==0:
                    paths.append(raw.relative_to(examples).as_posix()); continue
                # Color channels and the three comparison masks are mode-independent.
                dest=folder/f'stage_{idx+1:02}.png' if idx<8 else output/f'stage_{idx+1:02}.png'
                if idx>=8 or mode==0:
                    height=round(stage.shape[0]*640/stage.shape[1])
                    resized=cv2.resize(stage,(640,height),interpolation=cv2.INTER_NEAREST if stage.ndim==2 else cv2.INTER_AREA)
                    cv2.imwrite(str(dest),resized)
                paths.append(dest.relative_to(examples).as_posix())
            item['modes'].append({'key':key,'title':viewer.MODES[mode],
                                  'final':(output/'final.png').relative_to(examples).as_posix(),
                                  'stages':paths,'details':info})
        montage=np.vstack([np.hstack(panels[:2]),np.hstack(panels[2:])])
        cv2.imwrite(str(folder/'comparison.jpg'),montage,[cv2.IMWRITE_JPEG_QUALITY,92])
        item['comparison']=(folder/'comparison.jpg').relative_to(examples).as_posix()
        entries.append(item)
    manifest={'pipeline':'original viewer, native input resolution, no tracking',
              'roi':'Rectangle begins 2/5 down from top (bottom 60%)',
              'opencv':cv2.__version__,
              'detector_sha256':hashlib.sha256(Path(viewer.__file__).read_bytes()).hexdigest(),
              'stage_preview_width':640,'stage_names':[x[0] for x in viewer.STAGES],
              'stage_descriptions':[x[1] for x in viewer.STAGES], 'frames':entries}
    (examples/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    (examples/'manifest.js').write_text('const EXAMPLES = '+json.dumps(manifest)+';\n',encoding='utf-8')
    lines=['# Five original raw frames and their results','',
           'These are the actual raw JPEGs from the earlier projects, copied without recompression. Only these five raw frames are included; the full 1,078-frame set is not uploaded.','',
           'Results use the **restored original detector**, all three filters, native 1280×720 input, and the rectangular ROI starting 40% down from the top. There is no tracking or input resizing.','',
           'Download the repo/ZIP and open **gallery.html** here for I/O stage switching, A/D image switching, and M filter switching. It runs offline. GitHub shows the static comparisons below. Stage previews are resized to 640 pixels wide after detection; final PNGs remain full resolution.','',
           'In each grid: **original** (top left), **Article HSL white** (top right), **Previous HSV defaults** (bottom left), **Saved HSL** (bottom right). Results are shown as generated, including misses or incorrect fits.','']
    for item in entries:
        lines.extend([f"## Frame {item['frame']}",'',f"![Frame {item['frame']} comparison]({item['comparison']})",'',
                      f"[Raw JPEG]({item['raw']}) · "+' · '.join(f"[{m['title']} final]({m['final']})" for m in item['modes']),''])
    lines.extend(['## Reproduce','', 'From the repository root:','', '```bash','python scripts/generate_examples.py','python lane_pipeline_viewer.py examples/raw','```','',
                  'Raw-file SHA-256 hashes and detector/runtime metadata are recorded in manifest.json. These are visual examples, not labeled accuracy measurements.'])
    (examples/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Generated five comparisons, fifteen full-resolution finals, and all seventeen preview stages for each mode.')

if __name__=='__main__': main()
