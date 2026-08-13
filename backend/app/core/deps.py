# backend/app/deps.py
"""Shared FastAPI dependencies: auth resolves the current user from the Bearer
token, and the CSRF guard protects cookie-authenticated endpoints."""
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request

from app.config import ALLOWED_ORIGINS, is_admin
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
    return {"id": str(row[0]), "email": row[1], "name": row[2], "is_admin": is_admin(row[1])}


async def require_admin(user: dict = Depends(current_user)) -> dict:
    """Restrict an endpoint to accounts on the ADMIN_EMAILS allowlist."""
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def check_same_origin(request: Request) -> None:
    """CSRF guard for cookie-authenticated endpoints: block requests whose
    Origin/Referer does not match our host.

    Non-browser clients (no Origin) are allowed. When the app is served behind
    a reverse proxy (e.g. the Vercel rewrite that proxies Vercel's origin to
    this backend), the request Host differs from the browser's Origin — so an
    origin that matches any ALLOWED_ORIGINS entry is also accepted.

    The Host header is NOT trusted blindly: it must itself resolve to a known
    host. Without that, an attacker who can control the Host header (or whose
    domain points at this server via DNS rebinding) could make Origin == Host
    and walk straight past the guard.
    """
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin:
        return
    host = request.headers.get("host", "")
    try:
        origin_netloc = urlparse(origin).netloc
    except ValueError:
        raise HTTPException(status_code=403, detail="Invalid Origin header.")

    # Known hosts we are willing to serve, without ports, so Vite's
    # localhost:5173, uvicorn's 127.0.0.1:8000 and the Vercel domain all match
    # regardless of whether a default port is present on each side.
    trusted_hosts = set()
    for o in ALLOWED_ORIGINS:
        try:
            trusted_hosts.add(urlparse(o).netloc.rsplit(":", 1)[0])
        except ValueError:
            continue

    host_host = host.rsplit(":", 1)[0]
    origin_host = origin_netloc.rsplit(":", 1)[0]

    # True same-origin: Origin matches Host AND the Host is one we know. The
    # Host-trust requirement is what kills the Host-spoofing / DNS-rebinding
    # bypass (attacker sends Host=evil.com, Origin=evil.com, which used to slip
    # past the old `origin_netloc == host` check).
    if origin_netloc == host and host_host in trusted_hosts:
        return

    # Reverse-proxy scenario (e.g. the Vercel rewrite): the backend sees the
    # browser's Origin as the frontend domain while Host is the backend's own
    # host. Accept a request whose ORIGIN is one of our configured frontends —
    # browsers set Origin truthfully, so an attacker's page (evil origin) can
    # never present it.
    if origin_host in trusted_hosts:
        return

    raise HTTPException(status_code=403, detail="Cross-origin request rejected.")