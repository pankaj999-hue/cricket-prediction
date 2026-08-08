# backend/app/routers/subscribe.py
"""Subscribe/unsubscribe to match-toss email alerts."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.deps import check_same_origin
from app.services.subscribe import subscribe, unsubscribe

router = APIRouter(prefix="/api", tags=["subscribe"])


class SubscribeRequest(BaseModel):
    email: str
    league: str = "CPL"


class SubscribeResponse(BaseModel):
    ok: bool = True
    email: str
    league: str


@router.post("/subscribe", response_model=SubscribeResponse,
             dependencies=[Depends(check_same_origin)])
def do_subscribe(req: SubscribeRequest):
    row = subscribe(req.email, req.league)
    return SubscribeResponse(email=row["email"], league=row["league"])


@router.post("/unsubscribe", response_model=SubscribeResponse,
             dependencies=[Depends(check_same_origin)])
def do_unsubscribe(req: SubscribeRequest):
    unsubscribe(req.email)
    return SubscribeResponse(email=req.email, league=req.league)