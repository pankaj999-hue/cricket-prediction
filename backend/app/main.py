# backend/app/main.py
"""Application factory: builds the FastAPI app, installs middleware and the
route routers. Kept deliberately thin — business logic lives in
services/, routers/, schemas.py, deps.py and platform modules below."""
import os
import sys

# Ensure `backend/` is on the path so `app.*` and `engine` import cleanly,
# regardless of where uvicorn is launched from.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import ENABLE_HSTS
from app.core.security_headers import SecurityHeadersMiddleware
from app.routers import auth, data, predict

# Serve the frontend (repo-root/frontend) at /
FRONTEND_DIR = os.path.join(os.path.dirname(BACKEND_DIR), "frontend")


def create_app() -> FastAPI:
    app = FastAPI(title="MATCHCALL Prediction Engine API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # CSP + XSS/transport security headers on every response; HSTS only over HTTPS.
    app.add_middleware(SecurityHeadersMiddleware, hsts=ENABLE_HSTS)

    app.include_router(auth.router)
    app.include_router(data.router)
    app.include_router(predict.router)

    if os.path.isdir(FRONTEND_DIR):
        app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

    return app


app = create_app()