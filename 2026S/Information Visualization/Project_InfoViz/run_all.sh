uv sync

source .venv/bin/activate

python scripts/dataset_download.py
python scripts/preprocess_steam_data.py
python3 src/app.py
