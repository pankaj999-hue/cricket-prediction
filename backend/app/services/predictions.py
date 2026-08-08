# backend/app/services/predictions.py
"""Prediction business logic: run the engine and persist the outcome."""
import json

from fastapi import HTTPException

from app.core.db import get_db_connection

VALID_LEAGUES = ("IPL", "CPL")
VALID_PITCH_TYPES = ("batting", "bowling", "neutral")
CPL_DEBUT_VENUES = {"Arnos Vale Stadium, Kingstown"}


def run_prediction(req) -> dict:
    """Execute the 10-layer engine for a PredictRequest and return its result."""
    validate_predict_request(req)
    from engine.predictor import predict_match

    return predict_match(
        team_a=req.team_a,
        team_b=req.team_b,
        venue=req.venue,
        stage=req.stage,
        league=req.league,
        pitch_type=req.pitch_type,
        toss_winner=req.toss_winner,
        toss_decision=req.toss_decision,
        team_a_xi=req.team_a_xi,
        team_b_xi=req.team_b_xi,
    )


def validate_predict_request(req) -> None:
    """Reject malformed input up front instead of letting the engine silently
    produce a phantom near-50/50 prediction (a fabricated '50% win rate' from an
    empty sample looks worse than an error)."""
    if req.league not in VALID_LEAGUES:
        raise HTTPException(status_code=400, detail=f"league must be {', '.join(VALID_LEAGUES)}.")
    if req.pitch_type and req.pitch_type not in VALID_PITCH_TYPES:
        raise HTTPException(status_code=400, detail=f"pitch_type must be one of {', '.join(VALID_PITCH_TYPES)} or null.")

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT team_a FROM matches WHERE league = %s "
            "UNION SELECT DISTINCT team_b FROM matches WHERE league = %s "
            "UNION SELECT DISTINCT team FROM squads WHERE league = %s",
            (req.league, req.league, req.league),
        )
        teams = {row[0] for row in cur.fetchall()}
        cur.execute(
            "SELECT DISTINCT venue FROM matches WHERE league = %s",
            (req.league,),
        )
        venues = {row[0] for row in cur.fetchall()} | CPL_DEBUT_VENUES
        cur.close()
    finally:
        conn.close()

    if req.team_a not in teams:
        raise HTTPException(status_code=400, detail=f"Unknown team '{req.team_a}' for {req.league}.")
    if req.team_b not in teams:
        raise HTTPException(status_code=400, detail=f"Unknown team '{req.team_b}' for {req.league}.")
    if req.venue not in venues:
        raise HTTPException(status_code=400, detail=f"Unknown venue '{req.venue}' for {req.league}.")


def log_prediction(user_id: str, req, result: dict) -> None:
    """Persist a prediction to prediction_logs. Fail-silent: logging must never
    break the prediction response."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO prediction_logs
                (user_id, team_a, team_b, venue, format, predicted_winner,
                 team_a_score, team_b_score, confidence, layer_breakdown, key_factors)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id, req.team_a, req.team_b, req.venue, req.league,
                result.get("predicted_winner"), result.get("team_a_score"),
                result.get("team_b_score"), result.get("confidence"),
                _json(result.get("layer_breakdown")), _json(result.get("key_factors")),
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass


def _json(value):
    try:
        return json.dumps(value)
    except Exception:
        return None