"""Inspect every lane-processing stage beside its final result. Run with Python."""
from __future__ import annotations
import argparse
import json
from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np

WINDOW = "MARVIN - lane pipeline | I/O masks | A/D images"
MODES = ["Article HSL white", "Previous HSV defaults", "Saved HSL"]
STAGES = [
    ("Original", "Unmodified raw frame."),
    ("HSV saturation", "HSV saturation channel: white paint usually has low saturation."),
    ("HSV value", "HSV value channel: brightness."),
    ("HSL lightness", "OpenCV calls HSL HLS: channels are H, L, S."),
    ("HSL saturation", "HSL saturation channel."),
    ("Article white mask", "From the article notebook: HSL lightness 200..255; any hue or saturation."),
    ("Previous HSV mask", "HSV H=0..180, S=0..30, V=195..255; previous tester defaults."),
    ("Saved HSL mask", "Saved HSL settings: H=0..36, L=59..205, S=0..40."),
    ("Active color mask", "A copy of the Article white, Previous HSV, or Saved HSL mask selected by M."),
    ("Filtered original", "Original colors kept where the active mask is white; all other pixels become black."),
    ("Grayscale", "Filtered BGR image converted to grayscale."),
    ("Gaussian blur", "11 x 11 Gaussian smoothing, as in the article."),
    ("Canny edges", "Canny low=50, high=150, as in the linked article."),
    ("ROI edges", "Canny edges AND region mask; input to Hough transform."),
    ("Raw Hough segments", "All Hough segments, including rejected candidates."),
    ("Accepted segments", "Reject flat segments; group by position; keep the strongest aligned set with enough foreground support."),
    ("Fitted line mask", "Least-squares straight estimates; inferred extensions are not paint pixels."),
]

def in_range(img, lo, hi):
    return cv2.inRange(img, np.array(lo, np.uint8), np.array(hi, np.uint8))

def consistent_segments(segments, width):
    """Choose the length-supported line consensus, rather than averaging markings."""
    if not segments:
        return []
    seg = np.asarray(segments,dtype=float)
    lengths = np.hypot(seg[:,2]-seg[:,0],seg[:,3]-seg[:,1])
    best = None
    best_score = -1
    for x1,y1,x2,y2 in seg:
        a = (x2-x1)/(y2-y1)
        b = x1-a*y1
        # Both endpoints must be close to the candidate infinite line.
        residual = np.maximum(np.abs(seg[:,0]-a*seg[:,1]-b),np.abs(seg[:,2]-a*seg[:,3]-b))/np.sqrt(1+a*a)
        keep = residual <= max(5,width*.008)
        score = float(lengths[keep].sum())
        if score > best_score:
            best_score,best = score,keep
    return seg[best].astype(int).tolist()

def process(img, mode=0, article_roi=False):
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hls = cv2.cvtColor(img, cv2.COLOR_BGR2HLS)
    white = in_range(hls, [0,200,0], [180,255,255])
    old_hsv = in_range(hsv, [0,0,195], [180,30,255])
    saved_hsl = in_range(hls, [0,59,0], [36,205,40])
    active = [white, old_hsv, saved_hsl][mode]
    filtered = cv2.bitwise_and(img, img, mask=active)
    gray = cv2.cvtColor(filtered, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (11,11), 0)
    edges = cv2.Canny(blur, 50, 150)
    roi = np.zeros((h,w), np.uint8)
    # Scale the notebook's 960x540 trapezoid, avoiding its resolution-specific bug.
    points = (np.array([[130/960,1], [410/960,330/540], [650/960,350/540], [930/960,1]]) * [w-1,h-1]).astype(np.int32) if article_roi else np.array([[0,int(.4*h)],[w-1,int(.4*h)],[w-1,h-1],[0,h-1]],np.int32)
    cv2.fillPoly(roi, [points], 255)
    cropped = edges & roi
    lines = cv2.HoughLinesP(cropped, 1, np.pi/180, 15, minLineLength=20, maxLineGap=10)
    raw = np.zeros_like(img); accepted = raw.copy(); fits = raw.copy()
    groups = [[] for _ in range(2 if article_roi else 3)]
    candidates = [[] for _ in groups]
    colors = [(255,110,40),(60,230,80),(70,100,255)]
    counts = [0]*len(groups)
    if lines is not None:
        for x1,y1,x2,y2 in lines[:,0]:
            cv2.line(raw,(x1,y1),(x2,y2),(210,210,210),2,cv2.LINE_AA)
            dx,dy = float(x2-x1),float(y2-y1)
            if abs(dy) < 8 or abs(dx/dy) > 3.5: continue
            xb = x1 + (h-1-y1)*dx/dy
            if article_roi:
                if dx == 0: continue
                slope = dy/dx
                if slope < -.3 and (x1+x2)/2 < .6*w: group = 0
                elif slope > .3 and (x1+x2)/2 > .4*w: group = 1
                else: continue
            else:
                if not -.5*w < xb < 1.5*w: continue
                group = 0 if xb < .3*w else (1 if xb < .75*w else 2)
            candidates[group].append((x1,y1,x2,y2))
    for k,segments in enumerate(candidates):
        coherent = consistent_segments(segments,w)
        if coherent:
            ys = np.asarray(coherent)[:,[1,3]]
            # Short bright objects above the foreground are weak lane evidence.
            if np.ptp(ys) < .08*h or ys.max() < .7*h:
                coherent = []
        for x1,y1,x2,y2 in coherent:
            groups[k].extend([(x1,y1),(x2,y2)])
            counts[k] += 1
            cv2.line(accepted,(x1,y1),(x2,y2),colors[k],3,cv2.LINE_AA)
    for k, pts in enumerate(groups):
        if len(pts) < 4: continue
        pts = np.array(pts, dtype=float)
        if np.ptp(pts[:,1]) < 15: continue
        # Fit x(y), handling vertical lines without dividing by dx.
        a,b = np.polyfit(pts[:,1],pts[:,0],1)
        # A raised ROI may include sky: do not extrapolate upward beyond evidence.
        y0,y1 = max(int(points[:,1].min()),int(pts[:,1].min())),h-1
        p0,p1 = (int(np.clip(a*y0+b,-2*w,3*w)),y0),(int(np.clip(a*y1+b,-2*w,3*w)),y1)
        cv2.line(fits,p0,p1,colors[k],6,cv2.LINE_AA)
    fits = cv2.bitwise_and(fits,fits,mask=roi)
    final = img.copy()
    visible = np.any(accepted > 0,axis=2)
    final[visible] = accepted[visible]
    visible = np.any(fits > 0,axis=2)
    final[visible] = (final[visible]*.2 + fits[visible]*.8).astype(np.uint8)
    cv2.polylines(final,[points],True,(0,220,255),1,cv2.LINE_AA)
    stages = [img,hsv[:,:,1],hsv[:,:,2],hls[:,:,1],hls[:,:,2],white,old_hsv,saved_hsl,active,filtered,gray,blur,edges,cropped,raw,accepted,fits]
    return stages, final, {"segments":int(0 if lines is None else len(lines)),"accepted_by_group":counts,"fitted_groups":int(sum(len(p)>=4 and np.ptp(np.array(p)[:,1])>=15 for p in groups))}

def panel(img, title, size=(620,370)):
    if img.ndim == 2: img = cv2.cvtColor(img,cv2.COLOR_GRAY2BGR)
    w,h = size; canvas = np.full((h,w,3),20,np.uint8)
    scale = min(w/img.shape[1],(h-38)/img.shape[0])
    nw,nh = max(1,int(img.shape[1]*scale)),max(1,int(img.shape[0]*scale))
    x,y = (w-nw)//2,38+(h-38-nh)//2
    canvas[y:y+nh,x:x+nw] = cv2.resize(img,(nw,nh),interpolation=cv2.INTER_AREA)
    cv2.putText(canvas,title,(12,25),cv2.FONT_HERSHEY_SIMPLEX,.58,(240,240,240),1,cv2.LINE_AA)
    return canvas

@dataclass
class State:
    index: int = 0
    stage: int = 8
    mode: int = 0
    article_roi: bool = False
    def key(self,key,n):
        if key in (ord('i'),ord('I')): self.stage = (self.stage-1)%len(STAGES)
        elif key in (ord('o'),ord('O')): self.stage = (self.stage+1)%len(STAGES)
        elif key in (ord('a'),ord('A'),2424832,65361): self.index = (self.index-1)%n
        elif key in (ord('d'),ord('D'),2555904,65363): self.index = (self.index+1)%n
        elif key in (ord('m'),ord('M')): self.mode = (self.mode+1)%len(MODES)
        elif key in (ord('r'),ord('R')): self.article_roi = not self.article_roi
        elif key in (ord('q'),ord('Q'),27): return False
        return True

def compose(img, stages, final, info, state, name, n):
    top = np.hstack([panel(img,"RAW / "+name),panel(stages[state.stage],f"{state.stage+1:02}/{len(STAGES)} / "+STAGES[state.stage][0]),panel(final,"FINAL / "+MODES[state.mode])])
    footer = np.full((125,top.shape[1],3),24,np.uint8)
    roi = "ARTICLE trapezoid / two lane fits" if state.article_roi else "MARVIN boundary 2/5 from top / bottom 60%"
    description = STAGES[state.stage][1]
    if STAGES[state.stage][0] == "Active color mask":
        description = f"Source: {MODES[state.mode]} mask. M changes this selection; it feeds all following stages."
    texts = [f"Image {state.index+1}/{n}   |   I / O: previous / next mask   A / D or arrows: image   M: pipeline   R: ROI   S: save   Q: quit",
             description,f"ROI: {roi}  |  Hough: {info['segments']}  |  accepted: {info['accepted_by_group']}  |  fits: {info['fitted_groups']}",
             "Final always follows the active pipeline. Viewing another stage does not change it. Colored extensions are straight estimates."]
    for j,t in enumerate(texts): cv2.putText(footer,t,(12,24+j*27),cv2.FONT_HERSHEY_SIMPLEX,.56,(220,220,220),1,cv2.LINE_AA)
    return np.vstack([top,footer])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image_folder",nargs="?",type=Path,help="Original raw-image folder; opens a folder picker when omitted")
    parser.add_argument("--export",action="store_true",help="Export a preview and all stages of the first image without a GUI")
    parser.add_argument("--output-dir",type=Path,default=Path.cwd()/'results'/'original',help="Folder for exports and saved images")
    args = parser.parse_args()
    if args.image_folder is None:
        if args.export: parser.error("Provide an image folder when using --export")
        try:
            import tkinter as tk
            from tkinter.filedialog import askdirectory
            root=tk.Tk(); root.withdraw()
            try: selected=askdirectory(title='Choose the original raw-image folder',parent=root)
            finally: root.destroy()
        except Exception as exc:
            parser.error(f"Cannot open folder picker ({exc}). Pass the image folder as an argument.")
        if not selected: return
        args.image_folder=Path(selected)
    files = sorted(p for p in args.image_folder.rglob('*') if p.suffix.lower() in {'.jpg','.jpeg','.png','.bmp','.tif','.tiff','.webp'}) if args.image_folder.is_dir() else []
    if not files: raise SystemExit(f"No images in {args.image_folder}. Supply your image folder as an argument.")
    state = State(); cache = None; displayed = None
    if not args.export:
        cv2.namedWindow(WINDOW,cv2.WINDOW_NORMAL); cv2.resizeWindow(WINDOW,1600,470)
    while True:
        signature = (state.index,state.mode,state.article_roi)
        if signature != cache:
            img = cv2.imread(str(files[state.index]))
            if img is None: raise SystemExit(f"Cannot read {files[state.index]}")
            stages,final,info = process(img,state.mode,state.article_roi); cache = signature
        display_signature = (*signature,state.stage)
        if display_signature != displayed:
            view = compose(img,stages,final,info,state,files[state.index].name,len(files))
        if args.export:
            out = args.output_dir/'preview'; out.mkdir(parents=True,exist_ok=True)
            cv2.imwrite(str(out/'viewer.jpg'),view)
            for j,(title,_) in enumerate(STAGES): cv2.imwrite(str(out/f'{j+1:02}_{title.replace(" ","_")}.png'),stages[j])
            cv2.imwrite(str(out/'final.png'),final)
            (out/'details.json').write_text(json.dumps(info,indent=2))
            print(f"Exported {len(stages)} stages to {out}; {len(files)} raw images available.")
            break
        # Pump events on every iteration, repaint only after an actual change.
        if display_signature != displayed:
            cv2.imshow(WINDOW,view)
            displayed = display_signature
        key = cv2.waitKeyEx(40)
        if cv2.getWindowProperty(WINDOW,cv2.WND_PROP_VISIBLE)<1: break
        if key in (ord('s'),ord('S')):
            out = args.output_dir/'saved'; out.mkdir(parents=True,exist_ok=True)
            stem = f'{files[state.index].stem}_mode{state.mode}_stage{state.stage+1}_roi{int(state.article_roi)}'
            cv2.imwrite(str(out/(stem+'_view.jpg')),view)
            cv2.imwrite(str(out/(stem+'_stage.png')),stages[state.stage])
            cv2.imwrite(str(out/(stem+'_final.png')),final)
            print(f'Saved {stem} to {out}')
        if not state.key(key,len(files)): break
    if not args.export: cv2.destroyAllWindows()

if __name__ == '__main__': main()
