# backend/app/config.py
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Environment (for prod-only hardening defaults)
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()


def _is_production() -> bool:
    on_platform = bool(os.getenv("RAILWAY_STATIC") or os.getenv("VERCEL"))
    return ENVIRONMENT == "production" or on_platform


# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/cricket_predictor")

# JWT — no fallback: an app booted without an explicit SECRET_KEY must fail
# loudly instead of silently using a known static key that anyone can forge HS256
# tokens with.
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY is not set. Set it in the environment (e.g. in .env) before starting the app."
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "14"))

# Refresh-token cookie
REFRESH_COOKIE_NAME = "matchcall_refresh"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true" if _is_production() else "false").lower() in ("1", "true", "yes")
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")

# Transport security / headers
ENABLE_HSTS = os.getenv("ENABLE_HSTS", "true" if _is_production() else "false").lower() in ("1", "true", "yes")

# Allowed CORS origins (dev Vite + the served app itself)
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000",
    ).split(",")
    if o.strip()
]