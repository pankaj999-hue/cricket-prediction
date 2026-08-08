# backend/app/services/toss_watcher.py
"""Background poller: watches the CPL 2026 schedule, detects when a match has
tossed (via embedded Cricbuzz page data), runs the prediction engine with the
real toss info, and emails the key factors to active subscribers.

Runs as a daemon thread started from the FastAPI lifespan. Safe to run in dev
too: EMAIL_DISABLED / missing RESEND_API_KEY turn email sending into a no-op.
"""
import datetime
import logging
import threading
import time

from app.config import TOSS_POLL_INTERVAL
from app.services.cricbuzz import get_match_info, get_series_matches, get_toss
from app.services.notify import render_toss_email, send_toss_email
from app.services.subscribe import (
    get_active_subscribers,
    log_toss_alert,
    toss_alert_exists,
)
from engine.utils import data_loader  # noqa: F401  (sets LEAGUE default / normalizes)

logger = logging.getLogger("toss_watcher")

# CPL 2026 team names match the DB names exactly (Kingsmen, Falcons, Tridents,
# St Lucia Kings, St Kitts and Nevis Patriots, Trinbago Knight Riders,
# Guyana Amazon Warriors, Barbados Royals). Defensive map in case Cricbuzz
# renames one mid-season.
TEAM_MAP = {}

# Cricbuzz ground name (matchInfo.venueInfo.ground) -> DB canonical venue.
# data_loader.normalize_venue covers all of these too; mapping here keeps the
# poller explicit about what it feeds the engine.
VENUE_MAP = {
    "Arnos Vale Ground": "Arnos Vale Stadium, Kingstown",
    "Sabina Park": "Sabina Park, Kingston",
    "Daren Sammy National Cricket Stadium": "Daren Sammy Cricket Ground, Gros Islet",
    "Sir Vivian Richards Stadium": "Sir Vivian Richards Stadium, North Sound",
    "Brian Lara Stadium": "Brian Lara Cricket Academy, Tarouba",
    "Warner Park": "Warner Park Sporting Complex, Basseterre",
    "Providence Stadium": "Providence Stadium, Georgetown",
    "Kensington Oval": "Kensington Oval, Bridgetown",
}

# Runtime status for the /api/toss-watcher/status probe.
_STATUS = {
    "thread_alive": False,
    "env": "",
    "interval": TOSS_POLL_INTERVAL,
    "last_sweep": None,
    "last_sweep_result": None,
    "last_error": None,
    "kick_count": 0,
}


def _map_team(name):
    return TEAM_MAP.get(name, name)


def _map_venue(name):
    return VENUE_MAP.get(name, name) if name else name


def _stage(desc):
    if not desc:
        return "League"
    d = desc.lower()
    if any(k in d for k in ("qualifier", "eliminator", "final")):
        return "Playoffs"
    return "League"


def _build_alert(match_id, match_info, toss, match_date):
    """Run the engine and assemble the alert dict shared by email + DB log."""
    team_a = _map_team((match_info.get("team1") or {}).get("teamName"))
    team_b = _map_team((match_info.get("team2") or {}).get("teamName"))
    venue = _map_venue((match_info.get("venueInfo") or {}).get("ground"))
    toss_winner = _map_team(toss.get("tossWinnerName"))
    toss_decision = toss.get("decision")
    if toss_decision:
        toss_decision = "Batting" if toss_decision.lower().startswith("bat") else "Bowling"

    from engine.predictor import predict_match

    # Neon closes idle connections; pooled conns self-heal on close() but a
    # stale one can still raise mid-prediction. Retry to ride through it.
    import psycopg2
    import time

    last_err = None
    result = None
    for attempt in range(3):
        try:
            result = predict_match(
                team_a=team_a,
                team_b=team_b,
                venue=venue,
                stage=_stage(match_info.get("matchDesc")),
                league="CPL",
                toss_winner=toss_winner,
                toss_decision=toss_decision,
            )
            break
        except psycopg2.OperationalError as e:
            last_err = e
            logger.info("engine retry %d for %s after DB error", attempt + 1, match_id)
            time.sleep(2)
    if result is None:
        raise last_err

    return {
        "cricbuzz_match_id": str(match_id),
        "match_name": f"{team_a} vs {team_b}",
        "match_date": match_date,
        "team_a": team_a,
        "team_b": team_b,
        "venue": venue,
        "toss_winner": toss_winner,
        "toss_decision": toss_decision,
        "predicted_winner": result.get("predicted_winner"),
        "team_a_score": result.get("team_a_score"),
        "team_b_score": result.get("team_b_score"),
        "confidence": result.get("confidence"),
        "no_bet": bool(result.get("no_bet")),
        "key_factors": result.get("key_factors", []),
        "sent_count": 0,
    }


def process_match(match_id, dry_run=False) -> bool:
    """Handle a single match: fetch toss; if tossed and not yet handled, run
    the engine and email subscribers. Returns True when an alert was emitted."""
    if toss_alert_exists(str(match_id)):
        return False

    toss = get_toss(match_id)
    if not toss:
        return False  # not tossed yet — try again next sweep

    match_info = get_match_info(match_id)
    start_ms = match_info.get("startDate")
    match_date = None
    if start_ms:
        match_date = datetime.datetime.utcfromtimestamp(start_ms / 1000).date()

    try:
        alert = _build_alert(match_id, match_info, toss, match_date)
    except Exception as e:
        logger.warning("engine failed for match %s: %s", match_id, e)
        return False

    subscribers = [s["email"] for s in get_active_subscribers("CPL")]

    if subscribers:
        subject = (
            f"Toss alert: {alert['team_a']} vs {alert['team_b']} — "
            f"{alert['toss_winner']} chose {alert['toss_decision']}"
        )
        body = render_toss_email(
            alert["team_a"], alert["team_b"], alert["venue"],
            alert["toss_winner"], alert["toss_decision"],
            alert["predicted_winner"], alert["no_bet"],
            alert["team_a_score"], alert["team_b_score"], alert["confidence"],
            alert["key_factors"],
        )
        if dry_run:
            logger.info("dry-run: would email %d subscriber(s) for %s", len(subscribers), match_id)
        else:
            ok_count = 0
            for email in subscribers:
                ok, _detail = send_toss_email(email, subject, body)
                if ok:
                    ok_count += 1
            alert["sent_count"] = ok_count
    else:
        logger.info("no subscribers yet for %s — skipping email", match_id)

    if not dry_run:
        try:
            log_toss_alert(alert)
        except Exception as e:
            logger.warning("could not persist alert for %s: %s", match_id, e)
    logger.info("toss alert processed for %s (sent=%d)", match_id, alert["sent_count"])
    return True


def sweep(dry_run=False) -> int:
    """One pass over the CPL schedule; returns the number of alerts created."""
    created = 0
    for match in get_series_matches():
        mi = match.get("matchInfo") or {}
        mid = mi.get("matchId")
        if not mid:
            continue
        try:
            if process_match(str(mid), dry_run=dry_run):
                created += 1
        except Exception as e:
            logger.warning("sweep error on %s: %s", mid, e)
    _STATUS["last_sweep"] = datetime.datetime.utcnow().isoformat()
    _STATUS["last_sweep_result"] = created
    return created


def run_forever(interval: int | None = None):
    """Polling loop intended for a daemon thread. Never returns."""
    interval = interval or TOSS_POLL_INTERVAL
    logger.info("toss watcher started (interval=%ss)", interval)
    _STATUS["thread_alive"] = True
    while True:
        try:
            created = sweep()
            _STATUS["last_error"] = None
            if created:
                logger.info("sweep created %d alert(s)", created)
        except Exception as e:
            _STATUS["last_error"] = str(e)
            logger.error("sweep failed: %s", e)
        _STATUS["thread_alive"] = threading.current_thread().is_alive()
        time.sleep(interval)


def status() -> dict:
    return dict(_STATUS)