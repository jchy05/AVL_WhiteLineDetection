from dataclasses import asdict, dataclass, field
from importlib.resources import files
import json
import math
from pathlib import Path

MODES = ("article_hsl_white", "previous_hsv", "saved_hsl")

@dataclass
class Config:
    mode: str = "article_hsl_white"
    processing_width: int = 960
    roi_top: float = .4
    roi_shape: str = "rectangle"
    blur_kernel: int = 11
    canny_low: int = 50
    canny_high: int = 150
    hough_threshold: int = 15
    min_line_length: int = 20
    max_line_gap: int = 10
    consensus_distance: float = .008
    min_vertical_span: float = .08
    foreground_y: float = .7
    max_lines: int = 4
    max_candidates: int = 160
    association_gate: float = .10
    smoothing_seconds: float = .08
    confirm_hits: int = 3
    hold_seconds: float = .15
    reset_gap_seconds: float = .5
    min_confidence: float = .25
    max_frame_age_seconds: float = .25
    color_bounds: dict = field(default_factory=lambda: {
        'article_hsl_white': [[0,200,0],[180,255,255]],
        'previous_hsv': [[0,0,195],[180,30,255]],
        'saved_hsl': [[0,59,0],[36,205,40]],
    })

    def validate(self):
        for name,value in asdict(self).items():
            if isinstance(value,(float,int)) and not math.isfinite(value): raise ValueError(f"Non-finite {name}")
        for name in ("processing_width","blur_kernel","canny_low","canny_high","hough_threshold","min_line_length","max_line_gap","max_lines","max_candidates","confirm_hits"):
            if type(getattr(self,name)) is not int: raise ValueError(f"{name} must be an integer")
        if self.mode not in MODES: raise ValueError(f"mode must be one of {MODES}")
        if set(self.color_bounds)!=set(MODES): raise ValueError("color_bounds must contain exactly the three retained modes")
        for name,bounds in self.color_bounds.items():
            if len(bounds)!=2 or any(len(row)!=3 for row in bounds): raise ValueError(f"Invalid {name} color bounds")
            for lo,hi,maximum in zip(*bounds,(180,255,255)):
                if type(lo) is not int or type(hi) is not int or not 0<=lo<=hi<=maximum:
                    raise ValueError(f"Invalid {name} channel range")
        if self.roi_shape not in ("rectangle", "article"): raise ValueError("Invalid roi_shape")
        for name in ("roi_top", "foreground_y", "min_vertical_span", "min_confidence"):
            if not 0 <= getattr(self,name) <= 1: raise ValueError(f"Invalid {name}")
        if self.roi_top >= self.foreground_y: raise ValueError("roi_top must be above foreground_y")
        if self.processing_width < 160: raise ValueError("processing_width must be >=160")
        if self.blur_kernel < 1 or self.blur_kernel % 2 != 1: raise ValueError("blur_kernel must be positive and odd")
        if not 0 <= self.canny_low < self.canny_high <= 255: raise ValueError("Invalid Canny thresholds")
        for name in ("hough_threshold", "min_line_length", "max_lines", "max_candidates", "confirm_hits"):
            if getattr(self,name) < 1: raise ValueError(f"Invalid {name}")
        for name in ("consensus_distance", "association_gate", "smoothing_seconds", "hold_seconds", "reset_gap_seconds", "max_frame_age_seconds"):
            if getattr(self,name) <= 0: raise ValueError(f"Invalid {name}")
        if self.max_line_gap < 0: raise ValueError("Invalid max_line_gap")
        return self

def load_config(path=None):
    data = json.loads(Path(path).read_text() if path else files("avl_white_lines").joinpath("default.json").read_text())
    return Config(**data).validate()

def save_config(cfg, path):
    Path(path).write_text(json.dumps(asdict(cfg),indent=2)+"\n",encoding="utf-8")
