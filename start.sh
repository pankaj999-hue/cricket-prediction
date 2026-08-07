#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/backend"

# Resolve a python interpreter (Railpack images expose python, py, or python3).
PY=""
for c in python python3 py; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "ERROR: no python interpreter found on PATH"
  echo "PATH=$PATH"
  which python3 || true
  ls /usr/bin/python* /usr/local/bin/python* 2>/dev/null || true
  exit 1
fi
echo "Using interpreter: $PY"

# Build Python deps from the root requirements (Railpack detection) or backend copy.
"$PY" -m pip install --upgrade pip
"$PY" -m pip install -r "$(dirname "$0")/requirements.txt"

# Run the FastAPI app. Reads DATABASE_URL / SECRET_KEY from env (set in Railway).
exec "$PY" -m uvicorn app.main:app --app-dir . --host 0.0.0.0 --port "${PORT:-8000}"