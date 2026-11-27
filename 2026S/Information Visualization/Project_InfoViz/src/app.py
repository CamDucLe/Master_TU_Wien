from __future__ import annotations

import json
import os
from pathlib import Path

from flask import Flask, abort, send_from_directory, request
from flask_compress import Compress
import random


SRC_DIR = Path(__file__).resolve().parent
ROOT = SRC_DIR.parent
DATA_FILE = ROOT / "data" / "processed" / "dashboard_data.json"
FALLBACK_DATA_FILE = ROOT / "data" / "processed" / "dashboard_data.sample.json"


def resolve_data_file() -> Path | None:
    if DATA_FILE.exists():
        return DATA_FILE
    if FALLBACK_DATA_FILE.exists():
        return FALLBACK_DATA_FILE
    return None

app = Flask(__name__, static_folder=str(SRC_DIR), static_url_path="/static")
Compress().init_app(app)


@app.get("/")
def index():
    return send_from_directory(SRC_DIR, "index.html")


@app.get("/api/dashboard-data")
def dashboard_data():
    resolved = resolve_data_file()
    if resolved is None:
        abort(
            404,
            description=(
                "Dashboard data not found. Run scripts/preprocess_steam_data.py first "
                "or provide --output data/processed/dashboard_data.json."
            ),
        )
    # Optionally return a sampled subset to reduce client load: use ?sample=N
    sample_param = request.args.get("sample")
    if sample_param:
        try:
            sample_n = int(sample_param)
            if sample_n <= 0:
                raise ValueError()
        except ValueError:
            abort(400, description="Invalid sample parameter")
        with resolved.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        games = payload.get("games", [])
        if len(games) <= sample_n:
            return payload
        sampled = random.sample(games, sample_n)
        return {"meta": payload.get("meta", {}), "games": sampled}

    with resolved.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload


@app.get("/health")
def health() -> tuple[dict[str, str], int]:
    return {"status": "ok"}, 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"Serving Flask dashboard from {SRC_DIR}")
    print(f"Open http://localhost:{port}/ in your browser")
    app.run(host="0.0.0.0", port=port, debug=False)
