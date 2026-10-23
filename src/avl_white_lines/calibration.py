"""Pure calibration/registration checks usable without ROS installed."""
from dataclasses import asdict
import numpy as np
from .camera import CameraModel,camera_from_config


def camera_from_rectified_info(mount,width,height,projection,binning=(0,0),roi=(0,0,0,0)):
    """P intrinsics at full rectified stream size; never guess crop/binning."""
    if type(width) is not int or type(height) is not int or min(width,height)<2: raise ValueError('Invalid CameraInfo dimensions')
    if any(v not in (0,1) for v in binning) or (any(roi) and tuple(roi)!=(0,0,width,height)): raise ValueError('Cropped/binned CameraInfo requires explicitly adjusted calibration')
    P=np.asarray(projection,dtype=float)
    if P.size!=12 or not np.isfinite(P).all(): raise ValueError('Invalid CameraInfo P')
    P=P.reshape(3,4)
    if P[0,0]<=0 or P[1,1]<=0 or not np.allclose(P[2],[0,0,1,0]) or not np.allclose(P[:2,3],0) or not np.allclose([P[0,1],P[1,0]],0): raise ValueError('Expected rectified left-camera pinhole projection')
    original=camera_from_config(mount)
    model=CameraModel(float(P[0,0]),float(P[1,1]),float(P[0,2]),float(P[1,2]),width,height,original.height_m,original.pitch_deg)
    return asdict(camera_from_config(asdict(model)))


def depth_registration_reason(rgb_shape,depth_shape,rgb_frame,depth_frame):
    if tuple(rgb_shape[:2])!=tuple(depth_shape): return 'depth_size_mismatch'
    if not rgb_frame or not depth_frame: return 'depth_frame_id_missing'
    if rgb_frame!=depth_frame: return 'depth_frame_id_mismatch'
    return None
