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
    """Launch the background CPL toss poller as a daemon thread."""
    from app.config import ENVIRONMENT
    from app.services.toss_watcher import run_forever

    if ENVIRONMENT != "production":
        print("toss watcher: skipped (non-production env)")
        return

    thread = threading.Thread(target=run_forever, name="toss-watcher", daemon=True)
    thread.start()
    print("toss watcher: started (daemon thread)")


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