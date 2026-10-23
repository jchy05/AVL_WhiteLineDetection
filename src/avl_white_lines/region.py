"""Explicit normalized image ROI; a crop is not ground confirmation."""
import cv2
import numpy as np


def validate_polygon(points):
    a=np.asarray(points,dtype=float)
    if a.ndim!=2 or a.shape[1]!=2 or len(a)<3 or not np.isfinite(a).all() or np.any((a<0)|(a>1)):
        raise ValueError('image_roi requires >=3 finite [x,y] points in [0,1]')
    # Convex polygons avoid ambiguous self-intersections and are enough for road ROIs.
    contour=a.astype(np.float32)
    if cv2.contourArea(contour)<1e-4 or not cv2.isContourConvex(contour): raise ValueError('image_roi must be a nondegenerate convex polygon')
    return a


def image_region(shape,points):
    h,w=shape
    mask=np.ones((h,w),np.uint8)*255
    if points:
        vertices=np.rint(validate_polygon(points)*[w-1,h-1]).astype(np.int32)
        mask[:]=0;cv2.fillConvexPoly(mask,vertices,255)
    return mask
