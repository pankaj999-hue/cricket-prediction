# backend/app/services/auth.py
"""Authentication business logic: token-pair issuing/rotation, refresh-cookie
handling, and the register/login/refresh/logout flows. Routers only marshal
HTTP request/response around these functions."""
from datetime import datetime

from fastapi import HTTPException, Request, Response

from app.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_COOKIE_NAME,
    COOKIE_SECURE,
    COOKIE_SAMESITE,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from app.core.db import get_db_connection
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_expiry,
    verify_password,
)
from app.core.rate_limit import LOGIN_LOCKOUT


# ---------------------------------------------------------------------------
# Token + cookie helpers
# ---------------------------------------------------------------------------
def issue_token_pair(user: dict) -> dict:
    """Create an access token + a rotated refresh token, persist the refresh
    token (hashed) in Postgres, and return the pair (raw refresh for the
    cookie)."""
    raw_refresh = generate_refresh_token()
    access_token = create_access_token(user["id"])

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
        VALUES (%s, %s, %s)
        """,
        (user["id"], hash_refresh_token(raw_refresh), refresh_expiry()),
    )
    conn.commit()
    cur.close()
    conn.close()

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user,
    }


def set_refresh_cookie(response: Response, raw_refresh: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_refresh,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/",
        secure=COOKIE_SECURE,
        httponly=True,
        samesite=COOKIE_SAMESITE,
    )


def refresh_token_from_cookie(request: Request) -> str:
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token


# ---------------------------------------------------------------------------
# Flows
# ---------------------------------------------------------------------------
def register_account(email: str, password: str, name: str | None) -> dict:
    """Validate + insert a new user. Returns the user dict. Raises HTTP 400/409."""
    email = email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email is required.")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
    if cur.fetchone():
        cur.close()
        conn.close()
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    pwd_hash = hash_password(password)
    cur.execute(
        "INSERT INTO users (email, password_hash, name) VALUES (%s, %s, %s) RETURNING id, email, name",
        (email, pwd_hash, name.strip() if name else None),
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return {"id": str(row[0]), "email": row[1], "name": row[2]}


def login_account(email: str, password: str) -> dict:
    """Verify credentials, applying the per-account lockout. Returns the user
    dict on success; raises HTTP 401/429 on failure. Records lockout events."""
    email = email.strip().lower()

    if LOGIN_LOCKOUT.is_blocked(email):
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again later.")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, email, name, password_hash, is_active FROM users WHERE email = %s",
        (email,),
    )
    row = cur.fetchone()
    if not row or not verify_password(password, row[3]) or not row[4]:
        cur.close()
        conn.close()
        LOGIN_LOCKOUT.record_failure(email)
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    LOGIN_LOCKOUT.record_success(email)
    cur.execute("UPDATE users SET last_login = NOW() WHERE id = %s", (row[0],))
    conn.commit()
    cur.close()
    conn.close()

    return {"id": str(row[0]), "email": row[1], "name": row[2]}


def rotate_session(request: Request, response: Response):
    """Validate the refresh cookie, mint a new access+refresh pair, rotate the
    stored token (single-use). Returns (user, access_token). Raises 401."""
    token_hash = hash_refresh_token(refresh_token_from_cookie(request))
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, user_id, expires_at, revoked FROM refresh_tokens WHERE token_hash = %s",
        (token_hash,),
    )
    row = cur.fetchone()
    if not row or row[3] or row[2] < datetime.utcnow():
        cur.close()
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")

    cur.execute("SELECT id, email, name, is_active FROM users WHERE id = %s", (row[1],))
    u = cur.fetchone()
    if not u or not u[3]:
        cur.close()
        conn.close()
        raise HTTPException(status_code=401, detail="User no longer exists")
    user = {"id": str(u[0]), "email": u[1], "name": u[2]}

    new_pair = issue_token_pair(user)
    cur.execute("UPDATE refresh_tokens SET revoked = TRUE WHERE id = %s", (row[0],))
    conn.commit()
    cur.close()
    conn.close()

    set_refresh_cookie(response, new_pair["refresh_token"])
    return user, new_pair["access_token"]


def revoke_refresh(request: Request, user_id: str) -> None:
    """Revoke the refresh token carried by this request's cookie."""
    token_hash = hash_refresh_token(refresh_token_from_cookie(request))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE refresh_tokens SET revoked = TRUE WHERE user_id = %s AND token_hash = %s",
        (user_id, token_hash),
    )
    conn.commit()
    cur.close()
    conn.close()