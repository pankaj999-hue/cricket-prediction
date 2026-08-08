#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT/backend"

# Resolve a python interpreter (Railpack images expose python, py, or python3).
PY=""
for c in python python3 py; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "ERROR: no python interpreter found on PATH"
  echo "PATH=$PATH"
  exit 1
fi
echo "Using interpreter: $PY"

# Build the React frontend if the prebuilt bundle is missing (e.g. fresh clone
# before a commit that includes frontend/dist). Needed so FastAPI can serve a
# working app; fails loudly if Node isn't available.
if [ ! -f "$REPO_ROOT/frontend/dist/index.html" ]; then
  echo "frontend/dist not found — building frontend (requires node/npm)"
  ( cd "$REPO_ROOT/frontend" && npm ci && npm run build ) \
    || echo "ERROR: frontend build failed (no node/npm?). Commit frontend/dist or install Node."
fi

# Railpack pre-installs deps from the root requirements.txt into .venv.
# Ensure they're present just in case, then run the FastAPI app.
# Reads DATABASE_URL / SECRET_KEY from env (set in Railway).
"$PY" -m uvicorn app.main:app --app-dir . --host 0.0.0.0 --port "${PORT:-8000}"