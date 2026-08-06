# AGENTS.md

T20 cricket match-prediction app. Core is a 10-layer prediction engine (`backend/engine/`) that reads a Postgres DB populated from Cricsheet JSON (v1.2.0) match archives in `data/ipl_json/` and `data/cpl_json/`. A FastAPI web server (`backend/app/main.py`) exposes the engine over HTTP and serves the frontend (`frontend/`), which was segregated from `frontend/one.html` into `index.html` + `css/style.css` + `js/app.js`.

## Run the web app

```powershell
.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --app-dir backend --port 8000
```

Then open http://127.0.0.1:8000 (serves `frontend/index.html`). API endpoints:
- `GET  /api/teams?league=IPL&season=2026` — distinct teams
- `GET  /api/venues?league=IPL&season=2026` — distinct venues
- `POST /api/predict` — body `{team_a, team_b, venue, league, pitch_type?, toss_winner?, toss_decision?, stage?}` → engine result incl. `no_bet`

The frontend fetches teams/venues live and passes the selected `pitch_type` (neutral/batting/bowling) from the pitch pills. `app/main.py` mounts `FRONTEND_DIR` (repo-root/frontend) at `/` via StaticFiles(html=True).

## Setup order (all scripts connect to Postgres directly via psycopg2)

Run from repo root with the root `.venv` active:

1. `python backend/app/database/setup.py` — create tables from `schema.sql`
2. `python backend/app/database/load_data.py` — load IPL matches/players/deliveries
3. `python backend/app/database/load_cpl_data.py` — same for CPL
4. `python backend/app/database/refresh_aggregation.py` — rebuild pre-computed stat tables
5. `python backend/app/database/load_squads.py` — CPL 2026 squad names (needed for XI auto-fetch)

DB connection: `DATABASE_URL` from root `.env` (gitignored); fallback `postgresql://postgres:postgres@localhost:5432/cricket_predictor` (`backend/app/config.py`).

## Verification / tests

Not pytest — plain scripts that hit the live DB and print a prediction:
- `python backend/test_engine.py` (IPL prediction)
- `python backend/test_cpl.py` (CPL prediction — passes `league='CPL'`)
- `python backend/test_match.py` (playing-XI fetch)

Requires a running Postgres with the DB loaded (steps 1–5 above). No linter/formatter config exists.

## Architecture

- `engine/predictor.predict_match(team_a, team_b, venue, ...)` orchestrates all 10 `engine/layers/layer*.py` modules; each returns `{team_a_points, team_b_points, max_points, advantage, details}`. `engine/predictor.py:156` sums the hard-coded `max_possible` denominator — update it when a layer's `MAX_POINTS` changes.
- **Gating (accurate-pick behavior):** Low-confidence matchups return `predicted_winner="No Bet"` (`no_bet=True`) via `GATE_LOW_CONFIDENCE`/`NO_BET_LABEL` in `engine/utils/constants.py`. Only High/Medium confidence games get a team call. Backtests measure call accuracy separately from the decline rate.
- **Pitch input:** `predict_match` accepts `pitch_type` (`'batting' | 'bowling' | 'neutral' | None`) passed live from the frontend. Layer 6 (`layer6_toss_conditions.py`) reads it to compute which lineup the pitch favors (batting vs bowling rating from `player_career_stats`) and compounds the toss: correct decision for the pitch rewards the toss winner, wrong call swings edge away. `venue_pitch_profile.pitch_type` in the DB is currently all NULL — pitch/soil data is meant to come from the frontend in real time.
- **Layer weights (tuned 2026, validated 2024–25):** L1 venue 9, L2 form 14, L3 win-contrib 13, L4 matchups 16, L5 H2H 6, L6 toss/pitch 8, L7 balance 8, L8 venue-specialists 14, L9 pressure 4, L10 fatigue 3 (total 95). Historical layers (L1/L5) were downweighted and given small-sample damping (pull toward 50-50) because they drove confident wrong calls on upsets. An Elo layer (layer11) was tried but HURT accuracy — do not re-add without re-testing.
- League is selected via a module global: `predict_match` sets `data_loader.LEAGUE` (default `'IPL'`, pass `league='CPL'` for CPL). Recency windows use `RECENT_SEASONS = ['2024','2025','2026']` (`engine/utils/data_loader.py`).
- Layer weights: trust each layer's own `MAX_POINTS` docstring, not `LAYER_WEIGHTS` in `engine/utils/constants.py` (its keys don't match the layer module names).

## Gotchas

- `schema.sql` is stale: the `matches.league` column and the `squads` table are used everywhere in code but missing from it. If you change schema, update `schema.sql` AND the loaders — they have already diverged.
- Venue-name normalization is copy-pasted in 3 places (`load_data.py`, `load_cpl_data.py`, `engine/utils/data_loader.py`). DB rows must use the canonical names from `data_loader.normalize_venue`, or layer queries (which re-normalize) silently return no data.
- `normalize_team_name` in `load_cpl_data.py` is dead code — never called. Historical CPL names (Jamaica Tallawahs, St Lucia Zouks, Barbados Royals, Trinidad & Tobago Red Steel, etc.) are stored raw, so renamed 2026 squads (Jamaica Kingsmen, Barbados Tridents) will not join to their history for H2H/venue/aggregation queries.
- Loader scripts hardcode absolute Windows paths to `data/...` (`load_data.py:11`, `load_cpl_data.py:11`) — change if the repo moves.
- `data/ipl_json/` is gitignored; `data/cpl_json/` is tracked. `data/*/README.txt` maps match IDs to dates/teams.
- Dependencies file is `backend/requirement.txt` (misspelled, not "requirements").
