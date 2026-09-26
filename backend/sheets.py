"""
sheets.py - append every analysis to a public Google Sheet (tabs: images, frustules, pores).

Configure with environment variables (see README):
    GOOGLE_SHEET_ID               the id in the sheet's URL (.../spreadsheets/d/<ID>/edit)
    GOOGLE_SERVICE_ACCOUNT_JSON   path to the service-account key file, OR the JSON itself
    PUBLIC_URL                    optional, e.g. https://diatometer.example - used to put
                                  a clickable overlay link in each row

If either of the first two is missing, the app still works and simply skips the sheet.
"""
from __future__ import annotations

import json
import os
import threading

IMAGE_COLS = [
    "run_id", "uploaded_at", "filename", "sample_type", "sample_type_confidence",
    "sample_type_source", "p_Thalassiosira", "p_Didymosphenia", "p_Richmond",
    "n_frustules", "n_whole_in_frame", "n_intact", "n_cracked", "n_fragmented",
    "n_Thaps", "n_Didymo", "n_unknown_species", "median_length_um", "n_pores", "pore_note",
    "um_per_px", "scale_source", "scale_check", "backend", "seconds", "overlay_url",
]
FRUSTULE_COLS = [
    "run_id", "filename", "frustule_id", "species", "morphotype", "length_um", "width_um",
    "area_um2", "orientation_deg", "head_direction_deg", "view", "damage", "n_pores",
    "mean_pore_diameter_um", "median_pore_diameter_um", "x_um", "y_um", "equiv_diameter_um",
    "aspect_ratio", "circularity", "solidity", "touches_edge", "species_reason",
]
PORE_COLS = ["run_id", "filename", "frustule_id", "x_um", "y_um", "diameter_um"]
TABS = {"images": IMAGE_COLS, "frustules": FRUSTULE_COLS, "pores": PORE_COLS}

SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "").strip()
_KEY = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
PUBLIC_URL = os.environ.get("PUBLIC_URL", "").rstrip("/")

_lock = threading.Lock()
_book = None


def enabled() -> bool:
    return bool(SHEET_ID and _KEY)


def sheet_url() -> str | None:
    return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}" if SHEET_ID else None


def _workbook():
    global _book
    if _book is None:
        import gspread
        info = json.loads(_KEY) if _KEY.startswith("{") else json.load(open(_KEY))
        _book = gspread.service_account_from_dict(info).open_by_key(SHEET_ID)
    return _book


def _tab(name: str, cols: list[str]):
    import gspread
    book = _workbook()
    try:
        ws = book.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(name, rows=1000, cols=len(cols))
    if ws.row_values(1) != cols:
        ws.update([cols], "A1")
        ws.freeze(rows=1)
    return ws


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    return v


def append_run(run: dict) -> int:
    """Append one run's rows to the three tabs. Returns the number of rows written."""
    rid, fname, img = run["id"], run["filename"], run["image"]
    base = {"run_id": rid, "filename": fname}
    img_row = {**img, **base, "uploaded_at": run["created_at"],
               "overlay_url": f"{PUBLIC_URL}/api/runs/{rid}/overlay.png" if PUBLIC_URL else ""}
    rows = {
        "images": [img_row],
        "frustules": [{**f, **base} for f in run["frustules"]],
        "pores": [{**p, **base} for p in run["pores"]],
    }
    n = 0
    with _lock:
        for name, cols in TABS.items():
            if not rows[name]:
                continue
            ws = _tab(name, cols)
            ws.append_rows([[_cell(r.get(c)) for c in cols] for r in rows[name]],
                           value_input_option="RAW")
            n += len(rows[name])
    return n
