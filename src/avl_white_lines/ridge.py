"""White-line (course tape) detector for the dinosaur ZED X cameras.

Deployable module: construct once per camera from its intrinsics and mounting,
then call detect(bgr) per frame. Pure numpy + OpenCV, no ROS dependency.

What it separates, and how -- every choice here was measured, see the research
notes (see README.md, "How it works"):

  thing                       signature                  rejected by
  --------------------------  -------------------------  ----------------------------
  white tape (the target)     bright ridge, 7.6 cm wide  (kept)
  crack / dark joint          DARK ridge                 bright-ridge operator
  light-sealed joint          bright ridge, 5-8 mm       ground-width gate (measured)
  shadow edge                 step, not ridge            both sides darker, per side
  lit gap between 2 shadows   bright ridge, skylit sides shade colour + lit-surface level
  wall / slab / glare patch   too wide                   calibration-guided scale band
  grass, cones, coloured      chromatic                  colour vs local surface
  anything above the horizon  not on the ground          horizon from calibration

Method: Hessian ridge detection on LOG luminance (a shadow multiplies radiance,
so in log space it is a constant offset with zero curvature), at each pixel
searching only the scales a 2.5-15 cm ground strip can have there, computed
from the camera model. Ridge orientation is local, so curves are handled
natively (the component-shape gate this replaces went blind to any curve
tighter than ~30 m radius).
"""
import numpy as np
import cv2

TAPE_W = 0.0762                      # IGVC: "approximately three inches"
SIGMA_TO_W = 2.0                     # sigma^2-normalised bar response peaks at w = 2 sigma
SHADE_BLUE = 0.05                    # log(B/R): skylit shade vs sun, measured 0.10
# (pyramid level, scales in full-resolution pixels). Octave (2x) spacing:
# measured against 1.5x spacing on the same data -- equal real dash recall
# (0.93), 2.6x fewer false cells on real footage (1.4 vs 3.6 per frame),
# 30% faster. The width gate's 2.5-15 cm window does not need finer scales.
LEVELS = ((0, (0.9, 1.8)), (1, (3.6, 7.2)), (2, (14.4, 21.6)))
_S = np.arange(256, dtype=np.float64) / 255.0
_LIN = np.where(_S <= 0.04045, _S / 12.92, ((_S + 0.055) / 1.055) ** 2.4).astype(np.float32)
_Y = np.array([0.0722, 0.7152, 0.2126], np.float32)            # BGR luminance weights


def _sample(img, x, y):
    """Bilinear samples at arbitrary points (any shape). cv2.remap caps a map
    dimension at 32767, so points are laid out as a 2-D block."""
    x = np.asarray(x, np.float32).ravel()
    y = np.asarray(y, np.float32).ravel()
    n = x.size
    cols = 1024
    rows = max(1, -(-n // cols))
    pad = rows * cols - n
    out = cv2.remap(img, np.pad(x, (0, pad)).reshape(rows, cols),
                    np.pad(y, (0, pad)).reshape(rows, cols),
                    cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return out.ravel()[:n]


class WhiteRidgeDetector:
    def __init__(self, K, cam_height, pitch_deg, width, height,
                 t_high=0.22, t_low=0.10, side_log=0.10,
                 w_min=0.025, w_max=0.15, resolvable_px=3.0,
                 min_len_m=0.30, min_len_px=10,
                 shade_blue=SHADE_BLUE, shade_weak=0.02, lit_margin=0.15,
                 chroma_rel=12.0, chroma_abs=28.0, max_range_m=12.0):
        K = np.asarray(K, np.float64).reshape(3, 3)
        self.fx, self.fy, self.cx, self.cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
        self.h = float(cam_height)
        t = np.radians(pitch_deg)
        self.zc = np.array([np.cos(t), 0.0, -np.sin(t)])
        self.xc = np.array([0.0, -1.0, 0.0])
        self.yc = np.array([-np.sin(t), 0.0, -np.cos(t)])
        self.W, self.H = int(width), int(height)
        self.p = dict(t_high=t_high, t_low=t_low, side_log=side_log, w_min=w_min,
                      w_max=w_max, resolvable_px=resolvable_px, min_len_m=min_len_m,
                      min_len_px=min_len_px, shade_blue=shade_blue,
                      shade_weak=shade_weak, lit_margin=lit_margin,
                      chroma_rel=chroma_rel, chroma_abs=chroma_abs)
        self.horizon_row = self.cy - self.fy * np.tan(t)
        self._precompute(max_range_m)

    # ------------------------------------------------------------- geometry
    def _ray(self, u, v):
        rx = (u - self.cx) / self.fx
        ry = (v - self.cy) / self.fy
        dz = rx * self.xc[2] + ry * self.yc[2] + self.zc[2]
        dx = rx * self.xc[0] + ry * self.yc[0] + self.zc[0]
        dy = rx * self.xc[1] + ry * self.yc[1] + self.zc[1]
        with np.errstate(divide='ignore', invalid='ignore'):
            tt = -self.h / dz
        ok = dz < -1e-9
        return np.where(ok, tt * dx, np.nan), np.where(ok, tt * dy, np.nan), np.where(ok, tt, np.nan)

    def _precompute(self, max_range_m):
        """Everything that depends only on the camera, done once."""
        uu, vv = np.meshgrid(np.arange(self.W, dtype=np.float64),
                             np.arange(self.H, dtype=np.float64))
        X0, Y0, Z0 = self._ray(uu, vv)
        Xu, Yu, _ = self._ray(uu + 0.5, vv)
        Xv, Yv, _ = self._ray(uu, vv + 0.5)
        valid = np.isfinite(X0) & np.isfinite(Xu) & np.isfinite(Xv)
        f = lambda a: np.nan_to_num(a).astype(np.float32)
        self.Jxu, self.Jyu = f((Xu - X0) / 0.5), f((Yu - Y0) / 0.5)
        self.Jxv, self.Jyv = f((Xv - X0) / 0.5), f((Yv - Y0) / 0.5)
        # optical-axis depth a ground point at this pixel would have (for the
        # stereo "is it actually on the ground" check)
        self.z_ground = np.where(valid, Z0, np.nan).astype(np.float32)
        rng = np.hypot(np.nan_to_num(X0), np.nan_to_num(Y0))
        self.ground = valid & (rng <= max_range_m)
        self.ground[:max(0,min(self.H,int(np.ceil(self.horizon_row)) + 1)), :] = False
        self.r0 = max(0, min(self.H-4, int(np.floor(self.horizon_row)) - 2))
        # singular values of J -> the pixel widths a w_min..w_max strip can
        # have here, over all orientations -> the scales worth searching
        a, b, c, d = self.Jxu, self.Jxv, self.Jyu, self.Jyv
        p, q, r = a * a + c * c, b * b + d * d, a * b + c * d
        root = np.sqrt(np.maximum(((p - q) / 2) ** 2 + r * r, 0))
        smax = np.sqrt(np.maximum((p + q) / 2 + root, 0))
        smin = np.sqrt(np.maximum((p + q) / 2 - root, 0))
        lo = self.p['w_min'] / np.maximum(smax, 1e-9) / SIGMA_TO_W
        hi = self.p['w_max'] / np.maximum(smin, 1e-9) / SIGMA_TO_W
        all_s = [s for _, ss in LEVELS for s in ss]
        lo = np.minimum(lo, all_s[-1])
        hi = np.maximum(hi, all_s[0])
        self.inband = {s: ((s >= lo / 1.5) & (s <= hi * 1.5))[self.r0:] for s in all_s}

    def _per_px(self, nx, ny):
        """Ground metres per pixel across (perp) and along the local ridge."""
        tx, ty = -ny, nx
        glx = self.Jxu * tx + self.Jxv * ty
        gly = self.Jyu * tx + self.Jyv * ty
        gl = np.sqrt(glx * glx + gly * gly) + 1e-12
        sx = self.Jxu * nx + self.Jxv * ny
        sy = self.Jyu * nx + self.Jyv * ny
        return np.abs(sx * (-gly / gl) + sy * (glx / gl)), gl

    # --------------------------------------------------------------- ridges
    def _ridges(self, logL):
        roi = logL[self.r0:]
        H, W = roi.shape
        best = np.zeros((H, W), np.float32)
        best_s = np.zeros((H, W), np.float32)
        ex_b = np.ones((H, W), np.float32)      # unnormalised eigenvector of
        ey_b = np.zeros((H, W), np.float32)     # the best scale, normalised once
        img = roi
        for lvl, scales in LEVELS:
            if lvl > 0:
                img = cv2.pyrDown(img)
            k = 2 ** lvl
            for s in scales:
                sl = s / k
                g = cv2.GaussianBlur(img, (0, 0), sl)
                hxx = cv2.Sobel(g, cv2.CV_32F, 2, 0, ksize=3)
                hyy = cv2.Sobel(g, cv2.CV_32F, 0, 2, ksize=3)
                hxy = cv2.Sobel(g, cv2.CV_32F, 1, 1, ksize=3)
                tr = 0.5 * (hxx + hyy)
                dd = cv2.sqrt(0.25 * (hxx - hyy) ** 2 + hxy * hxy)
                lmin = tr - dd
                # bright ridge: strongly negative across, weak along
                r = (-lmin) * (sl * sl)
                r[(lmin >= 0) | (np.abs(tr + dd) >= -0.5 * lmin)] = 0.0
                ex, ey = hxy, lmin - hxx
                if lvl > 0:
                    r = cv2.resize(r, (W, H), interpolation=cv2.INTER_LINEAR)
                    ex = cv2.resize(ex, (W, H), interpolation=cv2.INTER_NEAREST)
                    ey = cv2.resize(ey, (W, H), interpolation=cv2.INTER_NEAREST)
                r[~self.inband[s]] = 0.0
                upd = r > best
                np.copyto(best, r, where=upd)
                best_s[upd] = s
                np.copyto(ex_b, ex, where=upd)
                np.copyto(ey_b, ey, where=upd)
        nrm = cv2.sqrt(ex_b * ex_b + ey_b * ey_b)
        deg = nrm < 1e-9
        nrm[deg] = 1.0
        nx = ex_b / nrm
        ny = ey_b / nrm
        nx[deg] = 1.0
        ny[deg] = 0.0
        pad = lambda a, v: np.vstack([np.full((self.r0, W), v, np.float32), a])
        return pad(best, 0), pad(best_s, 0), pad(nx, 1), pad(ny, 0)

    # ---------------------------------------------------------------- detect
    def detect(self, bgr, depth=None, depth_margin=0.15, depth_vote=0.3, depth_confirm=0.0,
               return_debug=False):
        """bgr: HxW BGR uint8 frame. depth (optional): registered stereo depth
        (metres along the optical axis); pixels where the measured surface is
        clearly NEARER than the ground plane are rejected as objects standing
        on the ground (wheels, shoes, barrel stripes, poles), and a connected
        segment is dropped whole when more than depth_vote of its pixels with
        valid depth are. depth_confirm > 0 also drops a segment unless that
        fraction of ALL its pixels have depth confirming they are on the
        ground (missing depth counts against)."""
        P = self.p
        H, W = self.H, self.W
        lin = _LIN[bgr]
        logL = np.log(lin @ _Y + 0.004).astype(np.float32)
        logBR = (np.log(lin[:, :, 0] + 0.004) - np.log(lin[:, :, 2] + 0.004)).astype(np.float32)
        labc = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
        la = cv2.GaussianBlur(labc[:, :, 1] - 128.0, (0, 0), 1.0)
        lb = cv2.GaussianBlur(labc[:, :, 2] - 128.0, (0, 0), 1.0)

        best, best_s, nx, ny = self._ridges(logL)
        perp_full, along_full = self._per_px(nx, ny)
        cand = (best >= P['t_low']) & self.ground

        w_px = best_s * SIGMA_TO_W
        ys, xs = np.nonzero(cand)
        good = np.zeros((H, W), bool)
        shade_map = np.zeros((H, W), np.float32)
        side_gate = np.zeros((H,W), bool); color_gate = side_gate.copy(); width_gate = side_gate.copy()
        if len(xs):
            sm = cv2.GaussianBlur(logL, (0, 0), 0.8)
            smBR = cv2.GaussianBlur(logBR, (0, 0), 1.5)
            o = 0.5 * w_px[ys, xs] + 2.0          # just outside the ridge edge
            ex, ey = nx[ys, xs], ny[ys, xs]
            px_, py_ = xs + ex * o, ys + ey * o
            qx_, qy_ = xs - ex * o, ys - ey * o
            c = sm[ys, xs]
            ok = ((c - _sample(sm, px_, py_)) >= P['side_log']) & \
                 ((c - _sample(sm, qx_, qy_)) >= P['side_log'])
            side_gate[ys,xs] = ok
            # shade-colour evidence, decided per segment below
            br_c = smBR[ys, xs]
            oc = o + 1.0
            ev = np.minimum(_sample(smBR, xs + ex * oc, ys + ey * oc) - br_c,
                            _sample(smBR, xs - ex * oc, ys - ey * oc) - br_c)
            # neutral, like the surface around it under the same light
            ca, cb = la[ys, xs], lb[ys, xs]
            sa = 0.5 * (_sample(la, px_, py_) + _sample(la, qx_, qy_))
            sb = 0.5 * (_sample(lb, px_, py_) + _sample(lb, qx_, qy_))
            ok &= (np.hypot(ca - sa, cb - sb) <= P['chroma_rel']) & \
                  (np.hypot(ca, cb) <= P['chroma_abs'])
            color_gate[ys,xs] = ok
            # ground width, where tape would be resolvable
            perp = perp_full[ys, xs]
            wg = w_px[ys, xs] * perp
            resolvable = TAPE_W / np.maximum(perp, 1e-9) >= P['resolvable_px']
            ok &= np.where(resolvable, (wg >= P['w_min']) & (wg <= P['w_max']),
                           wg <= 2.0 * P['w_max'])
            width_gate[ys,xs] = np.where(resolvable, (wg >= P['w_min']) & (wg <= P['w_max']), wg <= 2*P['w_max'])
            good[ys[ok], xs[ok]] = True
            shade_map[ys, xs] = ev

        # hysteresis: weak ridge pixels survive if connected to a strong one
        n, lab = cv2.connectedComponents(good.astype(np.uint8), connectivity=8)
        if n > 1:
            keep = np.zeros(n, bool)
            keep[np.unique(lab[good & (best >= P['t_high'])])] = True
            keep[0] = False
            mask = keep[lab]
        else:
            mask = good

        if mask.any():
            n, lab = cv2.connectedComponents(mask.astype(np.uint8), connectivity=8)
            li = lab[mask]
            # lit gap between two shadows: one verdict per segment (per-pixel
            # colour is too noisy), from two independent cues
            q = cv2.resize(logL, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
            q = cv2.dilate(cv2.morphologyEx(q, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)),
                           np.ones((15, 15), np.uint8))
            litref = cv2.resize(q, (W, H), interpolation=cv2.INTER_LINEAR)
            ev_m, above_m = _seg_median(li, shade_map[mask], (logL - litref)[mask], n)
            drop = (ev_m > P['shade_blue']) | ((ev_m > P['shade_weak']) & (above_m < P['lit_margin']))
            # ground length and image length along the ridge
            thick = np.maximum(w_px[mask], 1.0)
            g_len = np.bincount(li, weights=along_full[mask] / thick, minlength=n)
            p_len = np.bincount(li, weights=1.0 / thick, minlength=n)
            drop |= (g_len < P['min_len_m']) | (p_len < P['min_len_px'])
            drop[0] = True
            mask = ~drop[lab] & (lab > 0)

        length_mask = mask.copy()
        if mask.any() and depth is not None:
            # objects standing on the ground (chair legs, drawer handles,
            # table edges, people) are bright bars too; stereo says they are
            # nearer than the ground plane. Vote per segment: coarse stereo
            # bleeds at object edges, so single pixels are not trusted.
            dz = np.asarray(depth, np.float32)
            ok = np.isfinite(dz) & (dz > 0)
            nearer = ok & (dz < self.z_ground * (1.0 - depth_margin))
            n, lab = cv2.connectedComponents(mask.astype(np.uint8), connectivity=8)
            n_ok = np.bincount(lab[mask & ok], minlength=n)
            n_near = np.bincount(lab[mask & nearer], minlength=n)
            drop = n_near > depth_vote * np.maximum(n_ok, 1)
            if depth_confirm > 0:
                # positive evidence: stereo must put enough of the segment ON
                # the ground (no depth counts against), for consumers that
                # project unconfirmed pixels with a ground homography anyway
                n_all = np.bincount(lab[mask], minlength=n)
                n_ground = np.bincount(lab[mask & ok & (np.abs(dz-self.z_ground) <= self.z_ground*depth_margin)], minlength=n)
                drop |= n_ground < depth_confirm * n_all
            drop[0] = False
            mask &= ~drop[lab] & ~nearer

        depth_mask = mask.copy()
        if mask.any():
            mask = cv2.dilate(mask.astype(np.uint8),
                              cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))) > 0
            mask &= self.ground

        if return_debug:
            return mask, dict(best=best, best_s=best_s, nx=nx, ny=ny, good=good, logL=logL, width_gate=width_gate, side_gate=side_gate, color_gate=color_gate, length_mask=length_mask, depth_mask=depth_mask)
        return mask


def _seg_median(labels, a, b, n):
    """Per-label (lower) medians of two arrays, vectorised: sort by (label,
    value) and take each label's middle element. (A per-segment np.median loop
    cost ~12 ms/frame at ~190 segments.)"""
    counts = np.bincount(labels, minlength=n)
    starts = np.r_[0, np.cumsum(counts)[:-1]]
    mid = starts + (np.maximum(counts, 1) - 1) // 2
    out = []
    for arr in (a, b):
        o = np.lexsort((arr, labels))
        med = np.zeros(n, np.float32)
        have = counts > 0
        med[have] = arr[o][mid[have]]
        out.append(med)
    return out[0], out[1]
