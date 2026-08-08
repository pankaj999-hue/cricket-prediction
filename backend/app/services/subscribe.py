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
    """Record that a toss alert was generated + sent for a match."""
    import json

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO toss_alerts (
            cricbuzz_match_id, match_name, match_date, team_a, team_b, venue,
            toss_winner, toss_decision, predicted_winner, team_a_score, team_b_score,
            confidence, key_factors, sent_count)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (cricbuzz_match_id) DO UPDATE SET sent_count = EXCLUDED.sent_count""",
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