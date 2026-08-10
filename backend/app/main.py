# backend/app/main.py
"""Application factory: builds the FastAPI app, installs middleware and the
route routers. Kept deliberately thin — business logic lives in
services/, routers/, schemas.py, deps.py and platform modules below."""
import os
import sys
import threading
from contextlib import asynccontextmanager

# Ensure `backend/` is on the path so `app.*` and `engine` import cleanly,
# regardless of where uvicorn is launched from.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.config import ALLOWED_ORIGINS, ENABLE_HSTS
from app.core.security_headers import SecurityHeadersMiddleware
from app.routers import auth, data, predict, subscribe

# React frontend: the built Vite app lives in repo-root/frontend/dist.
# Falls back to serving the raw frontend dir when no build exists yet.
FRONTEND_DIR = os.path.join(os.path.dirname(BACKEND_DIR), "frontend")
FRONTEND_BUILD_DIR = os.path.join(FRONTEND_DIR, "dist")


def _start_toss_watcher(app: FastAPI) -> None:
    """Launch the background CPL toss poller as a daemon thread.

    Started unconditionally (not just in production): email sending self-guards
    on EMAIL_DISABLED / RESEND_API_KEY, and the poller is cheap when idle.
    Gating on ENVIRONMENT=production proved fragile (env var unset on Render),
    and a dead poller silently means no alerts.
    """
    from app.services.toss_watcher import run_forever
    from app.services.notify import EMAIL_DISABLED
    from app.config import RESEND_API_KEY

    thread = threading.Thread(target=run_forever, name="toss-watcher", daemon=True)
    thread.start()
    print(
        f"toss watcher: started (thread={thread.is_alive()}, "
        f"email={'disabled' if EMAIL_DISABLED else ('ready' if RESEND_API_KEY else 'no-key')})"
    )


def create_app() -> FastAPI:
    app = FastAPI(title="MATCHCALL Prediction Engine API")

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        _start_toss_watcher(_app)
        yield

    app.router.lifespan_context = lifespan

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # CSP + XSS/transport security headers on every response; HSTS only over HTTPS.
    app.add_middleware(SecurityHeadersMiddleware, hsts=ENABLE_HSTS)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """Turn any unhandled exception into a JSON 500 instead of a raw HTML
        traceback (HTTPException and its 4xx/5xx subclasses keep their own handler)."""
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    app.include_router(auth.router)
    app.include_router(data.router)
    app.include_router(predict.router)
    app.include_router(subscribe.router)

    @app.get("/api/toss-watcher/status")
    def toss_watcher_status():
        """Diagnostic probe: is the poller thread alive and what did the last
        sweep report? Lets us confirm the background emailer is actually
        running on Render (needs ENVIRONMENT=production)."""
        from app.services.toss_watcher import status as tw_status
        return tw_status()

    @app.get("/api/toss-records")
    def toss_records(limit: int = 8):
        """Recently collected pitch/toss calls with win/loss results, plus
        live accuracy. Powers the Recent calls panel on the home page."""
        from app.services.subscribe import recent_records
        return recent_records(limit=max(1, min(limit, 50)))

    @app.get("/api/ticker")
    def ticker():
        """Next scheduled CPL match: teams, start IST, toss winner, playing XIs
        and the logged prediction (when available). Drives the homescreen
        announcement ticker. Results cached briefly so many browsers polling the
        ticker don't each hammer Cricbuzz."""
        import datetime
        import time as _time

        cache = getattr(ticker, "_cache", None)
        now = _time.time()
        if cache and now < cache[0]:
            return cache[1]
        ticker._cache = (now + 90, None)

        from app.services.cricbuzz import get_match_squads, get_toss, upcoming_matches
        from app.services.subscribe import get_alert_by_match
        from app.services.toss_watcher import VENUE_MAP

        IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

        def fmt_ist(start_ms):
            try:
                dt = datetime.datetime.fromtimestamp(float(start_ms) / 1000, tz=IST)
                return dt.strftime("%a %d %b %I:%M %p IST")
            except (TypeError, ValueError):
                return None

        entry = None
        for match in upcoming_matches()[:1]:
            mid = match.get("matchId")
            if not mid:
                continue
            team_a = (match.get("team1") or {}).get("teamName")
            team_b = (match.get("team2") or {}).get("teamName")
            ground = (match.get("venueInfo") or {}).get("ground")
            venue = VENUE_MAP.get(ground, ground) if ground else None

            toss = {}
            try:
                toss = get_toss(mid)
            except Exception:
                pass

            xi = {}
            try:
                squads = get_match_squads(mid)
                for s in squads:
                    names = [p["name"] for p in s.get("players", []) if p.get("name")]
                    if names:
                        xi[s.get("team")] = names
            except Exception:
                pass

            alert = None
            try:
                alert = get_alert_by_match(str(mid))
            except Exception:
                pass

            entry = {
                "match_id": str(mid),
                "team_a": team_a,
                "team_b": team_b,
                "venue": venue,
                "start_ist": fmt_ist(match.get("startDate")),
                "state": match.get("state"),
                "toss_winner": toss.get("tossWinnerName") if toss.get("tossWinnerName") else None,
                "toss_decision": toss.get("decision"),
                "playing_xi": xi,
                "prediction": alert,
            }
            break

        payload = {"match": entry}
        ticker._cache = (now + 90, payload)
        return payload

    _mount_frontend(app)

    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built React SPA at / with history-API fallback.

    API routes (@/api/...) are registered before this catch-all, so they keep
    priority. Anything else resolves against FRONTEND_BUILD_DIR (hashing-asset
    files, hero video, etc.); unknown client paths fall through to index.html
    so React Router can handle them (e.g. /login).
    """
    if not os.path.isdir(FRONTEND_DIR):
        return
    active = FRONTEND_BUILD_DIR if os.path.isdir(FRONTEND_BUILD_DIR) else FRONTEND_DIR

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")

        root = os.path.realpath(active)
        resolved = os.path.realpath(os.path.join(active, full_path))
        if (
            full_path
            and os.path.isfile(resolved)
            and (resolved == root or resolved.startswith(root + os.sep))
        ):
            return FileResponse(resolved)

        # History-API fallback for client routes (/, /login, …).
        last = full_path.rstrip("/").rsplit("/", 1)[-1]
        if "." in last:
            # A real file request that doesn't exist (e.g. the hero video is
            # intentionally absent) should 404 so media onError handlers fire,
            # not silently return the HTML shell.
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(os.path.join(active, "index.html"))


app = create_app()