# DiatoMeter: one container = FastAPI backend + built React frontend.
# Works on Hugging Face Spaces (Docker SDK, port 7860), Render, Railway, DigitalOcean, ...

# ---- 1. build the React app ------------------------------------------------------------
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- 2. Python runtime -----------------------------------------------------------------
FROM python:3.12-slim

# tesseract: reads the printed field width on screenshots; libgl/glib: OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces runs containers as uid 1000
RUN useradd -m -u 1000 app
ENV HOME=/home/app \
    PYTHONUNBUFFERED=1 \
    YOLO_CONFIG_DIR=/home/app/.config/Ultralytics \
    DATA_DIR=/home/app/data \
    PORT=7860
WORKDIR /home/app/diatometer

# CPU-only PyTorch first (much smaller than the default CUDA build)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY --chown=app:app backend/ backend/
COPY --chown=app:app --from=web /web/dist frontend/dist

USER app
# fetch the FastSAM weights at build time so the first upload isn't slow
RUN python -c "from ultralytics import FastSAM; FastSAM('backend/pipeline/FastSAM-s.pt')"

EXPOSE 7860
CMD uvicorn app:app --app-dir backend --host 0.0.0.0 --port ${PORT}
