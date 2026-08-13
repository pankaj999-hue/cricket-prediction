# backend/app/services/predictions.py
"""Prediction business logic: run the engine and persist the outcome."""
import json
import threading
import time

from fastapi import HTTPException

from app.core.db import get_db_connection
from app.config import PREDICTION_CACHE_SECONDS

VALID_LEAGUES = ("IPL", "CPL")
VALID_PITCH_TYPES = ("batting", "bowling", "neutral")
CPL_DEBUT_VENUES = {"Arnos Vale Stadium, Kingstown", "Sabina Park, Kingston"}

# In-memory prediction cache. Two users requesting the same matchup + XIs land
# on the same key, so the second caller gets the engine's result without
# re-running the 10 layers or hammering the DB. Bounds: don't grow past
# MAX_ENTRIES by evicting oldest entries regardless of age.
PREDICTION_CACHE_MAX = 256

# Cap on how many 10-layer engine runs may be in flight at once. Each run is
# minutes-long and hammers the DB; without this cap a handful of concurrent
# cold-cache predicts exhausts the 20-connection pool and the whole API stops
# responding (trivial DoS). Requests beyond the cap get a fast 503 instead of
# queuing — their retry will hit the cache once the first run lands.
PREDICTION_MAX_CONCURRENT = 2
_PREDICTION_SEMAPHORE = threading.BoundedSemaphore(PREDICTION_MAX_CONCURRENT)


def _prediction_cache():
    """Lazily-built {key: (expires_at, result)} guarded by a lock."""
    bucket = getattr(_prediction_cache, "bucket", None)
    if bucket is None:
        lock = threading.Lock()
        with lock:
            if getattr(_prediction_cache, "bucket", None) is None:
                _prediction_cache.bucket = ({}, lock)
    return _prediction_cache.bucket


def _cache_key(req) -> str:
    """Stable key across all engine inputs. Lists (XIs) are order-insensitive
    since the order of the XI list shouldn't change the outcome."""
    def norm_xi(xi):
        return tuple(sorted(xi)) if xi else None
    return json.dumps(
        (
            req.team_a, req.team_b, req.venue, req.stage, req.league,
            req.pitch_type, req.toss_winner, req.toss_decision,
            norm_xi(req.team_a_xi), norm_xi(req.team_b_xi),
        ),
        sort_keys=True,
        default=str,
    )


def _cache_get(key):
    store, lock = _prediction_cache()
    with lock:
        item = store.get(key)
        if not item:
            return None
        expires_at, result = item
        if time.time() > expires_at:
            store.pop(key, None)
            return None
        return result


def _cache_put(key, result) -> None:
    store, lock = _prediction_cache()
    with lock:
        if len(store) >= PREDICTION_CACHE_MAX:
            # Drop the single oldest entry to keep the map bounded.
            oldest = min(store, key=lambda k: store[k][0])
            store.pop(oldest, None)
        store[key] = (time.time() + PREDICTION_CACHE_SECONDS, result)


def _resolve_live_xi(req):
    """Try to fill the request's XIs from Cricbuzz's actual lineup for today's
    match. Returns (xi_a, xi_b, note) — empty/None values mean "fall back"."""
    try:
        from app.services.cricbuzz import fetch_today_xi
        xi = fetch_today_xi(req.league, req.team_a, req.team_b)
    except Exception:
        return None, None, None
    if not xi or not xi[0] or not xi[1]:
        return (
            None, None,
            "No live lineup on Cricbuzz yet — using expected XI",
        )
    return (
        xi[0], xi[1],
        "Live XI from Cricbuzz (actual lineup)",
    )


def run_prediction(req) -> dict:
    """Execute the 10-layer engine for a PredictRequest and return its result.

    Identical requests (same teams, venue, stage, pitch, toss info and XIs)
    within the TTL share one computation: the first caller runs the engine and
    subsequent callers read the cached result instead of re-querying the DB.
    """
    validate_predict_request(req)

    # Auto-lineup: pull today's actual XI off Cricbuzz when the caller asked
    # for it and didn't supply explicit XIs. Silent fallback keeps predict
    # working on days with no CPL/IPL fixture or before lineups are announced.
    xi_note = None
    if getattr(req, "auto_xi", False) and not req.team_a_xi and not req.team_b_xi:
        req.team_a_xi, req.team_b_xi, xi_note = _resolve_live_xi(req)

    key = _cache_key(req)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    from engine.predictor import predict_match

    if not _PREDICTION_SEMAPHORE.acquire(blocking=False):
        raise HTTPException(
            status_code=503,
            detail="Prediction engine is at capacity — retry in a moment.",
        )
    try:
        result = predict_match(
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
    finally:
        _PREDICTION_SEMAPHORE.release()
    result["xi_note"] = xi_note
    _cache_put(key, result)
    return result


def validate_predict_request(req) -> None:
    """Reject malformed input up front instead of letting the engine silently
    produce a phantom near-50/50 prediction (a fabricated '50% win rate' from an
    empty sample looks worse than an error)."""
    if req.league not in VALID_LEAGUES:
        raise HTTPException(status_code=400, detail=f"league must be {', '.join(VALID_LEAGUES)}.")
    if req.pitch_type and req.pitch_type not in VALID_PITCH_TYPES:
        raise HTTPException(status_code=400, detail=f"pitch_type must be one of {', '.join(VALID_PITCH_TYPES)} or null.")
    if req.toss_decision and req.toss_decision.lower() not in ("batting", "bowling"):
        raise HTTPException(status_code=400, detail="toss_decision must be 'batting' or 'bowling' or null.")

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
    if req.toss_winner and req.toss_winner not in (req.team_a, req.team_b):
        raise HTTPException(status_code=400, detail="toss_winner must be one of the two teams or null.")


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