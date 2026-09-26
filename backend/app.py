"""
app.py - DiatoMeter web API.

    uvicorn app:app --reload --port 8000        (from the backend/ folder)

POST /api/analyze            upload an SEM image (+ optional Hitachi .txt) -> full result
GET  /api/runs               history (newest first)
GET  /api/runs/{id}          one result: image summary, frustules, pores
GET  /api/runs/{id}/{file}   preview.png | overlay.png | results.xlsx | frustules.csv | pores.csv
GET  /api/config             Google Sheet link + whether syncing is on
Anything else serves the built React app (frontend/dist) when it exists.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import threading
import traceback
import uuid

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "pipeline"))

from run import process, species_reference  # noqa: E402
from scale import IMG_EXT  # noqa: E402

import sheets  # noqa: E402
import storage  # noqa: E402

MAX_UPLOAD_MB = 60
SAMPLE_TYPES = {"auto", "thaps", "didymo", "mixed"}
BACKENDS = {"fastsam", "circles"}
FILES = {"preview.png", "overlay.png", "results.xlsx", "frustules.csv", "pores.csv"}

app = FastAPI(title="DiatoMeter")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_pipeline_lock = threading.Lock()   # FastSAM + the CPU are shared: one image at a time


def _safe_name(name: str) -> str:
    base = os.path.basename(name or "image")
    return re.sub(r"[^A-Za-z0-9._ -]", "_", base)[:120] or "image"


def _write_tables(folder: str, run: dict) -> None:
    img = pd.DataFrame([run["image"]])
    fr = pd.DataFrame(run["frustules"])
    po = pd.DataFrame(run["pores"], columns=["frustule_id", "x_um", "y_um", "diameter_um"])
    fr.to_csv(os.path.join(folder, "frustules.csv"), index=False)
    po.to_csv(os.path.join(folder, "pores.csv"), index=False)
    with pd.ExcelWriter(os.path.join(folder, "results.xlsx")) as xw:
        img.T.reset_index().rename(columns={"index": "field", 0: "value"}).to_excel(
            xw, sheet_name="image", index=False)
        fr.to_excel(xw, sheet_name="frustules", index=False)
        po.to_excel(xw, sheet_name="pores", index=False)
        if len(fr):
            pd.crosstab(fr["species"], fr["damage"], margins=True, margins_name="total").to_excel(
                xw, sheet_name="summary")
        species_reference().to_excel(xw, sheet_name="literature sizes", index=False)


def _sync_sheet(run: dict) -> None:
    try:
        n = sheets.append_run(run)
        storage.set_sheet_status(run["id"], f"synced ({n} rows)")
    except Exception as e:  # never let the sheet break an analysis
        traceback.print_exc()
        storage.set_sheet_status(run["id"], f"failed: {type(e).__name__}: {e}"[:300])


@app.get("/api/config")
def config():
    return {"sheets_enabled": sheets.enabled(), "sheet_url": sheets.sheet_url()}


@app.post("/api/analyze")
def analyze(image: UploadFile = File(...),
            sidecar: UploadFile | None = File(None),
            sample_type: str = Form("auto"),
            backend: str = Form("fastsam"),
            um_per_px: float | None = Form(None)):
    if sample_type not in SAMPLE_TYPES:
        raise HTTPException(400, f"sample_type must be one of {sorted(SAMPLE_TYPES)}")
    if backend not in BACKENDS:
        raise HTTPException(400, f"backend must be one of {sorted(BACKENDS)}")
    if um_per_px is not None and not (0 < um_per_px < 100):
        raise HTTPException(400, "µm per pixel must be between 0 and 100")
    fname = _safe_name(image.filename)
    if not fname.lower().endswith(IMG_EXT):
        raise HTTPException(400, f"Unsupported file type. Use one of: {', '.join(IMG_EXT)}")

    run_id = uuid.uuid4().hex[:12]
    folder = storage.run_dir(run_id)
    os.makedirs(folder)
    try:
        return _analyze(run_id, folder, fname, image, sidecar, sample_type, backend, um_per_px)
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise


def _analyze(run_id, folder, fname, image, sidecar, sample_type, backend, um_per_px):
    stem, ext = os.path.splitext(fname)
    path = os.path.join(folder, "original" + ext.lower())
    data = image.file.read()
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {MAX_UPLOAD_MB} MB")
    with open(path, "wb") as fh:
        fh.write(data)
    if sidecar is not None and sidecar.filename:
        # scale.py looks for <image name>.txt next to the image (Hitachi S-4700)
        with open(os.path.join(folder, "original.txt"), "wb") as fh:
            fh.write(sidecar.file.read())

    try:
        Image.open(path).verify()
    except Exception:
        raise HTTPException(400, "That file could not be opened as an image")

    with _pipeline_lock:
        try:
            shells, pores, img_row = process(path, fname, backend, folder, sample_type,
                                             um_per_px=um_per_px, overlay_name="overlay.png")
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(500, f"Analysis failed: {type(e).__name__}: {e}")

    if not img_row.get("um_per_px"):
        raise HTTPException(422, "NO_SCALE: couldn't find the scale in this file. Upload the "
                                 "original TIFF, add the Hitachi .txt file, or type µm per pixel.")

    # move overlay out of the overlays/ subfolder and make a browser-friendly preview
    ov = img_row.pop("overlay")
    os.replace(ov, os.path.join(folder, "overlay.png"))
    os.rmdir(os.path.dirname(ov))
    w, h = Image.open(os.path.join(folder, "overlay.png")).size
    Image.open(path).convert("L").crop((0, 0, w, h)).save(os.path.join(folder, "preview.png"))
    img_row.update(width_px=w, height_px=h)

    created = storage.now_iso()
    storage.save_run(run_id, created, fname, img_row, shells, pores)
    run = storage.load_run(run_id)
    _write_tables(folder, run)
    if sheets.enabled():
        threading.Thread(target=_sync_sheet, args=(run,), daemon=True).start()
    else:
        storage.set_sheet_status(run_id, "off")
    return storage.load_run(run_id)


@app.get("/api/runs")
def runs():
    return storage.list_runs()


@app.get("/api/runs/{run_id}")
def run(run_id: str):
    if not re.fullmatch(r"[0-9a-f]{12}", run_id):
        raise HTTPException(404)
    out = storage.load_run(run_id)
    if out is None:
        raise HTTPException(404, "No such run")
    return out


@app.get("/api/runs/{run_id}/{name}")
def run_file(run_id: str, name: str):
    if not re.fullmatch(r"[0-9a-f]{12}", run_id) or name not in FILES:
        raise HTTPException(404)
    p = os.path.join(storage.run_dir(run_id), name)
    if not os.path.exists(p):
        raise HTTPException(404)
    return FileResponse(p, filename=f"diatometer_{run_id}_{name}" if not name.endswith(".png") else None)


@app.get("/api/runs.xlsx")
def all_runs_xlsx():
    """Every run so far in one workbook (the offline twin of the Google Sheet)."""
    imgs, frs, pos = [], [], []
    for r in storage.list_runs(limit=100000):
        full = storage.load_run(r["id"])
        if not full:
            continue
        base = {"run_id": r["id"], "filename": r["filename"]}
        imgs.append({**base, "uploaded_at": r["created_at"], **full["image"]})
        frs += [{**base, **f} for f in full["frustules"]]
        pos += [{**base, **p} for p in full["pores"]]
    out = os.path.join(storage.DATA_DIR, "all_runs.xlsx")
    with pd.ExcelWriter(out) as xw:
        pd.DataFrame(imgs).to_excel(xw, sheet_name="images", index=False)
        pd.DataFrame(frs).to_excel(xw, sheet_name="frustules", index=False)
        pd.DataFrame(pos).to_excel(xw, sheet_name="pores", index=False)
    return FileResponse(out, filename="diatometer_all_runs.xlsx")


DIST = os.path.join(HERE, "..", "frontend", "dist")
if os.path.isdir(DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = os.path.join(DIST, path)
        if path and os.path.isfile(f) and os.path.realpath(f).startswith(os.path.realpath(DIST)):
            return FileResponse(f)
        return FileResponse(os.path.join(DIST, "index.html"))
