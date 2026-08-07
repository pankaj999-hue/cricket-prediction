#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/backend"

# Build Python deps from the (misspelled) requirements file.
python -m pip install --upgrade pip
python -m pip install -r requirement.txt

# Run the FastAPI app. Reads DATABASE_URL / SECRET_KEY from env (set in Railway).
exec python -m uvicorn app.main:app --app-dir . --host 0.0.0.0 --port "${PORT:-8000}"