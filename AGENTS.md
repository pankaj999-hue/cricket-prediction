# AGENTS.md

T20 cricket match-prediction app. Core is a 10-layer prediction engine (`backend/engine/`) that reads a Postgres DB populated from Cricsheet JSON (v1.2.0) match archives in `data/ipl_json/` and `data/cpl_json/`. A FastAPI web server (`backend/app/main.py`) exposes the engine over HTTP and serves the frontend (`frontend/`). The frontend is a **React app (Vite)** — a port of the old vanilla `index.html` + `css/style.css` + `js/app.js`. Components live in `frontend/src/components/`, pages in `frontend/src/pages/`, styles in `frontend/src/styles/` (imported straight through, class names unchanged).

Beyond request/response, the app runs a **background CPL poller** (`app/services/toss_watcher.py`) that scrapes Cricbuzz, runs the engine pre-match, emails subscribers, and auto-scores past calls.

## Run the web app

1. Build/run the React frontend (Node 18+):
   - Dev (hot reload, proxies `/api` → `http://127.0.0.1:8000`): `cd frontend; npm install; npm run dev` → http://localhost:5173
   - Production: `cd frontend; npm run build` (outputs `frontend/dist/`; `frontend/dist/` is committed — the build ships with the repo)
2. Serve the built app + API from FastAPI:
   ```powershell
   .venv\Scripts\Activate.ps1
   python -m uvicorn app.main:app --app-dir backend --port 8000
   ```
   Then open http://127.0.0.1:8000. `app/main.py` serves `frontend/dist/` (falls back to `frontend/` if no build exists) via a catch-all route that returns `index.html` for unknown paths — so React Router handles `/login` etc. API routes (`/api/*`), registered before the catch-all, keep priority; real-but-missing files (e.g. the intentionally absent hero video) 404 so `onError` handlers fire.

**`SECRET_KEY` must be set before boot**: `backend/app/config.py` raises at import if it's missing (no fallback). Put it in the root `.env` (gitignored). `DATABASE_URL` falls back to `postgresql://postgres:postgres@localhost:5432/cricket_predictor`.

API endpoints:
- `GET  /api/teams?league=IPL&season=2026` — distinct teams (includes squad names, so first-season franchises appear pre-match)
- `GET  /api/venues?league=IPL&season=2026` — distinct venues, always unioned with every venue the league has ever used (so a partially-loaded season can't starve the dropdown); CPL also unions debut grounds (`CPL_DEBUT_VENUES` in `services/predictions.py`)
- `GET  /api/team-strength?league=IPL&season=2026` — squad-strength leaderboard over the 2024–26 window only
- `POST /api/predict` — **requires auth (JWT) + same-origin + rate-limit**; body `{team_a, team_b, venue, league, pitch_type?, toss_winner?, toss_decision?, stage?, auto_xi?, team_a_xi?, team_b_xi?}` → engine result incl. `no_bet`. Validates team/venue names against the DB and returns 400 otherwise
- `POST /api/auth/register|login|refresh|logout`, `GET /api/auth/me` — register/login/refresh are unauthenticated
- `POST /api/subscribe` / `POST /api/unsubscribe` — toss-alert emails
- `POST /api/admin/ingest` (full Cricsheet match JSON) / `POST /api/admin/refresh` / `GET /api/admin/matches` — admin emails only (`ADMIN_EMAILS` in `.env`), same-origin enforced
- `GET  /api/ticker` — next CPL match + toss + playing XIs + stored prediction (90s in-memory cache)
- `GET  /api/toss-records` — recent scored calls + accuracy stats
- `GET  /api/toss-watcher/status` — poller thread/health probe

Interactive docs (`/docs`, `/openapi.json`) are disabled when `ENVIRONMENT=production`. The frontend fetches teams/venues live and passes the selected `pitch_type` (neutral/batting/bowling) from the pitch pills. Auth is the port of the old `js/auth.js`: access token in sessionStorage + HttpOnly rotating refresh cookie; `src/auth.jsx` exposes an `AuthProvider` (use `useAuth()` / `useApi()`), and `/login` redirects there when a request 401s.

## Setup order (all scripts connect to Postgres directly via psycopg2)

Run from repo root with the root `.venv` active:

1. `python backend/app/database/setup.py` — create tables from `schema.sql`
2. `python backend/app/database/load_data.py` — load IPL matches/players/deliveries
3. `python backend/app/database/load_cpl_data.py` — same for CPL
4. `python backend/app/database/refresh_aggregation.py` — rebuild pre-computed stat tables
5. `python backend/app/database/load_squads.py` — CPL 2026 squad names (needed for XI auto-fetch)

`data_load.sh` runs all five steps against `DATABASE_URL` for fresh deploys (used by Render's `preDeployCommand`). New CPL match JSONs can also go in through the admin panel (`POST /api/admin/ingest`) instead of re-running loaders.

## Verification / tests

Not pytest — plain scripts that hit the live DB / network and print a prediction:
- `python backend/test_engine.py` (IPL prediction)
- `python backend/test_cpl.py` (CPL prediction — passes `league='CPL'`)
- `python backend/test_match.py` (playing-XI fetch)
- `python backend/test_auto_xi.py` (end-to-end `/api/predict` path incl. Cricbuzz XI + cache; needs `SECRET_KEY` set)
- `python backend/test_cricbuzz_xi.py` (live-site scrape check, no DB)
- `python backend/backtest_accuracy.py [--no-bets-as-wrong]` — replays scored `toss_alerts` through the engine, reports per-match correct/wrong and "layer blame" for wrong calls

Requires a running Postgres with the DB loaded (steps 1–5 above). No linter/formatter config exists.

## Architecture

- `engine/predictor.predict_match(team_a, team_b, venue, ...)` orchestrates all 10 `engine/layers/layer*.py` modules; each returns `{team_a_points, team_b_points, max_points, advantage, details}`. `engine/predictor.py:168` sums the hard-coded `max_possible` denominator — update it when a layer's `MAX_POINTS` changes.
- **Gating (accurate-pick behavior):** Low-confidence matchups return `predicted_winner="No Bet"` (`no_bet=True`) via `GATE_LOW_CONFIDENCE`/`NO_BET_LABEL` in `engine/utils/constants.py`. CPL has a stricter medium threshold (`CONFIDENCE_MEDIUM_CPL=12` vs IPL `CONFIDENCE_MEDIUM=8`) — tuned so CPL medium calls don't land at coin-flip. Backtests measure call accuracy separately from the decline rate.
- **Pitch input:** `predict_match` accepts `pitch_type` (`'batting' | 'bowling' | 'neutral' | None`) passed live from the frontend. Layer 6 (`layer6_toss_conditions.py`) reads it to compute which lineup the pitch favors (batting vs bowling rating from `player_career_stats`) and compounds the toss: correct decision for the pitch rewards the toss winner, wrong call swings edge away. `venue_pitch_profile.pitch_type` in the DB is currently all NULL — pitch/soil data is meant to come from the frontend in real time.
- **Layer weights (tuned 2026, validated 2024–25):** L1 venue 9, L2 form 14, L3 win-contrib 13, L4 matchups 16, L5 H2H 6, L6 toss/pitch 8, L7 balance 8, L8 venue-specialists 14, L9 pressure 4, L10 fatigue 3 (total 95). Historical layers (L1/L5) were downweighted and given small-sample damping (pull toward 50-50) because they drove confident wrong calls on upsets. An Elo layer (layer11) was tried but HURT accuracy — do not re-add without re-testing.
- League is selected via a module global: `predict_match` sets `data_loader.LEAGUE` (default `'IPL'`, pass `league='CPL'` for CPL). Recency windows use `RECENT_SEASONS = ['2024','2025','2026']` (`engine/utils/data_loader.py`).
- Layer weights: trust each layer's own `MAX_POINTS` docstring, not `LAYER_WEIGHTS` in `engine/utils/constants.py` (its keys don't match the layer module names).
- **Request layer** (`app/services/predictions.run_prediction`): validates, resolves `auto_xi` via Cricbuzz, dedupes identical requests through an in-memory cache (TTL `PREDICTION_CACHE_SECONDS`=900), and caps concurrent engine runs at 2 (`PREDICTION_MAX_CONCURRENT`) — a cold-cache stampede would otherwise exhaust the 20-conn pool (503 when at capacity). Engine runs go through `data_loader`'s `ThreadedConnectionPool`; layer queries use `get_connection()`, whose `close()` returns to the pool.
- **Background CPL poller** (`app/services/toss_watcher.run_forever`, daemon thread from the FastAPI lifespan): scrapes Cricbuzz (series 12123) every `TOSS_POLL_INTERVAL`s. Pre-match (`PRE_MATCH_MINUTES` before start) it runs the engine on the scraped live XI and logs a call; once the toss lands it rebuilds + emails subscribers (Resend; no-op when `EMAIL_DISABLED`/no key). Finished matches are auto-scored (`No Bet` rows get `is_correct=NULL` — recorded but never counted as a call). **Finished matches with no alert get backfilled** (`_backfill_complete`): on a sleeping free-tier box a match's whole window can pass unobserved, so the poller rebuilds the call from the final toss + XI (no result leak) and scores it. Cricbuzz has no public JSON API — `app/services/cricbuzz.py` decodes embedded Next.js flight payloads (no API key); `get_match_info` prefers the fixture-shaped `matchInfo` block (teamName + venueInfo) and falls back to the series schedule when a match page embeds only the commentary variant.
- **Admin ingest** (`app/services/ingest.py`) is the only path that maps historical CPL franchise names to 2026 names (`TEAM_MAP`, e.g. Jamaica Tallawahs → Jamaica Kingsmen) so H2H/venue/aggregation queries still join. `toss_watcher.py` has its own small `TEAM_MAP` + `VENUE_MAP` for Cricbuzz names.

## Gotchas

- `schema.sql` is now in sync with the loaders (it has `matches.league`, `squads`, and the auth tables `users`/`refresh_tokens`/`prediction_logs`/`subscribers`/`toss_alerts`). If you change schema, update `schema.sql` AND the loaders — they are hand-written SQL and diverged once before.
- Venue-name normalization is copy-pasted in 3 places (`load_data.py`, `load_cpl_data.py`, `engine/utils/data_loader.py`). DB rows must use the canonical names from `data_loader.normalize_venue`, or layer queries (which re-normalize) silently return no data.
- `normalize_team_name` in `load_cpl_data.py` is dead code — never called. The CPL loader stores historical franchise names raw (Jamaica Tallawahs, St Lucia Zouks, …) so renamed 2026 squads won't join history unless ingested via the admin `TEAM_MAP` path. Same for `data_loader` — there is no team-normalizer there, so team names must match DB rows exactly.
- Loader scripts hardcode absolute Windows paths to `data/...` (`load_data.py:11`, `load_cpl_data.py:11`) — override with `DATA_DIR` / `DATA_DIR_CPL` env (or change) if the repo moves.
- Both `data/ipl_json/` and `data/cpl_json/` are tracked in git now (including the committed `frontend/dist/` build). `data/*/README.txt` maps match IDs to dates/teams. `data/players_ids.json` is currently untracked.
- Root `requirements.txt` mirrors `backend/requirement.txt` (misspelled, not "requirements") — needed for Railpack/Render Python detection; keep them in sync.
- `app/config.py` CORS always appends the Vercel prod origin (`PRODUCTION_FRONTEND_ORIGINS`) so cookie-auth endpoints work behind the Vercel `/api/*` proxy.
