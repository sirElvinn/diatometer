"""
scale.py - get the physical pixel size (um per pixel) for every SEM image in the
&hacks diatom dataset, WITHOUT hard-coding any pixel size.

Three sources, tried in order:
  1. Phenom SEM metadata  - XML embedded in the TIFF tag 34683 or in the JPEG bytes
                            (<pixelWidth unit="um">, <databarHeight>)
  2. Hitachi S-4700 sidecar .txt (same name as the image)
                            um/px = 127 mm / (Magnification * image width in px)
                            -> cross-checked against the dotted scale marker ticks
  3. OCR of the databar     - for screenshots with no metadata: read the field width
                            ("HFW", e.g. "43.7 um") and divide by the image width

Usage:
    python scale.py "path/to/2026 Hackathon" --out manifest.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import re
from dataclasses import dataclass, asdict

import numpy as np
from PIL import Image

IMG_EXT = (".jpg", ".jpeg", ".tif", ".tiff", ".png")


@dataclass
class ScaleInfo:
    path: str
    width_px: int
    height_px: int
    um_per_px: float | None
    databar_px: int          # rows at the bottom that are the info bar (crop these off)
    source: str              # phenom_xml | hitachi_txt | ocr_hfw | none
    microscope: str
    magnification: float | None = None
    check: str = ""          # cross-check result, if any


# ---------------------------------------------------------------- Phenom -----
def _phenom_xml(path: str) -> str | None:
    """Phenom stores an <FeiImage> XML block in TIFF tag 34683 and in JPEG EXIF."""
    raw = open(path, "rb").read()
    s = raw.find(b"<FeiImage")
    e = raw.find(b"</FeiImage>")
    if s == -1 or e == -1:
        return None
    return raw[s:e + len(b"</FeiImage>")].decode("utf-8", "ignore")


def _xml_value(xml: str, tag: str) -> str | None:
    m = re.search(rf"<{tag}\b[^>]*>([^<]+)</{tag}>", xml)
    return m.group(1).strip() if m else None


def _xml_unit(xml: str, tag: str) -> str | None:
    m = re.search(rf'<{tag}\b[^>]*unit="([^"]+)"', xml)
    return m.group(1) if m else None


_UNIT_TO_UM = {"m": 1e6, "mm": 1e3, "um": 1.0, "µm": 1.0, "nm": 1e-3}


def from_phenom(path: str, w: int, h: int) -> ScaleInfo | None:
    xml = _phenom_xml(path)
    if not xml:
        return None
    pw = _xml_value(xml, "pixelWidth")
    if pw is None:
        return None
    unit = _xml_unit(xml, "pixelWidth") or "um"
    um_per_px = float(pw) * _UNIT_TO_UM.get(unit, 1.0)
    bar = _xml_value(xml, "databarHeight")
    return ScaleInfo(path, w, h, um_per_px, int(bar) if bar else 0,
                     "phenom_xml", "Phenom")


# --------------------------------------------------------------- Hitachi -----
def _hitachi_txt(path: str) -> dict | None:
    txt = os.path.splitext(path)[0] + ".txt"
    if not os.path.exists(txt):
        return None
    d = {}
    for line in open(txt, encoding="latin-1"):
        if "=" in line:
            k, v = line.strip().split("=", 1)
            d[k.strip()] = v.strip()
    return d if "Magnification" in d else None


def _dark_databar_top(a: np.ndarray, thresh: float = 15) -> int:
    """First row (searching the bottom half) where the image turns into the black databar."""
    rm = a.mean(axis=1)
    for i in range(a.shape[0] // 2, a.shape[0]):
        if rm[i] < thresh and rm[i:i + 5].mean() < thresh * 2:
            return i
    return a.shape[0]


def _hitachi_marker_px(a: np.ndarray, top: int) -> float | None:
    """Span (px) between the first and last tick of the dotted micron marker."""
    band = a[top + 2: top + 14, :]
    prof = (band > 180).sum(axis=0)
    cols = np.where(prof >= 6)[0]
    if len(cols) == 0:
        return None
    ticks: list[list[int]] = []
    for c in cols:
        if ticks and c - ticks[-1][-1] <= 2:
            ticks[-1].append(int(c))
        else:
            ticks.append([int(c)])
    if len(ticks) < 5:
        return None
    centers = [float(np.mean(t)) for t in ticks]
    gaps = np.diff(centers)
    if gaps.std() > 0.15 * gaps.mean():
        return None                      # not an evenly spaced dotted marker (text, specks)
    return centers[-1] - centers[0]


def from_hitachi(path: str, w: int, h: int) -> ScaleInfo | None:
    d = _hitachi_txt(path)
    if not d:
        return None
    mag = float(d["Magnification"])
    # Hitachi magnification is defined for a 127 mm (5 in) wide photo
    um_per_px = 127_000.0 / (mag * w)
    a = np.array(Image.open(path).convert("L")).astype(int)
    top = _dark_databar_top(a)
    info = ScaleInfo(path, w, h, um_per_px, h - top, "hitachi_txt",
                     d.get("InstructName", "Hitachi"), magnification=mag)
    # independent check: the dotted marker spans MicronMarker nanometres
    span = _hitachi_marker_px(a, top)
    if span and "MicronMarker" in d:
        measured = float(d["MicronMarker"]) / 1000.0 / span
        diff = 100 * (measured - um_per_px) / um_per_px
        info.check = f"scale-bar ticks agree within {abs(diff):.1f}%"
    return info


# ------------------------------------------------------------------- OCR -----
def from_ocr(path: str, w: int, h: int) -> ScaleInfo | None:
    """Screenshots with no metadata: OCR the field width printed in the databar."""
    try:
        import pytesseract
        from PIL import ImageOps
    except ImportError:
        return None
    im = Image.open(path).convert("L")
    # Phenom scans are square, so a (resized) screenshot is W x W image + databar.
    if 0.03 * w < h - w < 0.12 * w:
        top = w
    else:  # otherwise: bottom block whose rows are mostly black
        a = np.array(im).astype(int)
        dark = (a < 40).mean(axis=1) > 0.6
        top = h
        while top > int(h * 0.75) and dark[top - 1]:
            top -= 1
    if h - top < 5:
        return None                     # no info bar at all -> nothing to read
    crop = im.crop((0, top, w, h))
    big = ImageOps.invert(crop.resize((crop.width * 4, crop.height * 4), Image.LANCZOS))
    try:
        text = " ".join(pytesseract.image_to_string(big, config="--psm 6").split())
    except (pytesseract.TesseractNotFoundError, pytesseract.TesseractError):
        return None                     # no Tesseract app installed -> ask the user instead
    # OCR misreads the micro sign as u / p / pu.
    unit_re = r"(\d+(?:\.\d+)?)\s*(p?[uµp]m|mm|nm)"
    to_um = {"mm": 1e3, "nm": 1e-3}

    # Hitachi image without its .txt: the dotted marker's label (e.g. "10.0um") is the
    # marker's length, so scale = label / measured tick span. Never divide it by the
    # image width - that made everything ~4x too small.
    a = np.array(im).astype(int)
    span = _hitachi_marker_px(a, _dark_databar_top(a))
    if span:
        labels = [(n, u) for n, u in re.findall(unit_re, text) if u != "mm"]  # mm = working distance
        if not labels:
            return None
        num, unit = labels[-1]                                # the marker label is printed last
        length_um = float(num) * to_um.get(unit, 1.0)
        return ScaleInfo(path, w, h, length_um / span, h - _dark_databar_top(a), "ocr_scale_bar",
                         "Hitachi (no .txt)",
                         check=f"measured the printed scale bar: {length_um:g} um over {span:.0f} px")

    # Phenom screenshot: only trust the field width printed right after the width icon,
    # which OCR reads as '<]' or '<['. Anything looser risks grabbing the scale-bar label.
    m = re.search(r"<\s*[\]\[\|{}]?\s*" + unit_re, text)
    if not m:
        return None                     # not sure -> the app asks the user for the scale
    num, unit = m.groups()
    hfw = float(num) * to_um.get(unit, 1.0)
    return ScaleInfo(path, w, h, hfw / w, h - top, "ocr_hfw", "Phenom (screenshot, no metadata)",
                     check=f"OCR read field width {hfw:g} um - verify by eye")


# ------------------------------------------------------------------- API -----
def read_scale(path: str) -> ScaleInfo:
    with Image.open(path) as im:
        w, h = im.size
    for fn in (from_phenom, from_hitachi, from_ocr):
        info = fn(path, w, h)
        if info and info.um_per_px:
            return info
    return ScaleInfo(path, w, h, None, 0, "none", "unknown",
                     check="no scale found - ask user to click the scale bar")


def crop_databar(img: Image.Image, info: ScaleInfo) -> Image.Image:
    """Return the image area only (info bar removed)."""
    return img.crop((0, 0, img.width, img.height - info.databar_px))


# ------------------------------------------------------ labels from paths -----
def weak_labels(rel_path: str) -> dict:
    """Species / treatment hints from folder and file names (confirm with the lab)."""
    p = rel_path.lower()
    if "thaps" in p:
        species, morph = "Thalassiosira pseudonana", "centric"
    elif "lab grown" in p or "rich_harv" in p or "richharv" in p:
        species, morph = "unknown pennate (ask lab)", "pennate"
    elif "didy" in p:
        species, morph = "Didymosphenia geminata", "pennate"
    elif "richmond" in p or "ams_rich" in p:
        species, morph = "Richmond fossil diatomite (mixed)", "mixed"
    else:
        species, morph = "unknown", "unknown"
    treatments = [t for t in ("raw", "dried", "scraped", "tga", "cultjar", "precip",
                              "sint", "acid", "burn", "lab grown")
                  if t in p]
    return {"species_hint": species, "morphotype_hint": morph,
            "treatment_hint": "+".join(treatments) or "unspecified"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--out", default="manifest.csv")
    args = ap.parse_args()

    rows = []
    for dirpath, _, files in os.walk(args.root):
        for f in sorted(files):
            if not f.lower().endswith(IMG_EXT):
                continue
            path = os.path.join(dirpath, f)
            rel = os.path.relpath(path, args.root)
            info = read_scale(path)
            row = asdict(info)
            row["path"] = rel
            row["folder"] = rel.split(os.sep)[0]
            row["field_width_um"] = round(info.um_per_px * info.width_px, 2) if info.um_per_px else None
            row.update(weak_labels(rel))
            rows.append(row)

    cols = ["path", "folder", "species_hint", "morphotype_hint", "treatment_hint",
            "microscope", "source", "magnification", "width_px", "height_px",
            "databar_px", "um_per_px", "field_width_um", "check"]
    with open(args.out, "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        wr.writeheader()
        wr.writerows(rows)
    print(f"wrote {len(rows)} rows -> {args.out}")


if __name__ == "__main__":
    main()
