# backend/app/services/predictions.py
"""Prediction business logic: run the engine and persist the outcome."""
import json

from app.core.db import get_db_connection


def run_prediction(req) -> dict:
    """Execute the 10-layer engine for a PredictRequest and return its result."""
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