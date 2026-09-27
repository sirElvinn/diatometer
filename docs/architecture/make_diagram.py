"""
make_diagram.py - draws docs/architecture/architecture.html (an SVG architecture diagram).
Render it to PNG with render.mjs (headless Chrome), or open the HTML in a browser.

    python docs/architecture/make_diagram.py
"""
import os
from html import escape

W, H = 1600, 1000
INK, MUTED, LINE, ACCENT = "#15201e", "#5d6a67", "#d6d6cc", "#0d7a6b"
PAPER, CARD, TINT, PILL = "#f6f5f0", "#ffffff", "#eef6f3", "#e3eee9"
parts: list[str] = []


def text(x, y, s, size=15, weight=400, fill=INK, family="sans", anchor="start"):
    fam = "'IBM Plex Mono', monospace" if family == "mono" else "'IBM Plex Sans', sans-serif"
    parts.append(f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" font-weight="{weight}" '
                 f'fill="{fill}" text-anchor="{anchor}">{escape(s)}</text>')


def lines(x, y, rows, size=14.5, gap=21, fill=INK, weight=400):
    for i, r in enumerate(rows):
        text(x, y + i * gap, r, size, weight, fill)


def box(x, y, w, h, fill=CARD, stroke=LINE, r=14, dash=None, sw=1.5):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="{sw}"{d}/>')


def pill_rows(names, maxw):
    rows, cx = 1, 0
    for n in names:
        w = 7.0 * len(n) + 18
        if cx and cx + w > maxw:
            rows, cx = rows + 1, 0
        cx += w + 7
    return rows


def pills(x, y, names, maxw=10_000):
    cx, cy = x, y
    for n in names:
        w = 7.0 * len(n) + 18
        if cx > x and cx + w > x + maxw:
            cx, cy = x, cy + 28
        parts.append(f'<rect x="{cx}" y="{cy}" width="{w}" height="22" rx="11" fill="{PILL}"/>')
        text(cx + w / 2, cy + 15.5, n, 11.5, 500, ACCENT, "mono", "middle")
        cx += w + 7


def arrow(pts, dashed=False, color=INK):
    d = " ".join(f"{'M' if i == 0 else 'L'}{px},{py}" for i, (px, py) in enumerate(pts))
    dash = ' stroke-dasharray="7 6"' if dashed else ""
    parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.2"{dash} marker-end="url(#head)"/>')


def badge(x, y, n):
    parts.append(f'<circle cx="{x}" cy="{y}" r="14" fill="{ACCENT}"/>')
    text(x, y + 5, n, 14, 700, "#fff", anchor="middle")


# ---- title -------------------------------------------------------------------------------
text(48, 62, "DiatoMeter · architecture", 34, 700)
text(48, 94, "What happens between dropping in an SEM photo and getting a spreadsheet back", 17, 400, MUTED)

# ---- 1. browser --------------------------------------------------------------------------
box(48, 140, 290, 560)
text(70, 178, "Your browser", 21, 700)
text(70, 202, "React + TypeScript app, built with Vite", 14, 400, MUTED)
pages = [
    ("Analyze", ["drag & drop an SEM photo", "(+ the Hitachi .txt)"]),
    ("Result", ["clickable SVG outline for", "every shell, stats, tables"]),
    ("History", ["every past analysis,", "shareable links"]),
    ("Downloads", [".xlsx and .csv files"]),
]
py = 226
for title, rows in pages:
    hh = 38 + 20 * len(rows)
    box(68, py, 250, hh, fill=TINT, stroke="none", r=10)
    text(84, py + 26, title, 15.5, 600)
    lines(84, py + 48, rows, 13.5, 20, MUTED)
    py += hh + 12
pills(68, 636, ["react", "typescript", "vite"], 250)

# ---- 2. cloudflare -----------------------------------------------------------------------
box(390, 140, 240, 280)
text(410, 178, "diamometer.us", 21, 700)
text(410, 202, "Cloudflare Worker (free)", 14, 400, MUTED)
lines(410, 236, ["• streams every request", "   to the Modal server", "• forces https:// and", "   drops www.", "• domain from Porkbun,", "   DNS on Cloudflare"], 14, 22)
pills(410, 384, ["cloudflare-workers"], 210)

box(390, 444, 240, 256, fill="none", dash="6 6")
text(410, 474, "Why this setup?", 15.5, 600)
lines(410, 500, ["Free hosts give ~512 MB RAM;", "one dense photo needs ~2 GB.",
                 "Modal's free tier gives 4 GB", "and sleeps when idle ($0).",
                 "Its free plan has no custom", "domains, so a Cloudflare", "Worker serves diamometer.us."], 13.5, 21, MUTED)

# ---- 3. modal ----------------------------------------------------------------------------
box(680, 124, 872, 846, fill="#fbfbf8", stroke=ACCENT, sw=2)
text(704, 162, "Modal · serverless Python server", 21, 700)
text(704, 186, "2 CPU · 4 GB RAM · one container · sleeps when idle, wakes on the next visit", 14, 400, MUTED)
pills(1400, 146, ["modal", "python"])

box(704, 208, 824, 106)
text(724, 240, "FastAPI web server", 17, 700)
lines(724, 266, ["POST /api/analyze · GET /api/runs · GET /api/runs/{id} · .xlsx / .csv / .png downloads",
                 "also serves the built React app, so the whole site is one server"], 14, 21, MUTED)
pills(1440, 226, ["fastapi"])

box(704, 340, 824, 470)
text(724, 372, "Image-analysis pipeline", 17, 700)
text(724, 394, "one photo → every shell measured, in ~2–15 seconds", 14, 400, MUTED)
steps = [
    ("1  Read the ruler", ["µm per pixel from Phenom", "metadata, the Hitachi .txt,", "or the printed scale bar"], ["tesseract", "numpy"]),
    ("2  Sample type", ["44-number size fingerprint", "→ random forest (500 trees)", "Thaps · Didymo · fossil · unsure"], ["scikit-learn", "scikit-image"]),
    ("3  Outline everything", ["FastSAM traces every object;", "drop background and", "duplicate outlines"], ["fastsam", "ultralytics", "pytorch"]),
    ("4  Measure", ["length, width, area, angle,", "solidity, all converted", "to real micrometers"], ["scikit-image", "opencv"]),
    ("5  Name & grade", ["species from published sizes;", "intact / cracked /", "fragmented / partial; facing"], ["numpy"]),
    ("6  Pores & export", ["dark-spot finder when pores", "are ≥ 2 px wide; overlay", "image + spreadsheet"], ["scikit-image", "pandas", "opencv"]),
]
sx, sy, sw_, sh, gx, gy = 724, 414, 236, 176, 38, 28
for i, (t, rows, tags) in enumerate(steps):
    x = sx + (i % 3) * (sw_ + gx)
    y = sy + (i // 3) * (sh + gy)
    box(x, y, sw_, sh, fill=TINT, stroke="none", r=10)
    text(x + 16, y + 28, t, 15.5, 700)
    lines(x + 16, y + 52, rows, 13, 19, MUTED)
    pills(x + 14, y + sh - 36 - 28 * (pill_rows(tags, sw_ - 28) - 1), tags, sw_ - 28)
    if i % 3 < 2:
        arrow([(x + sw_ + 4, y + sh / 2), (x + sw_ + gx - 4, y + sh / 2)])
# 3 -> 4: down the right, back to the left
x3 = sx + 2 * (sw_ + gx) + sw_ / 2
arrow([(x3, sy + sh + 2), (x3, sy + sh + gy / 2), (sx + sw_ / 2, sy + sh + gy / 2), (sx + sw_ / 2, sy + sh + gy - 2)])

box(704, 830, 824, 130)
text(724, 862, "Storage", 17, 700)
text(724, 884, "a persistent Modal Volume, so history survives the server sleeping", 14, 400, MUTED)
lines(724, 914, ["one folder per analysis: original photo · preview.png · overlay.png · result.json · results.xlsx",
                 "+ a small SQLite index for History, rebuilt from those folders on wake-up"], 14, 21)
pills(1440, 846, ["sqlite"])

# ---- request flow ------------------------------------------------------------------------
arrow([(340, 262), (386, 262)])
badge(363, 240, "1")
arrow([(632, 262), (700, 262)])
badge(666, 240, "2")
arrow([(1116, 316), (1116, 336)])
badge(1146, 327, "3")
arrow([(1116, 812), (1116, 826)])
badge(1146, 820, "4")
arrow([(700, 296), (636, 296)], dashed=True, color=ACCENT)
arrow([(386, 296), (344, 296)], dashed=True, color=ACCENT)
badge(666, 318, "5")

box(48, 724, 582, 246, fill=CARD)
text(70, 758, "One upload, step by step", 17, 700)
flow = [
    ("1", "You drop a photo on diamometer.us"),
    ("2", "The Cloudflare Worker passes it to Modal"),
    ("3", "FastAPI saves it and runs the 6-step pipeline"),
    ("4", "Results are saved to storage"),
    ("5", "JSON + images come back; the browser draws"),
    ("", "a clickable outline for every shell"),
]
for i, (n, s) in enumerate(flow):
    y = 792 + i * 29
    if n:
        badge(84, y - 5, n)
    text(108, y, s, 14.5)

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">'
       f'<defs><marker id="head" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" '
       f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="context-stroke"/></marker></defs>'
       f'<rect width="{W}" height="{H}" fill="{PAPER}"/>' + "".join(parts) + "</svg>")
html = ("<!doctype html><html><head><meta charset='utf-8'><title>DiatoMeter architecture</title>"
        "<link href='https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500&family=IBM+Plex+Sans:wght@400;600;700&display=swap' rel='stylesheet'>"
        "<style>html,body{margin:0;background:" + PAPER + "}svg{display:block;max-width:100%;height:auto}</style>"
        "</head><body>" + svg + "</body></html>")
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "architecture.html")
open(out, "w").write(html)
print("wrote", out)
