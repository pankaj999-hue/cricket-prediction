# backend/app/routers/auth.py
"""Authentication routes: register, login, refresh, logout, me."""
from fastapi import APIRouter, Depends, Request, Response

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES
from app.core.deps import current_user, check_same_origin
from app.core.rate_limit import check_auth, check_login
from app.core.schemas import AuthResponse, LoginRequest, RefreshResponse, RegisterRequest
from app.services.auth import (
    register_account,
    login_account,
    rotate_session,
    revoke_refresh,
    set_refresh_cookie,
    clear_refresh_cookie,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _issue_auth_response(user, response: Response) -> AuthResponse:
    """Helper: set the refresh cookie and return the access-token response."""
    from app.services.auth import issue_token_pair

    pair = issue_token_pair(user)
    set_refresh_cookie(response, pair["refresh_token"])
    return AuthResponse(access_token=pair["access_token"], user=pair["user"])


@router.post("/register", response_model=AuthResponse,
             dependencies=[Depends(check_auth)])
def register(req: RegisterRequest, response: Response):
    user = register_account(req.email, req.password, req.name)
    return _issue_auth_response(user, response)


@router.post("/login", response_model=AuthResponse,
             dependencies=[Depends(check_login)])
async def login(req: LoginRequest, response: Response):
    user = login_account(req.email, req.password)
    return _issue_auth_response(user, response)


@router.post("/refresh", response_model=RefreshResponse,
             dependencies=[Depends(check_auth), Depends(check_same_origin)])
async def refresh(request: Request, response: Response):
    """Exchange the HttpOnly refresh cookie for a new access token + rotated
    refresh cookie. Single-use: the presented token is revoked server-side."""
    user, access_token = rotate_session(request, response)
    return RefreshResponse(
        access_token=access_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user,
    )


@router.post("/logout", dependencies=[Depends(check_auth), Depends(check_same_origin)])
async def logout(request: Request, response: Response, user: dict = Depends(current_user)):
    revoke_refresh(request, user["id"])
    clear_refresh_cookie(response)
    return {"ok": True}


@router.get("/me", dependencies=[Depends(check_auth)])
async def me(current=Depends(current_user)):
    return current