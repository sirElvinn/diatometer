"""
segment.py - turn an SEM image (databar already removed) into a list of object masks.

Backends
  fastsam  : Ultralytics FastSAM "segment everything"  (fast on a laptop CPU)
  sam      : Ultralytics MobileSAM "segment everything" (slower, usually cleaner outlines)
  circles  : size-aware circle finder for round centric shells (Thaps). No deep learning.
             Radius range comes from the literature size of the species, so it is
             precise but misses shells seen side-on - use it as a sanity baseline.

The first run of fastsam/sam downloads the weights automatically (open-source models).
"""
from __future__ import annotations

import os

import numpy as np
import cv2

from species import SPECIES

_MODELS: dict = {}
_HERE = os.path.dirname(os.path.abspath(__file__))


def _dedupe(masks: list[np.ndarray], max_frac: float = 0.5, iou_thr: float = 0.8) -> list[np.ndarray]:
    """Drop background-sized masks and near-duplicates (keep the larger one)."""
    if not masks:
        return []
    h, w = masks[0].shape
    items = []                                   # (mask, area, bounding box)
    for m in masks:
        area = int(m.sum())
        if 0 < area < max_frac * h * w:
            rows, cols = np.flatnonzero(m.any(axis=1)), np.flatnonzero(m.any(axis=0))
            items.append((m, area, (rows[0], rows[-1] + 1, cols[0], cols[-1] + 1)))
    items.sort(key=lambda it: -it[1])
    kept: list[tuple] = []
    for m, area, (r0, r1, c0, c1) in items:
        dup = False
        for k, karea, (s0, s1, d0, d1) in kept:
            # only compare inside the overlap of the two bounding boxes (big photos have
            # hundreds of masks; full-frame comparisons took minutes)
            y0, y1, x0, x1 = max(r0, s0), min(r1, s1), max(c0, d0), min(c1, d1)
            if y0 >= y1 or x0 >= x1:
                continue
            inter = int(np.logical_and(m[y0:y1, x0:x1], k[y0:y1, x0:x1]).sum())
            if inter == 0:
                continue
            union = area + karea - inter
            if inter / union > iou_thr or inter / area > 0.9:   # same object or nested copy
                dup = True
                break
        if not dup:
            kept.append((m, area, (r0, r1, c0, c1)))
    return [k[0] for k in kept]


def _ultralytics_masks(img_gray: np.ndarray, kind: str) -> list[np.ndarray]:
    from ultralytics import SAM, FastSAM  # pip install ultralytics
    rgb = cv2.cvtColor(img_gray, cv2.COLOR_GRAY2RGB)
    if kind not in _MODELS:
        _MODELS[kind] = FastSAM(os.path.join(_HERE, "FastSAM-s.pt")) if kind == "fastsam" \
            else SAM(os.path.join(_HERE, "mobile_sam.pt"))
    model = _MODELS[kind]
    if kind == "fastsam":
        res = model(rgb, retina_masks=True, imgsz=1024, conf=0.4, iou=0.9, verbose=False)
    else:
        res = model(rgb, verbose=False)          # no prompts = segment everything
    if not res or res[0].masks is None:
        return []
    data = res[0].masks.data.cpu().numpy() > 0.5
    h, w = img_gray.shape
    out = []
    for m in data:
        if m.shape != (h, w):
            m = cv2.resize(m.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST) > 0
        out.append(m)
    return out


def _circle_masks(img_gray: np.ndarray, um_per_px: float, species: str | None) -> list[np.ndarray]:
    sp = SPECIES.get(species or "", SPECIES["Thalassiosira pseudonana"])
    if sp["morphotype"] != "centric":
        return []
    d_lo, d_hi = sp.get("typical_length_um", sp["length_um"])
    # work at a resolution where a typical shell radius is ~20 px
    f = min(1.0, 20.0 / ((d_lo + d_hi) / 4.0 / um_per_px))
    small = cv2.resize(img_gray, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    ump = um_per_px / f
    blur = cv2.GaussianBlur(small, (0, 0), 1.2)
    rmin, rmax = int(0.45 * d_lo / ump), int(0.6 * d_hi / ump)
    if rmin < 4:
        return []
    c = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT_ALT, dp=1.5, minDist=int(0.5 * d_lo / ump),
                         param1=150, param2=0.75, minRadius=rmin, maxRadius=rmax)
    if c is None:
        return []
    keep: list[tuple[float, float, float]] = []
    for x, y, r in c[0]:                           # suppress heavily overlapping circles
        if all(np.hypot(x - kx, y - ky) > 0.8 * max(r, kr) for kx, ky, kr in keep):
            keep.append((x, y, r))
    h, w = img_gray.shape
    masks = []
    for x, y, r in keep:
        m = np.zeros((h, w), np.uint8)
        cv2.circle(m, (int(x / f), int(y / f)), int(r / f), 1, -1)
        masks.append(m > 0)
    return masks


def segment(img_gray: np.ndarray, um_per_px: float, species: str | None, backend: str) -> list[np.ndarray]:
    if backend in ("fastsam", "sam"):
        masks = _ultralytics_masks(img_gray, backend)
    elif backend == "circles":
        masks = _circle_masks(img_gray, um_per_px, species)
    else:
        raise ValueError(f"unknown backend {backend}")
    return _dedupe(masks)
