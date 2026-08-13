# backend/app/services/subscribe.py
"""Subscriber management: store emails who opted in to toss alerts."""
import re

from fastapi import HTTPException

from app.core.db import get_db_connection


def _valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


def subscribe(email: str, league: str = "CPL") -> dict:
    """Add a subscriber email (idempotent). Returns the stored row."""
    email = email.strip().lower()
    if not _valid_email(email):
        raise HTTPException(status_code=400, detail="A valid email address is required.")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO subscribers (email, league)
           VALUES (%s, %s)
           ON CONFLICT (email) DO UPDATE SET league = EXCLUDED.league, is_active = TRUE
           RETURNING id, email, league, is_active, created_at""",
        (email, league.upper()),
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return {
        "id": str(row[0]),
        "email": row[1],
        "league": row[2],
        "is_active": bool(row[3]),
    }


def unsubscribe(email: str) -> None:
    """Deactivate a subscriber (keep row for history)."""
    email = email.strip().lower()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE subscribers SET is_active = FALSE WHERE email = %s",
        (email,),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_active_subscribers(league: str = "CPL") -> list[dict]:
    """All emails configured to receive alerts for a league."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, email FROM subscribers WHERE is_active = TRUE AND league = %s",
        (league.upper(),),
    )
    rows = [{"id": str(r[0]), "email": r[1]} for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


def log_toss_alert(alert: dict) -> None:
    """Record that a toss alert was generated + sent for a match. Upserts the
    prediction fields rather than just the sent_count, so a pre-toss entry
    (created ahead of the match) is refreshed in place when the toss lands."""
    import json

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO toss_alerts (
            cricbuzz_match_id, match_name, match_date, team_a, team_b, venue,
            toss_winner, toss_decision, predicted_winner, team_a_score, team_b_score,
            confidence, key_factors, sent_count)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (cricbuzz_match_id) DO UPDATE SET
               match_name = EXCLUDED.match_name,
               match_date = EXCLUDED.match_date,
               team_a = EXCLUDED.team_a,
               team_b = EXCLUDED.team_b,
               venue = EXCLUDED.venue,
               toss_winner = EXCLUDED.toss_winner,
               toss_decision = EXCLUDED.toss_decision,
               predicted_winner = EXCLUDED.predicted_winner,
               team_a_score = EXCLUDED.team_a_score,
               team_b_score = EXCLUDED.team_b_score,
               confidence = EXCLUDED.confidence,
               key_factors = EXCLUDED.key_factors,
               sent_count = EXCLUDED.sent_count""",
        (
            alert["cricbuzz_match_id"], alert.get("match_name"), alert.get("match_date"),
            alert.get("team_a"), alert.get("team_b"), alert.get("venue"),
            alert.get("toss_winner"), alert.get("toss_decision"),
            alert.get("predicted_winner"), alert.get("team_a_score"), alert.get("team_b_score"),
            alert.get("confidence"), json.dumps(alert.get("key_factors")), alert.get("sent_count", 0),
        ),
    )
    conn.commit()
    cur.close()
    conn.close()


def toss_alert_exists(cricbuzz_match_id: str) -> bool:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM toss_alerts WHERE cricbuzz_match_id = %s", (cricbuzz_match_id,))
    exists = cur.fetchone() is not None
    cur.close()
    conn.close()
    return exists


def toss_alert_has_toss(cricbuzz_match_id: str) -> bool:
    """True when the stored alert already carries toss info (so the pre-toss
    entry shouldn't be rebuilt/emailed again once the toss lands)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT toss_winner FROM toss_alerts WHERE cricbuzz_match_id = %s",
        (cricbuzz_match_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return bool(row and row[0])


def get_alert_by_match(cricbuzz_match_id: str) -> dict | None:
    """Prediction stored for a specific match (loose team-name matching so a
    Cricbuzz 'Saint Lucia Kings' row joins to the canonical DB name)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT team_a, team_b, predicted_winner, confidence, team_a_score, "
        "team_b_score, result_winner FROM toss_alerts WHERE cricbuzz_match_id = %s",
        (cricbuzz_match_id,),
    )
    r = cur.fetchone()
    cur.close()
    conn.close()
    if not r:
        return None
    return {
        "team_a": r[0], "team_b": r[1], "predicted_winner": r[2],
        "confidence": r[3] or "", "no_bet": bool(r[2] and r[2] == "No Bet"),
        "team_a_score": float(r[4] or 0), "team_b_score": float(r[5] or 0),
        "result_winner": r[6],
    }


def get_unscored_alerts() -> list[dict]:
    """Alerts whose match may now be finished but hasn't been scored yet."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT cricbuzz_match_id, team_a, team_b, predicted_winner, confidence, "
        "team_a_score, team_b_score FROM toss_alerts WHERE result_winner IS NULL "
        "ORDER BY created_at DESC"
    )
    rows = [
        {
            "cricbuzz_match_id": str(r[0]), "team_a": r[1], "team_b": r[2],
            "predicted_winner": r[3], "confidence": r[4] or "",
            "team_a_score": float(r[5] or 0), "team_b_score": float(r[6] or 0),
        }
        for r in cur.fetchall()
    ]
    cur.close()
    conn.close()
    return rows


def score_alert(cricbuzz_match_id: str, result_winner: str, is_correct: bool | None) -> None:
    """Record the actual match winner and whether our call was right.

    is_correct=None marks a decline (No Bet) — recorded but not counted in
    accuracy calls."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE toss_alerts SET result_winner = %s, is_correct = %s, scored_at = NOW() "
        "WHERE cricbuzz_match_id = %s",
        (result_winner, is_correct, str(cricbuzz_match_id)),
    )
    conn.commit()
    cur.close()
    conn.close()


def recent_records(limit: int = 8) -> dict:
    """Recent scored toss calls + accuracy stats for the frontend Records panel."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT match_name, team_a, team_b, predicted_winner, confidence,
                  team_a_score, team_b_score, is_correct, result_winner,
                  toss_winner, cricbuzz_match_id
           FROM toss_alerts ORDER BY created_at DESC LIMIT %s""",
        (limit,),
    )
    rows = []
    for r in cur.fetchall():
        predicted = r[3]
        no_bet = bool(predicted and predicted == "No Bet")
        rows.append({
            "match_id": str(r[10]),
            "match": r[0] or (f"{r[1]} vs {r[2]}"),
            "pick": "No Bet" if no_bet else (predicted or ""),
            "confidence": "Decline" if no_bet else (r[4] or ""),
            "no_bet": no_bet,
            "team_a_score": float(r[5] or 0),
            "team_b_score": float(r[6] or 0),
            "is_correct": None if no_bet else (r[7] if r[7] is not None else None),
            "result_winner": r[8],
            "toss": r[9],
        })

    # Calls accuracy counts only team calls (is_correct set, not a No Bet).
    # Declines are tallied separately and never count as wrong.
    cur.execute(
        """SELECT count(*),
                  count(*) FILTER (WHERE is_correct = TRUE)
           FROM toss_alerts
           WHERE is_correct IS NOT NULL AND predicted_winner <> 'No Bet'"""
    )
    calls_total, calls_correct = cur.fetchone()
    cur.execute(
        "SELECT count(*) FROM toss_alerts WHERE result_winner IS NOT NULL AND predicted_winner = 'No Bet'"
    )
    no_bets = cur.fetchone()[0]
    cur.close()
    conn.close()

    calls_total = calls_total or 0
    calls_correct = calls_correct or 0
    no_bets = no_bets or 0
    pct = round(calls_correct / calls_total * 100) if calls_total else 0
    return {
        "records": rows,
        "accuracy": {
            "calls": calls_total,
            "correct": calls_correct,
            "wrong": max(0, calls_total - calls_correct),
            "no_bet": no_bets,
            "pct": pct,
        },
    }