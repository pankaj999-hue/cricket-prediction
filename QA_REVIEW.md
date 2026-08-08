# Quality Assurance Review — ANTARYAMI (Cricket Match Predictor)

- **Date:** 2026-08-08
- **Scope:** Full-stack review (backend FastAPI prediction engine + React/Vite frontend, DB ETL)
- **Method:** Code review, production build, live API exercises, engine test scripts against the live Postgres DB.

---

## 1. Executive summary

**Overall verdict: functional and well-architected, but NOT production-grade.**

The 10-layer prediction pipeline works end-to-end (IPL + CPL), gating (`No Bet` on low
confidence) behaves correctly, the frontend is a clean React port, and the auth/CSRF chain
is solid. However there are **2 critical data issues**, several security-hardening gaps, and
**quiet failure paths** that would mislead users or crash the app at scale.

---

## 2. What was verified live

| Check | Result |
|---|---|
| Frontend `npm run build` | ✓ passes (Vite 5) |
| `backend/test_engine.py` (IPL) | ✓ CSK 44.4% vs RCB 55.6%, **Medium**, no bet false |
| `backend/test_cpl.py` (CPL) | ✓ Jamaica 52.1% vs AF 47.9%, **No Bet / Low** (correct gating) |
| `backend/test_match.py` (XI fetch) | ✓ RCB + MI XIs fetched |
| `POST /api/register` → `POST /api/predict` (Bearer) | ✓ 200 with prediction |
| Same team_a == team_b | ✓ 400 with message |
| Cross-origin predict (Origin mismatch) | ✓ 403 "Cross-origin request rejected." |
| Login lockout after 5 bad attempts | ✓ 429 |
| CORS response headers | ✓ correct specific-origin echo |
| `GET /api/teams`, `/api/venues`, `/api/team-strength` | ✓ 200 (10 teams, 13 venues, 10 rows) |
| SPA fallback `GET /login` | ✓ 200 (React Router handles it) |
| Unknown `GET /api/*` | ✓ 404 |

---

## 3. Findings

### 🔴 CRITICAL

1. **Stale `schema.sql` breaks fresh installs.**
   The `matches.league` column and the `squads` table are used throughout the loaders,
   routers and engine (`backend/app/database/load_squads.py`, `engine/utils/data_loader.py:90`,
   `app/routers/data.py`) but are **missing from `schema.sql`**.
   - A clean `setup.py` produces a half-schema; seed scripts and `/api/teams` then fail.
   - The live DB works only because it was bootstrapped from a fuller schema.
   - Reference: AGENTS.md "Gotchas".

#### 2. Silent data-integrity failures — fabricated "50% win rate".
   Calling `/api/predict` with **nonexistent teams/venues returned a plausible-looking result
   instead of an error**:
   - `{team_a: "Fake Team One", team_b: "Fake Team Two", venue: "Unknown Ground", league: "IPL"}`
   → `No Bet · 49.5 vs 50.5`, including a key factor
     _"Venue advantage: Fake Team Two has **50.0%** win rate at this ground"_
     even though **0 matches** exist at that ground.
   - Root cause: `PredictRequest` accepts free-text `team_a/team_b/venue/league/stage` and only
     validates `team_a != team_b` (`backend/app/core/schemas.py`, `backend/app/routers/predict.py`).
   - A 50% win rate derived from an empty sample is fabricated data — worse than an error.

### 🟠 HIGH

#### 3. Fallback JWT secret.
    `config.py` falls back to `"default-secret-change-me"` when `SECRET_KEY` is unset
    (`backend/app/config.py:12`). On a deployment that forgets the env var, HS256 tokens can
    be forged by anyone. The real secret also sits in the repo `.env` (gitignored, but present
    on disk).

#### 4. Unhandled exceptions → raw 500s.
    `/api/predict` has no exception handler; any engine/DB failure produces a raw 500 with an
    HTML traceback instead of a JSON error. `log_prediction` is fail-silent on purpose but the
    pages it opens (layer code) are not shielded.

#### 5. Per-request DB connection explosion (no pooling).
    Layers, e.g. Layer 4 (`layer4_player_matchups.py`), open a
    `psycopg2.connect()` **per batter-vs-bowler pair**; a single `/predict` can open 30–100
    DB connections. No pooling anywhere (SQLAlchemy is listed in `requirement.txt` but never used).
    Under concurrent users this exhausts Postgres quickly.

#### 6. Wide-open CORS config.
    `allow_origins=["*"]` **with** `allow_credentials=True` (`backend/app/main.py:33-34`).
    It happens to work today because Starlette echoes the specific origin, but is a standing
    misconfiguration that browsers reject and invites cookie leakage if it ever behaves as
    intended. Should be pinned to the real frontend origins.

### 🟡 MEDIUM

#### 7. Venue/team normalization drift.
    - Venue-name normalization is copy-pasted in 3 places
      (`load_data.py`, `load_cpl_data.py`, `engine/utils/data_loader.py`).
    - Renamed 2026 CPL squads (Jamaica Kingsmen, Barbados Tridents) will **not join** their own
      historical H2H/venue rows because `normalize_team_name` in `load_cpl_data.py` is never called.
    - Effect: CPL model quality is weaker than IPL and CPL-matchup signals are silent.

#### 8. Refresh-token rotation is not atomic.
    `refresh` does SELECT-then-UPDATE across two DB connections
    (`backend/app/services/auth.py`); two concurrent `POST /api/auth/refresh` can both pass the
    checks → the single-use guarantee breaks. React 18 StrictMode double-mounting in dev
    reproduces this race.

#### 9. Rate limits are in-memory / per-process.
    `core/rate_limit.py` uses `threading.Lock` + in-process queues; multi-worker deployments get
    `N ×` the configured limits and limits are lost on restart.

#### 10. No real tests.
    `backend/test_*.py` print results but **assert nothing**; frontend has no tests and no
    linter. A regression could ship green.

### 🟢 LOW

- `Builder.jsx` `hint.err` never turns red — engine errors render as neutral text, not themed error color.
- Duplicate React keys in `Ticker.jsx` (track duplicated for marquee).
- `/api/teams` fetched twice on first load (`Home.jsx` boot + `loadData`).
- Double 401 redirect (`auth.jsx` then `api.js`) — can mislabel engine as "offline" when it's actually a stale session.
- Hero `<video src="/assets/hero-action.mp4">` — **the file does not exist** in `frontend/public/assets/` (only PNGs) → hero video is silently hidden on the live site.
- Login page enforces `password.length < 6` even for the login state, but the server only enforces 6+ at registration.
- Accessibility gaps: no `role="alert"`/`aria-live` on messages, tabs lack `aria-selected`, no `<table>` semantics for leaderboard/logs, marquee not `aria-hidden`, no focus management/skip link.
- Unused deps in `requirement.txt` (`sqlalchemy`, `pandas`, `numpy`, `cryptography`).

---

## 4. What works well

- **CSRF chain is genuinely good:** HttpOnly refresh cookie + `SameSite=lax` + Origin/`Host`
  guard + Bearer access token — verified that a cross-origin predict gets 403.
- **Account lockout + rate limits:** verified (5 bad logins → 429).
- **Low-confidence gating (`No Bet`):** prevents confident wrong picks on upsets — verified.
- **Clean React port:** no dead vanilla JS is served; `dist/` build is the only path.
- **Clear AGENTS.md** documenting the known divergences.

---

## 5. Recommended priority order

| # | Fix | Time est. |
|---|---|---|
| 1 | Bring `schema.sql` up to date (`league`, `squads`) | small |
| 2 | Validate team/venue/league against DB before predicting (return 400, not phantom 50%) | small |
| 3 | Add a global 500→JSON exception handler on `/api/predict` | small |
| 4 | Pool DB connections across layers | medium |
| 5 | Real `SECRET_KEY` env (no fallback); tighten CORS origins; `COOKIE_SECURE`/`HSTS` in prod | small |
| 6 | Atomic refresh-token rotation (single UPDATE ... RETURNING) | small |
| 7 | Add assertions to `test_*.py`; add ESLint + a smoke CI job | medium |

---

## 6. Fix status (2026-08-08)

| # | Finding | Status |
|---|---|---|
| 1 | Stale `schema.sql` (`matches.league`, `squads`) | ✅ Fixed — columns + table + index added to `schema.sql` |
| 2 | Silent phantom 50% predictions for unknown teams/venues | ✅ Fixed — `validate_predict_request` returns 400 (league/pitch/team/venue) |
| 3 | Fallback JWT secret | ✅ Fixed — `SECRET_KEY` now required; app refuses to boot without it |
| 4 | Raw 500 tracebacks | ✅ Fixed — global `Exception` handler → JSON 500 (HTTPException/4xx preserved) |
| 5 | Per-request DB connections | ✅ Fixed — `ThreadedConnectionPool` (1–20) in `engine/utils/data_loader.py` with a close-returns-to-pool wrapper; all 9 layer files + app code route through it |
| 6 | CORS `*` + credentials | ✅ Fixed — explicit `ALLOWED_ORIGINS` (config-driven); disallowed origins now get no ACAO header |
| 7 | Prod cookie/HSTS defaults | ✅ Fixed — `COOKIE_SECURE`/`ENABLE_HSTS` default on when `ENVIRONMENT=production` or a platform env is set |
| — | Frontend: hint error color | ✅ Fixed — `Builder.jsx` reads `hint.kind === 'err'` |
| — | Frontend: Ticker duplicate keys | ✅ Fixed — unique `a/b` keys + `aria-hidden` on marquee copy |
| — | Frontend: duplicate `/api/teams` on boot | ✅ Fixed — single `loadData` drives boot + engine status |
| — | Frontend: double 401 redirect | ✅ Fixed — `api.js` no longer re-navigates on 401 |

Verified live after fixes: bogus team → 400 `Unknown team`, bad league → 400, bad pitch → 400,
valid IPL predict → 200 (44.4 vs 55.6), CPL → No Bet, CORS allowed/disallowed correct,
cross-origin predict → 403, `test_engine.py`/`test_cpl.py`/`test_match.py` all green.

**Still open:** #7 venue/team normalization drift, #8 non-atomic refresh rotation, #9 in-memory
rate limits (multi-worker), #10 no real test assertions/linter. Not in the fixed scope above.

---

*This document is a point-in-time review, not a guarantee; re-run after the above fixes.*