# backend/app/config.py
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/cricket_predictor")

# JWT
SECRET_KEY = os.getenv("SECRET_KEY", "default-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "14"))

# Refresh-token cookie
REFRESH_COOKIE_NAME = "matchcall_refresh"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() in ("1", "true", "yes")
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")

# Transport security / headers
ENABLE_HSTS = os.getenv("ENABLE_HSTS", "false").lower() in ("1", "true", "yes")