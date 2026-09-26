---
title: DiatoMeter
emoji: 🔬
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
---

# DiatoMeter

**SEM image in, measurements out.** Built at &hacks XII (William & Mary, Sept 26–27 2026) for the
W&M Nano & Biomaterials Lab, Challenge #1.

Upload a scanning-electron-microscope image of diatoms and DiatoMeter:

| The lab asked for | What you get |
| --- | --- |
| How many diatoms are in frame | frustule count, plus how many are fully inside the image |
| Which species | Thaps / Didymo / unknown, from literature sizes + a size-fingerprint model of the whole image |
| How large | length, width (Feret diameters), area, all in µm |
| Which way they face | valve (face-on) vs. girdle (side-on) view, long-axis angle, head-pole direction |
| How broken | intact / cracked / fragmented / cut off by the image edge |
| Pores | x, y and diameter of every pore in µm, when the magnification can resolve them |

Every result is kept (image, outlined overlay, spreadsheet) and appended to a **public Google Sheet**.

Everything is open-source and runs on a laptop CPU. The scale always comes from the image
(Phenom metadata, the Hitachi `.txt` sidecar, or OCR of the printed field width). It is never
a hard-coded pixel size. If none of those exist, the app asks the user to type µm per pixel.

## How it works

```
upload ─► read scale (µm/px) ─► crop info bar ─► predict sample type (random forest on a size fingerprint)
       ─► FastSAM outlines every object ─► drop objects the wrong size for the species
       ─► measure each outline (Feret length/width, area, angle, solidity)
       ─► species + damage from literature sizes and outline shape
       ─► pores: LoG blob detection sized from the literature pore range (skipped if < 2 px)
       ─► overlay PNG + xlsx/csv + Google Sheet rows
```

```
backend/
  app.py            FastAPI: upload, history, downloads; serves the built frontend
  storage.py        one folder per run + a SQLite index
  sheets.py         appends every run to the Google Sheet (images / frustules / pores tabs)
  pipeline/         the image analysis (scale, segment, measure, pores, species, sample_type)
frontend/           React + TypeScript (Vite): Analyze, Result and History pages
Dockerfile          one container for everything
```

## Run it locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd frontend && npm install && npm run build && cd ..
uvicorn app:app --app-dir backend --port 8000
```

Open http://localhost:8000. The first analysis downloads the FastSAM weights (23 MB) automatically.

For frontend development with hot reload, keep uvicorn running and in another terminal run
`cd frontend && npm run dev` (Vite proxies `/api` to port 8000).

Optional: `brew install tesseract` lets it read the scale off screenshots that have no metadata.

## Google Sheet setup (public spreadsheet)

The app works without this; it just skips the sheet.

1. In [Google Cloud Console](https://console.cloud.google.com/), create a project and enable the **Google Sheets API**.
2. Under **IAM & Admin → Service accounts**, create a service account, then **Keys → Add key → JSON**. A key file downloads.
3. Create a Google Sheet. Click **Share**, add the service account's email (`...@...iam.gserviceaccount.com`) as **Editor**,
   and set **General access** to **Anyone with the link → Viewer**. That makes it public.
4. Copy the sheet ID from its URL: `https://docs.google.com/spreadsheets/d/<THIS PART>/edit`.
5. Create a `.env` file in the repo root (it is git-ignored):

   ```
   GOOGLE_SHEET_ID=your-sheet-id
   GOOGLE_SERVICE_ACCOUNT_JSON=/absolute/path/to/key.json
   PUBLIC_URL=http://localhost:8000
   ```

6. Start the server with `uvicorn app:app --app-dir backend --port 8000 --env-file .env`.

The app creates `images`, `frustules` and `pores` tabs with headers on the first upload, and a
**Public sheet ↗** link appears in the header. Never commit the key file.

## Deploy (Hugging Face Spaces, free CPU)

1. Create a new Space at https://huggingface.co/new-space and pick **Docker → Blank**.
2. In the Space's **Settings → Variables and secrets**, add secrets:
   `GOOGLE_SHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON` (paste the whole JSON key file contents), and
   `PUBLIC_URL` (`https://<user>-<space>.hf.space`).
3. Push this repo to the Space:

   ```bash
   git remote add space https://huggingface.co/spaces/<user>/<space>
   git push space main
   ```

The front matter at the top of this README tells Spaces to build the `Dockerfile` and expose port 7860.
Free Spaces reset their disk on restart. The Google Sheet is the permanent record; the in-app
history only covers runs since the last restart. The same Dockerfile runs on Render, Railway or
DigitalOcean App Platform (they set `PORT` automatically).

## API

| Method | Path | |
| --- | --- | --- |
| POST | `/api/analyze` | multipart: `image`, optional `sidecar` (.txt), `sample_type` (auto/thaps/didymo/mixed), `backend` (fastsam/circles), `um_per_px` |
| GET | `/api/runs` | history, newest first |
| GET | `/api/runs/{id}` | image summary, frustule rows, pore rows |
| GET | `/api/runs/{id}/{file}` | `overlay.png`, `preview.png`, `results.xlsx`, `frustules.csv`, `pores.csv` |
| GET | `/api/runs.xlsx` | every run in one workbook |
| GET | `/api/config` | Google Sheet link |

## Known limitations

- Damage thresholds are first guesses. Didymo's "Coke bottle" outline scores low on solidity even when whole,
  and overlapping shells sometimes merge into one outline, so Didymo is over-graded as fragmented.
- Pores are only measured on close-ups. At 3,000× a Thaps pore is smaller than a pixel, so the app says
  "not measured" instead of guessing.
- The sample-type model scores 76% on held-out imaging sessions, and 91% when it is confident. Otherwise it answers "unsure".
