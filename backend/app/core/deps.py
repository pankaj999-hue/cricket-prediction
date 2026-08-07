# backend/app/deps.py
"""Shared FastAPI dependencies: auth resolves the current user from the Bearer
token, and the CSRF guard protects cookie-authenticated endpoints."""
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request

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
    Origin/Referer does not match our host. Non-browser clients (no Origin)
    are allowed."""
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin:
        return
    host = request.headers.get("host", "")
    try:
        if urlparse(origin).netloc != host:
            raise HTTPException(status_code=403, detail="Cross-origin request rejected.")
    except ValueError:
        raise HTTPException(status_code=403, detail="Invalid Origin header.")