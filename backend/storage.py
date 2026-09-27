"""
storage.py - every analysis ("run") lives in DATA_DIR/runs/<run_id>/:

    original.<ext>   the uploaded file (plus the Hitachi .txt sidecar, if any)
    preview.png      the image with the info bar cropped, for the browser
    overlay.png      outlines coloured by damage + pores
    result.json      image summary, frustule rows, pore rows
    results.xlsx     the same tables as a spreadsheet

A small SQLite index (DATA_DIR/runs.db) makes the history list fast.
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
import threading
from datetime import datetime, timezone

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
RUNS_DIR = os.path.join(DATA_DIR, "runs")
os.makedirs(RUNS_DIR, exist_ok=True)

_DB = os.path.join(DATA_DIR, "runs.db")
_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB)
    c.row_factory = sqlite3.Row
    return c


with _conn() as c:
    c.execute("""CREATE TABLE IF NOT EXISTS runs (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        filename TEXT NOT NULL,
        sample_type TEXT,
        n_frustules INTEGER,
        n_pores INTEGER,
        seconds REAL,
        sheet_status TEXT
    )""")


def run_dir(run_id: str) -> str:
    return os.path.join(RUNS_DIR, run_id)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean(v):
    """JSON / Sheets-safe value: NaN, inf and numpy scalars become plain Python."""
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return v


def save_run(run_id: str, created_at: str, filename: str, image: dict,
             frustules: list[dict], pores: list[dict],
             outlines: dict[str, list] | None = None) -> None:
    """outlines: frustule_id -> list of polygons [[x, y], ...] in preview.png pixels."""
    image = {k: clean(v) for k, v in image.items()}
    frustules = [{k: clean(v) for k, v in r.items()} for r in frustules]
    pores = [{k: clean(v) for k, v in r.items()} for r in pores]
    with open(os.path.join(run_dir(run_id), "result.json"), "w") as fh:
        json.dump({"id": run_id, "created_at": created_at, "filename": filename,
                   "image": image, "frustules": frustules, "pores": pores,
                   "outlines": outlines or {}}, fh, separators=(",", ":"))
    with _lock, _conn() as c:
        c.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?,?)",
                  (run_id, created_at, filename, image.get("sample_type"),
                   image.get("n_frustules"), image.get("n_pores"), image.get("seconds"),
                   "pending"))


def set_sheet_status(run_id: str, status: str) -> None:
    with _lock, _conn() as c:
        c.execute("UPDATE runs SET sheet_status=? WHERE id=?", (status, run_id))


def load_run(run_id: str) -> dict | None:
    p = os.path.join(run_dir(run_id), "result.json")
    if not os.path.exists(p):
        return None
    with open(p) as fh:
        out = json.load(fh)
    with _conn() as c:
        row = c.execute("SELECT sheet_status FROM runs WHERE id=?", (run_id,)).fetchone()
    out["sheet_status"] = row["sheet_status"] if row else None
    return out


def list_runs(limit: int = 200) -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
