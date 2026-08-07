# backend/app/schemas.py
"""Pydantic request/response models shared by the routers."""
from typing import Optional

from pydantic import BaseModel, Field

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    email: str
    password: str
    name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    user: dict


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    user: dict


# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------
class PredictRequest(BaseModel):
    team_a: str
    team_b: str
    venue: str
    stage: str = "League"
    league: str = "IPL"
    pitch_type: Optional[str] = Field(None, description="batting | bowling | neutral | None")
    toss_winner: Optional[str] = None
    toss_decision: Optional[str] = None
    team_a_xi: Optional[list] = None
    team_b_xi: Optional[list] = None


class PredictResponse(BaseModel):
    team_a: str
    team_b: str
    venue: str
    team_a_score: float
    team_b_score: float
    predicted_winner: str
    confidence: str
    no_bet: bool
    point_gap: float
    key_factors: list
    layer_breakdown: dict