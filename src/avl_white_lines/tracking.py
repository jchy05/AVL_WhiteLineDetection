"""One-to-one geometric association and time-based smoothing, with explicit expiry."""
from dataclasses import dataclass
import math
import numpy as np
from .detector import Observation

@dataclass
class Track:
    identity: int
    line: Observation
    last_seen: float
    hits: int = 1
    streak: int = 1
    confirmed: bool = False
    measured: bool = True

class Tracker:
    def __init__(self,cfg):
        self.cfg = cfg; self.tracks = []; self.next_id = 1; self.last_time = None

    def reset(self):
        self.tracks = []; self.last_time = None

    def update(self,observations,timestamp):
        if not math.isfinite(timestamp): raise ValueError("timestamp must be finite")
        if self.last_time is not None and (timestamp<=self.last_time or timestamp-self.last_time>self.cfg.reset_gap_seconds): self.reset()
        dt = timestamp-self.last_time if self.last_time is not None else 1/30
        self.last_time = timestamp
        self.tracks = [t for t in self.tracks if timestamp-t.last_seen<=self.cfg.hold_seconds]
        for t in self.tracks: t.measured = False
        # Compare within common observed y range, avoiding unstable bottom extrapolation.
        pairs=[]
        for i,t in enumerate(self.tracks):
            for j,o in enumerate(observations):
                y0,y1 = max(t.line.y_min,o.y_min),min(t.line.y_max,o.y_max)
                if y1-y0<.03: continue
                ys = np.array([y0,y1])
                distance = float(np.max(np.abs(t.line.x(ys)-o.x(ys))))
                angle = abs(math.atan(t.line.a)-math.atan(o.a))
                if distance<self.cfg.association_gate and angle<.35:
                    pairs.append((distance+.05*angle,i,j))
        used_t,used_o = set(),set()
        alpha = 1-math.exp(-dt/self.cfg.smoothing_seconds)
        for _,i,j in sorted(pairs):
            if i in used_t or j in used_o: continue
            used_t.add(i); used_o.add(j)
            t,o = self.tracks[i],observations[j]
            t.line = Observation((1-alpha)*t.line.a+alpha*o.a,(1-alpha)*t.line.b+alpha*o.b,o.y_min,o.y_max,o.confidence,o.support)
            t.last_seen=timestamp; t.hits+=1; t.streak+=1; t.measured=True
            t.confirmed = t.confirmed or t.streak>=self.cfg.confirm_hits
        for i,t in enumerate(self.tracks):
            if i not in used_t: t.streak=0
        for j,o in enumerate(observations):
            if j not in used_o and o.confidence>=self.cfg.min_confidence:
                self.tracks.append(Track(self.next_id,o,timestamp,confirmed=self.cfg.confirm_hits==1)); self.next_id+=1
        output=[]
        for t in self.tracks:
            age = max(0,timestamp-t.last_seen)
            confidence = t.line.confidence*math.exp(-age/self.cfg.hold_seconds)
            status = "tentative" if not t.confirmed else ("measured" if t.measured else "held")
            valid = t.confirmed and t.measured and confidence>=self.cfg.min_confidence
            output.append(dict(id=t.identity,a=t.line.a,b=t.line.b,y_min=t.line.y_min,y_max=t.line.y_max,
                               confidence=confidence,valid=bool(valid),status=status,age_seconds=age,hits=t.hits))
        return output
