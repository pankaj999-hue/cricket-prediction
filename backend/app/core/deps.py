# backend/app/deps.py
"""Shared FastAPI dependencies: auth resolves the current user from the Bearer
token, and the CSRF guard protects cookie-authenticated endpoints."""
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request

from app.config import ALLOWED_ORIGINS
from app.core.db import get_db_connection
from app.core.security import decode_access_token


async def current_user(request: Request) -> dict:
    """Resolve the logged-in user from the Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, email, name, is_active FROM users WHERE id = %s",
        (payload["sub"],),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row or not row[3]:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return {"id": str(row[0]), "email": row[1], "name": row[2]}


async def check_same_origin(request: Request) -> None:
    """CSRF guard for cookie-authenticated endpoints: block requests whose
    Origin/Referer does not match our host.

    Non-browser clients (no Origin) are allowed. When the app is served behind
    a reverse proxy (e.g. the Vercel rewrite that proxies Vercel's origin to
    this backend), the request Host differs from the browser's Origin — so an
    origin that matches any ALLOWED_ORIGINS entry is also accepted.
    """
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin:
        return
    host = request.headers.get("host", "")
    try:
        origin_netloc = urlparse(origin).netloc
    except ValueError:
        raise HTTPException(status_code=403, detail="Invalid Origin header.")

    if origin_netloc == host:
        return

    allowed = set()
    for o in ALLOWED_ORIGINS:
        try:
            allowed.add(urlparse(o).netloc)
        except ValueError:
            continue
    # Drop the port for comparison so `https://app.vercel.app` matches whether
    # or not a default port is present on each side.
    origin_host = origin_netloc.rsplit(":", 1)[0]
    if origin_host in allowed:
        return

    raise HTTPException(status_code=403, detail="Cross-origin request rejected.")