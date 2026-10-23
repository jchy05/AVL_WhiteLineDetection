"""Deterministic per-frame pipeline; no fixed left/center/right bins."""
from dataclasses import dataclass, field
import time
import cv2
import numpy as np
from .config import Config

STAGES = ("Original", "HSV saturation", "HSV value", "HSL lightness", "HSL saturation",
          "Article white mask", "Previous HSV mask", "Saved HSL mask", "Active color mask",
          "Filtered original", "Grayscale", "Gaussian blur", "Canny edges", "ROI edges",
          "Raw Hough segments", "Accepted segments", "Fitted line mask")

@dataclass
class Observation:
    # x_normalized = a*y_normalized + b; independent of input resolution.
    a: float
    b: float
    y_min: float
    y_max: float
    confidence: float
    support: int

    backend: str = "legacy_hough"
    centerline_ground: list = field(default_factory=list)
    centerline_image: list = field(default_factory=list)
    length_m: float = 0.0
    width_m: float = 0.0
    heading_rad: float = 0.0
    depth_confirmed: bool = False

    def x(self,y): return self.a*y+self.b

@dataclass
class FrameResult:
    original: np.ndarray
    observations: list
    stages: dict
    roi: np.ndarray
    processing_ms: float
    raw_segments: int
    mask: np.ndarray | None = None
    backend: str = "legacy_hough"
    ground_estimate: dict = field(default_factory=dict)

def extract_observations(segments, width, height, cfg):
    """Repeated consensus finds separate line hypotheses before temporal association."""
    if segments is None: return [], []
    seg = np.asarray(segments,dtype=float).reshape(-1,4)
    dx,dy = seg[:,2]-seg[:,0],seg[:,3]-seg[:,1]
    good = (np.abs(dy)>=max(5,.01*height)) & (np.abs(dx)<=3.5*np.abs(dy))
    seg = seg[good]
    if len(seg)==0: return [], []
    length = np.hypot(seg[:,2]-seg[:,0],seg[:,3]-seg[:,1])
    # Bound consensus cost even on noisy scenes. Stable sort makes tie handling repeatable.
    order = np.argsort(-length,kind="stable")[:cfg.max_candidates]
    seg,length = seg[order],length[order]
    observations, accepted = [], []
    while len(seg)>=2 and len(observations)<cfg.max_lines:
        slopes = (seg[:,2]-seg[:,0])/(seg[:,3]-seg[:,1])
        offsets = seg[:,0]-slopes*seg[:,1]
        r1 = np.abs(seg[None,:,0]-slopes[:,None]*seg[None,:,1]-offsets[:,None])
        r2 = np.abs(seg[None,:,2]-slopes[:,None]*seg[None,:,3]-offsets[:,None])
        residual = np.maximum(r1,r2)/np.sqrt(1+slopes[:,None]**2)
        votes = residual<=max(4,width*cfg.consensus_distance)
        score = votes@length
        best = None
        for idx in np.argsort(-score,kind="stable"):
            pts = seg[votes[idx]].reshape(-1,2)
            if len(pts)>=4 and np.ptp(pts[:,1])>=cfg.min_vertical_span*height and pts[:,1].max()>=cfg.foreground_y*height:
                best = idx; break
        if best is None: break
        selected = votes[best]
        supporting = seg[selected]
        pts = supporting.reshape(-1,2)/[width-1,height-1]
        # Length-weight endpoints; many tiny noisy segments cannot dominate long paint edges.
        weights = np.repeat(np.sqrt(length[selected]),2)
        a,b = np.polyfit(pts[:,1],pts[:,0],1,w=weights)
        residual_fit = np.abs(pts[:,0]-(a*pts[:,1]+b))/np.sqrt(1+a*a)
        coverage = float(np.ptp(pts[:,1]))
        support_length = float(length[selected].sum()/height)
        confidence = float(np.clip(min(1,coverage/.35)*min(1,support_length/.7)*np.exp(-np.median(residual_fit)/.01),0,1))
        observations.append(Observation(float(a),float(b),float(pts[:,1].min()),float(pts[:,1].max()),confidence,int(selected.sum())))
        accepted.append(supporting.astype(int))
        seg,length = seg[~selected],length[~selected]
    return observations,accepted

def legacy_detect(frame, cfg: Config, debug=False):
    started = time.perf_counter()
    if frame is None or frame.ndim!=3 or frame.shape[2]!=3 or frame.dtype!=np.uint8:
        raise ValueError("Expected uint8 BGR frame")
    h0,w0 = frame.shape[:2]
    if min(h0,w0)<2: raise ValueError("Frame too small")
    scale = min(1,cfg.processing_width/w0)
    img = cv2.resize(frame,(max(2,round(w0*scale)),max(2,round(h0*scale))),interpolation=cv2.INTER_AREA) if scale<1 else frame
    h,w = img.shape[:2]
    hls = cv2.cvtColor(img,cv2.COLOR_BGR2HLS)
    hsv = cv2.cvtColor(img,cv2.COLOR_BGR2HSV) if debug or cfg.mode=="previous_hsv" else None
    masks = {}
    for name in ('article_hsl_white','previous_hsv','saved_hsl'):
        if debug or cfg.mode==name:
            low,high=cfg.color_bounds[name]
            masks[name]=cv2.inRange(hsv if name=='previous_hsv' else hls,tuple(low),tuple(high))
    active = masks[cfg.mode]
    filtered = cv2.bitwise_and(img,img,mask=active)
    gray = cv2.cvtColor(filtered,cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray,(cfg.blur_kernel,cfg.blur_kernel),0)
    edges = cv2.Canny(blur,cfg.canny_low,cfg.canny_high)
    points = (np.array([[130/960,1],[410/960,330/540],[650/960,350/540],[930/960,1]])*[w-1,h-1]).astype(np.int32) if cfg.roi_shape=="article" else np.array([[0,int(cfg.roi_top*h)],[w-1,int(cfg.roi_top*h)],[w-1,h-1],[0,h-1]],np.int32)
    roi = np.zeros((h,w),np.uint8); cv2.fillPoly(roi,[points],255)
    cropped = edges & roi
    # Length/gap settings are expressed at the configured processing width.
    lines = cv2.HoughLinesP(cropped,1,np.pi/180,cfg.hough_threshold,minLineLength=cfg.min_line_length,maxLineGap=cfg.max_line_gap)
    observations,accepted = extract_observations(lines,w,h,cfg)
    stages = {}
    if debug:
        raw = np.zeros_like(img); kept = raw.copy(); fits = raw.copy()
        if lines is not None:
            for x1,y1,x2,y2 in lines[:,0]: cv2.line(raw,(x1,y1),(x2,y2),(200,200,200),2)
        for i,(obs,segs) in enumerate(zip(observations,accepted)):
            color = line_color(i+1)
            for x1,y1,x2,y2 in segs: cv2.line(kept,(x1,y1),(x2,y2),color,2)
            draw_line(fits,obs,color)
        values = [img,hsv[:,:,1],hsv[:,:,2],hls[:,:,1],hls[:,:,2],masks['article_hsl_white'],masks['previous_hsv'],masks['saved_hsl'],active,filtered,gray,blur,edges,cropped,raw,kept,cv2.bitwise_and(fits,fits,mask=roi)]
        stages = dict(zip(STAGES,values))
    return FrameResult(img,observations,stages,roi,(time.perf_counter()-started)*1000,0 if lines is None else len(lines))

def line_color(identity):
    return [(255,130,40),(60,230,80),(70,100,255),(220,100,220),(50,220,230)][(identity-1)%5]

def draw_line(image,line,color,held=False):
    h,w = image.shape[:2]
    # Draw only through supported height, plus a small foreground extension.
    if line.centerline_image:
        pts = (np.asarray(line.centerline_image)*[w-1,h-1]).astype(np.int32)
        for i in range(len(pts)-1):
            if not held or i%2==0: cv2.line(image,tuple(pts[i]),tuple(pts[i+1]),color,3,cv2.LINE_AA)
        return
    ys = np.linspace(line.y_min,min(1,line.y_max+.03),28)
    pts = np.column_stack([np.clip(line.a*ys+line.b,-2,3)*(w-1),ys*(h-1)]).astype(np.int32)
    for i in range(len(pts)-1):
        if not held or i%2==0: cv2.line(image,tuple(pts[i]),tuple(pts[i+1]),color,3,cv2.LINE_AA)

def render(result, tracks):
    overlay = result.original.copy(); h,w = overlay.shape[:2]
    for track in tracks:
        obs = Observation(track['a'],track['b'],track['y_min'],track['y_max'],track['confidence'],0)
        obs.centerline_image = track.get('centerline_image',[])
        color = line_color(track['id']) if track['valid'] else (150,150,150)
        draw_line(overlay,obs,color,held=not track['valid'])
        y = min(.95,obs.y_max); x = int(np.clip(obs.x(y),0,.9)*(w-1))
        cv2.putText(overlay,f"ID {track['id']} {track['status']}",(x,int(y*(h-1))),cv2.FONT_HERSHEY_SIMPLEX,.45,color,1,cv2.LINE_AA)
    # Preserve clean geometry inside the requested ROI.
    overlay[result.roi==0] = result.original[result.roi==0]
    return overlay


class Detector:
    """One persistent instance per camera; owns live ground history, not tracking."""
    def __init__(self, cfg):
        self.cfg = cfg
        self.ridge = None

    def detect(self, frame, debug=False, depth=None):
        if self.cfg.backend == 'legacy_hough':
            return legacy_detect(frame, self.cfg, debug)
        if self.ridge is None:
            from .physical import PhysicalDetector
            self.ridge = PhysicalDetector(self.cfg)
        result = self.ridge.detect(frame, depth, debug)
        if self.cfg.backend == 'hybrid_fallback' and not any(o.confidence >= self.cfg.min_confidence for o in result.observations):
            result = legacy_detect(frame, self.cfg, debug)
            result.backend = 'legacy_hough_fallback'
            for o in result.observations:
                o.confidence *= .5
                o.backend = result.backend
        return result


def detect(frame, cfg, debug=False, depth=None):
    """Stateless compatibility API. Streaming clients should keep a Detector."""
    return Detector(cfg).detect(frame, debug, depth)
