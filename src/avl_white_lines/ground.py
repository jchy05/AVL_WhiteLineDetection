"""Live ground-plane estimate from a registered depth image.

Back-projects a sample of pixels below the horizon into the camera's optical
frame (x right, y down, z forward), RANSAC-fits a plane, and returns the
camera's height above it and its downward pitch. A camera pitched down by t
sees world-up as n = (0, -cos t, -sin t), so t = atan2(-n_z, -n_y).

Returns None unless the fit is clearly a floor: enough valid depth below the
horizon (a blocked or blurred lens has little), enough points on the plane, a
normal within max_tilt_deg of the expected one, and (given h_ref, the
configured mount height) a height within h_window of it, so a table top is
never taken for the floor while a hoist still is. RANSAC
hypotheses are scored together as one matrix product (~10 ms on the Orin).
"""
import numpy as np


def fit_ground(depth, K, pitch_guess_deg, h_ref=None, rng=None, n_sample=3000, z_min=0.4,
               z_max=6.0, tol=0.02, iters=150, min_inliers=600, min_frac=0.15,
               min_valid=0.35, h_window=0.35, max_tilt_deg=25.0):
    rng = np.random.default_rng(0) if rng is None else rng
    h, w = depth.shape[:2]
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
    v0 = int(max(0, min(h - 1, cy - fy * np.tan(np.radians(pitch_guess_deg)) + 0.08 * h)))
    vs, us = np.mgrid[v0:h:2, 0:w:2]
    z = depth[vs, us].astype(np.float32)
    ok = np.isfinite(z) & (z > z_min) & (z < z_max)
    if ok.sum() < min_inliers or ok.mean() < min_valid:
        return None
    us, vs, z = us[ok], vs[ok], z[ok]
    if len(z) > n_sample:
        k = rng.choice(len(z), n_sample, replace=False)
        us, vs, z = us[k], vs[k], z[k]
    P = np.stack([(us - cx) * z / fx, (vs - cy) * z / fy, z], 1)
    t = np.radians(pitch_guess_deg)
    n_exp = np.array([0.0, -np.cos(t), -np.sin(t)])
    cos_max = np.cos(np.radians(max_tilt_deg))
    # all RANSAC hypotheses at once: (iters, 3) normals vs (N, 3) points
    tri = P[rng.integers(0, len(P), (iters, 3))]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    nn = np.linalg.norm(n, axis=1)
    keep = nn > 1e-9
    n = n[keep] / nn[keep, None]
    n *= np.sign(n @ n_exp)[:, None]
    good = (n @ n_exp) >= cos_max
    if not good.any():
        return None
    n, d = n[good], np.einsum('ij,ij->i', n[good], tri[keep][good][:, 0])
    counts = (np.abs(P @ n.T - d) < tol).sum(0)
    k = int(np.argmax(counts))
    best_n = int(counts[k])
    if best_n < min_inliers or best_n < min_frac * len(P):
        return None
    best = (n[k], d[k])
    n, d = best
    inl = P[np.abs(P @ n - d) < tol]
    c0 = inl.mean(0)
    n = np.linalg.svd(inl - c0, full_matrices=False)[2][2]
    if n @ n_exp < 0:
        n = -n
    height = float(-(c0 @ n))           # origin is above the floor: n.c0 < 0
    pitch = float(np.degrees(np.arctan2(-n[2], -n[1])))
    if not (0.1 < height < 3.0):
        return None
    if h_ref is not None and abs(height - h_ref) > h_window:
        return None
    return height, pitch, best_n / len(P)
