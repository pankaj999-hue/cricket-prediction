#!/usr/bin/env bash
# One-shot DB bootstrap for a fresh deployment (Railway etc.).
# Idempotent-ish: setup.py creates tables with IF NOT EXISTS; loaders upsert.
#
# Requires env: DATABASE_URL (Postgres). Set DATA_DIR if JSON lives elsewhere.
set -e

cd "$(dirname "$0")/backend"

echo "==> Installing deps"
python -m pip install --upgrade pip
python -m pip install -r requirement.txt

echo "==> Creating tables"
python -m app.database.setup

echo "==> Loading CPL matches (git-tracked data)"
python -m app.database.load_cpl_data || echo "WARN: CPL load failed"

echo "==> Rebuilding pre-computed stats"
python -m app.database.refresh_aggregation || echo "WARN: aggregation failed"

echo "==> Loading squads"
python -m app.database.load_squads || echo "WARN: squads failed"

echo "DONE. Note: IPL match data is gitignored; load IPL via a DB dump or DATA_DIR pointing to it."
