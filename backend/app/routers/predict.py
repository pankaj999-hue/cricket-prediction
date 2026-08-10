# backend/app/routers/predict.py
"""Prediction route: run the engine and persist the outcome."""
from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import current_user, check_same_origin
from app.core.rate_limit import check_predict
from app.core.schemas import PredictRequest, PredictResponse
from app.services.predictions import run_prediction, log_prediction

router = APIRouter(prefix="/api", tags=["predict"])

RESULT_KEYS = [
    "team_a", "team_b", "venue", "team_a_score", "team_b_score",
    "predicted_winner", "confidence", "no_bet", "point_gap",
    "key_factors", "layer_breakdown", "xi_note",
]


@router.post("/predict", response_model=PredictResponse,
             dependencies=[Depends(check_predict), Depends(check_same_origin)])
def predict(req: PredictRequest, user: dict = Depends(current_user)):
    if req.team_a == req.team_b:
        raise HTTPException(status_code=400, detail="team_a and team_b must be different.")

    result = run_prediction(req)
    resp = PredictResponse(**{k: result[k] for k in RESULT_KEYS})
    log_prediction(user["id"], req, result)
    return resp