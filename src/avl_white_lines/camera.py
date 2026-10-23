"""Camera models for the white-line detector.

The detector reasons about the ground in metres (how wide a line is, how far
away it is), so it needs three things about a camera:

  * pinhole intrinsics fx, fy, cx, cy at some reference image size,
  * the lens height above the ground (m),
  * the downward pitch of the optical axis (deg, positive = looking down).

With stereo depth the height and pitch can be measured live instead
(see ``WhiteLineDetector(ground_live=True)`` and ``ground_fit.py``).
"""
from dataclasses import dataclass

import numpy as np


@dataclass
class CameraModel:
    fx: float
    fy: float
    cx: float
    cy: float
    ref_width: int
    ref_height: int
    height_m: float
    pitch_deg: float

    def K_for(self, width, height):
        """Intrinsics rescaled to an image of width x height (pixel-centre correct)."""
        sx, sy = width / float(self.ref_width), height / float(self.ref_height)
        return np.array([[self.fx * sx, 0.0, (self.cx + 0.5) * sx - 0.5],
                         [0.0, self.fy * sy, (self.cy + 0.5) * sy - 0.5],
                         [0.0, 0.0, 1.0]])

    def horizon_for(self,width,height):
        K=self.K_for(width,height)
        return float(K[1,2]-K[1,1]*np.tan(np.radians(self.pitch_deg)))

    def pixel_to_ground(self,u,v,width,height):
        """Intersect rectified pixels with flat ground; NaN above horizon."""
        K=self.K_for(width,height); t=np.radians(self.pitch_deg)
        rx=(np.asarray(u)-K[0,2])/K[0,0]; ry=(np.asarray(v)-K[1,2])/K[1,1]
        den=np.cos(t)*ry+np.sin(t)
        with np.errstate(divide='ignore',invalid='ignore'):
            scale=np.where(den>1e-9,self.height_m/den,np.nan)
        return np.stack([scale*(np.cos(t)-np.sin(t)*ry),-scale*rx],axis=-1)

    def ground_to_pixel(self,points,width,height):
        """Ground [X forward,Y left] metres to rectified image [u,v]."""
        points=np.asarray(points); X,Y=points[...,0],points[...,1]
        t=np.radians(self.pitch_deg); K=self.K_for(width,height)
        z=np.cos(t)*X+np.sin(t)*self.height_m
        with np.errstate(divide='ignore',invalid='ignore'):
            u=K[0,0]*(-Y)/z+K[0,2]
            v=K[1,1]*(-np.sin(t)*X+np.cos(t)*self.height_m)/z+K[1,2]
        return np.stack([np.where(z>0,u,np.nan),np.where(z>0,v,np.nan)],axis=-1)

    @classmethod
    def from_hfov(cls, hfov_deg, width, height, height_m, pitch_deg):
        """Ideal pinhole from a horizontal field of view (no calibration at hand)."""
        f = (width / 2.0) / np.tan(np.radians(hfov_deg) / 2.0)
        return cls(f, f, (width - 1) / 2.0, (height - 1) / 2.0, width, height,
                   height_m, pitch_deg)


# Marvin's three ZED X cameras: intrinsics from camera_info at 480x300 (the
# rectified, downscaled stream), height/pitch from the stereo ground plane
# with the robot on the floor (2026-10-09/19). These are the "current" mounts.
PRESETS = {
    'marvin_front': CameraModel(181.2, 181.2, 242.0, 153.3, 480, 300, 0.62, 20.7),
    'marvin_left': CameraModel(317.1, 317.1, 234.3, 153.8, 480, 300, 0.61, 18.1),
    'marvin_right': CameraModel(320.2, 320.2, 234.2, 153.8, 480, 300, 0.62, 18.2),
    # Mounts in the 2026-09-17 outdoor recording (the front camera sat lower
    # then); use these with that footage.
    'marvin_front_2026_09_17': CameraModel(181.2, 181.2, 242.0, 153.3, 480, 300, 0.45, 21.5),
    'marvin_left_2026_09_17': CameraModel(317.1, 317.1, 234.3, 153.8, 480, 300, 0.61, 18.3),
    'marvin_right_2026_09_17': CameraModel(320.2, 320.2, 234.2, 153.8, 480, 300, 0.61, 20.5),
}


def camera_from_config(data):
    if isinstance(data,str):
        if data not in PRESETS: raise ValueError('Unknown camera preset')
        from dataclasses import replace
        cam = replace(PRESETS[data])
    else:
        if not data: raise ValueError('Ridge backend requires explicit camera calibration or preset')
        cam = CameraModel(**data)
    values = list(vars(cam).values())
    if not np.isfinite(values).all() or min(cam.fx,cam.fy,cam.ref_width,cam.ref_height,cam.height_m)<=0 or not -45<cam.pitch_deg<85:
        raise ValueError('Invalid camera calibration')
    return cam
