"""
deploy.py - publish DiatoMeter to a Hugging Face Space (free Docker CPU hardware).

    hf auth login                      # once, with a Write token
    python deploy.py                   # creates/updates https://huggingface.co/spaces/<you>/diatometer

Uploads the repo (minus venvs, node_modules, local data and model weights; the Docker
build fetches FastSAM itself) and sets PUBLIC_URL so Google Sheet rows link to overlays.
Google Sheet secrets, if you use them, are added in the Space settings (see README).
"""
from __future__ import annotations

import argparse
import os

from huggingface_hub import HfApi

HERE = os.path.dirname(os.path.abspath(__file__))
IGNORE = [
    ".git/*", ".venv/*", ".claude/*", "**/__pycache__/*", "**/.DS_Store",
    "backend/data/*", "**/*.pt", "frontend/node_modules/*", "frontend/dist/*",
    ".env", "**/service-account*.json", "deploy.py",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="diatometer")
    ap.add_argument("--private", action="store_true")
    a = ap.parse_args()

    api = HfApi()
    user = api.whoami()["name"]
    repo_id = f"{user}/{a.name}"
    api.create_repo(repo_id, repo_type="space", space_sdk="docker", private=a.private, exist_ok=True)
    host = f"https://{user}-{a.name}".lower().replace("_", "-") + ".hf.space"
    api.add_space_variable(repo_id, "PUBLIC_URL", host)
    api.upload_folder(repo_id=repo_id, repo_type="space", folder_path=HERE,
                      ignore_patterns=IGNORE, commit_message="Deploy DiatoMeter")
    print(f"Space: https://huggingface.co/spaces/{repo_id}")
    print(f"App:   {host}   (first build takes ~5-10 min)")


if __name__ == "__main__":
    main()
