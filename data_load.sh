#!/usr/bin/env bash
# One-shot DB bootstrap for a fresh deployment (Railway etc.).
# Idempotent-ish: setup.py creates tables with IF NOT EXISTS; loaders upsert.
#
# Requires env: DATABASE_URL (Postgres). DATA_DIR defaults to the repo's data/ dir.
# Set DATA_DIR externally to override where the JSON archives live.
set -e

cd "$(dirname "$0")/backend"
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
export DATA_DIR="${DATA_DIR:-$REPO_ROOT/data/ipl_json}"
export DATA_DIR_CPL="${DATA_DIR_CPL:-$REPO_ROOT/data/cpl_json}"

echo "==> Installing deps"
python -m pip install --upgrade pip
python -m pip install -r requirement.txt

echo "==> Creating tables"
python -m app.database.setup

echo "==> Loading IPL matches"
python -m app.database.load_data || echo "WARN: IPL load failed"

echo "==> Loading CPL matches"
python -m app.database.load_cpl_data || echo "WARN: CPL load failed"

echo "==> Rebuilding pre-computed stats"
python -m app.database.refresh_aggregation || echo "WARN: aggregation failed"

echo "==> Loading squads"
python -m app.database.load_squads || echo "WARN: squads failed"

echo "DONE. IPL + CPL data loaded."
