"""
modal_app.py - host DiatoMeter on Modal (free Starter plan: $30/month of compute, no card).

    pip install modal
    modal setup                                   # once: log in through the browser
    cd frontend && npm run build && cd ..         # the built React app is uploaded as-is
    modal deploy modal_app.py                     # prints https://<workspace>--diatometer-web.modal.run

The container sleeps when idle (so it costs nothing) and wakes on the next visit in ~20-30 s.
Uploaded images and results persist in the Modal Volume "diatometer-data".
Optional Google Sheet sync: create a Modal secret named "diatometer-sheets" with
GOOGLE_SHEET_ID / GOOGLE_SERVICE_ACCOUNT_JSON / PUBLIC_URL and deploy with WITH_SHEETS=1.
"""
import os

import modal

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/root/diatometer"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("tesseract-ocr", "libgl1", "libglib2.0-0")
    .pip_install("torch", "torchvision", index_url="https://download.pytorch.org/whl/cpu")
    .pip_install_from_requirements(os.path.join(HERE, "backend", "requirements.txt"))
    .env({"DATA_DIR": "/data", "DB_PATH": "/tmp/runs.db", "YOLO_CONFIG_DIR": "/tmp/Ultralytics"})
    .add_local_dir(os.path.join(HERE, "backend"), f"{ROOT}/backend", copy=True,
                   ignore=["data", "data/**", "**/*.pt", "**/__pycache__"])
    # bake the FastSAM weights into the image so the first upload isn't slow
    .run_commands(f"cd {ROOT} && python -c \"from ultralytics import FastSAM; "
                  f"FastSAM('backend/pipeline/FastSAM-s.pt')\"")
    .add_local_dir(os.path.join(HERE, "frontend", "dist"), f"{ROOT}/frontend/dist")
)

volume = modal.Volume.from_name("diatometer-data", create_if_missing=True)
secrets = [modal.Secret.from_name("diatometer-sheets")] if os.environ.get("WITH_SHEETS") else []

app = modal.App("diatometer")


@app.function(
    image=image,
    cpu=2,
    memory=4096,              # one dense image peaks at ~2.1 GB
    volumes={"/data": volume},
    secrets=secrets,
    max_containers=1,         # one FastSAM model, one results index
    scaledown_window=600,     # stay awake 10 min after the last request, then sleep
    timeout=600,
)
@modal.concurrent(max_inputs=16)
@modal.asgi_app()
def web():
    import sys

    sys.path.insert(0, f"{ROOT}/backend")
    from app import app as fastapi_app

    return fastapi_app
