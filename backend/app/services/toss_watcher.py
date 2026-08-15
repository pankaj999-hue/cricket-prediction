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

from app.config import PRE_MATCH_MINUTES, TOSS_POLL_INTERVAL
from app.services.cricbuzz import (
    get_match_info,
    get_match_squads,
    get_series_matches,
    get_result,
    get_toss,
)
from app.services.notify import render_toss_email, send_toss_email
from app.services.subscribe import (
    get_active_subscribers,
    get_unscored_alerts,
    log_toss_alert,
    score_alert,
    toss_alert_exists,
    toss_alert_has_toss,
)
from engine.utils import data_loader  # noqa: F401  (sets LEAGUE default / normalizes)

logger = logging.getLogger("toss_watcher")

# CPL 2026 team names match the DB names exactly (Kingsmen, Falcons, Tridents,
# St Lucia Kings, St Kitts and Nevis Patriots, Trinbago Knight Riders,
# Guyana Amazon Warriors, Barbados Royals). Defensive map in case Cricbuzz
# renames one mid-season.
TEAM_MAP = {
    "Saint Lucia Kings": "St Lucia Kings",
}

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

# How long after a match's scheduled start we'll still log a call when the toss
# hasn't been scraped yet. Covers the full live window (a CPL T20 runs ~3h) so
# an in-progress match shows up in "Recent calls" even if the toss scrape lags;
# avoids resurrecting stale alerts for matches that finished days ago.
LIVE_CREATE_GRACE_HOURS = 6

# Runtime status for the /api/toss-watcher/status probe.
from app.config import ENVIRONMENT as _ENV

_STATUS = {
    "thread_alive": False,
    "env": _ENV,
    "interval": TOSS_POLL_INTERVAL,
    "last_sweep": None,
    "last_sweep_result": None,
    "last_error": None,
    "email_configured": False,
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


def _scraped_xi(match_info, match_id):
    """Recover the actual playing XIs for a match from Cricbuzz and map them to
    DB canonical team names. Returns (xi_a, xi_b) or (None, None) when one side
    hasn't named a full lineup yet."""
    try:
        squads = get_match_squads(match_id)
    except Exception:
        return None, None
    team_a = _map_team((match_info.get("team1") or {}).get("teamName"))
    team_b = _map_team((match_info.get("team2") or {}).get("teamName"))
    xi_a = []
    xi_b = []
    for s in squads:
        names = [p["name"] for p in s.get("players", []) if p.get("name")]
        canonical = _map_team(s.get("team"))
        if canonical == team_a:
            xi_a = names
        elif canonical == team_b:
            xi_b = names
    if len(xi_a) >= 8 and len(xi_b) >= 8:
        return xi_a, xi_b
    return None, None


def _build_alert(match_id, match_info, toss, match_date, team_a_xi=None, team_b_xi=None):
    """Run the engine and assemble the alert dict shared by email + DB log."""
    team_a = _map_team((match_info.get("team1") or {}).get("teamName"))
    team_b = _map_team((match_info.get("team2") or {}).get("teamName"))
    venue = _map_venue((match_info.get("venueInfo") or {}).get("ground"))
    if not team_a or not team_b or not venue:
        raise ValueError(f"incomplete match_info for {match_id}: teams/venue missing")
    has_toss = bool(toss and toss.get("tossWinnerName"))
    toss_winner = _map_team(toss.get("tossWinnerName")) if has_toss else None
    toss_decision = toss.get("decision") if has_toss else None
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
                team_a_xi=team_a_xi,
                team_b_xi=team_b_xi,
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


def _backfill_complete(match_id, dry_run=False) -> bool:
    """Log + score an engine call for a finished match that has no alert yet.

    The poller only runs while the process is alive; on a sleeping free-tier
    box a match's whole pre-match/toss window can pass unobserved. When that
    happens the match shows up here as Complete with no toss_alerts row, so
    rebuild the call now from the final toss + playing XI and score it. The
    pick is generated from toss/XI only (the result is fetched afterwards), so
    it is a genuine prediction, not a result leak."""
    try:
        if toss_alert_exists(str(match_id)):
            return False  # an alert already exists — never re-predict it
        match_info = get_match_info(match_id)
        toss = get_toss(match_id)
        team_a_xi, team_b_xi = _scraped_xi(match_info, match_id)
        alert = _build_alert(
            match_id, match_info, toss, None,
            team_a_xi=team_a_xi, team_b_xi=team_b_xi,
        )
        if dry_run:
            return True
        log_toss_alert(alert)
        result = get_result(match_id)
        winner = _map_team((result or {}).get("winningTeam"))
        if winner:
            predicted = alert["predicted_winner"]
            is_correct = None if (predicted and predicted == "No Bet") else bool(predicted) and predicted == winner
            score_alert(str(match_id), winner, is_correct)
        logger.info("backfilled finished match %s (%s)", match_id, winner or "no result")
        return True
    except Exception as e:
        logger.warning("backfill failed for %s: %s", match_id, e)
        return False


def process_match(match_id, start_ms=None, state=None, dry_run=False) -> bool:
    """Handle a single match.

    Pre-match (start minus PRE_MATCH_MINUTES) — run the engine on the scraped
    live XI (no toss yet) and log it so the Recent-calls tab gets a call ahead
    of the toss. Once the toss lands, rebuild the same alert with the toss info
    (upserted in place) and email subscribers. Finished matches with no alert
    (missed live window) are backfilled so every completed match still shows up.
    """
    if state and str(state).lower() in ("complete", "abandoned"):
        if toss_alert_exists(str(match_id)):
            return False  # already logged — never re-predict a finished match
        return _backfill_complete(match_id, dry_run=dry_run)
    if start_ms:
        try:
            start_ms = float(start_ms)
        except (TypeError, ValueError):
            start_ms = None
    now_ms = time.time() * 1000
    if start_ms and now_ms < start_ms - PRE_MATCH_MINUTES * 60_000:
        return False  # too far from the match — wait for the pre-match timer

    toss = get_toss(match_id)
    has_toss = bool(toss and toss.get("tossWinnerName"))

    exists = toss_alert_exists(str(match_id))
    if exists:
        if toss_alert_has_toss(str(match_id)):
            return False  # already handled with toss info
        if not has_toss:
            return False  # pre-toss call already logged — nothing new yet
        # fall through: pre-toss alert exists and the toss just landed -> update

    if not has_toss and not start_ms:
        return False
    if not has_toss and start_ms and now_ms > start_ms + LIVE_CREATE_GRACE_HOURS * 3_600_000:
        return False  # started too long ago without a scraped toss — skip stale recreates

    match_info = get_match_info(match_id)
    match_date = None
    try:
        match_date = datetime.datetime.utcfromtimestamp(float(match_info.get("startDate") or start_ms) / 1000).date()
    except (TypeError, ValueError):
        match_date = None

    team_a_xi, team_b_xi = _scraped_xi(match_info, match_id)

    try:
        alert = _build_alert(
            match_id, match_info, toss, match_date,
            team_a_xi=team_a_xi, team_b_xi=team_b_xi,
        )
    except Exception as e:
        logger.warning("engine failed for match %s: %s", match_id, e)
        return False

    if has_toss:
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
    logger.info("toss alert processed for %s (toss=%s, sent=%d)",
                match_id, has_toss, alert["sent_count"])
    return True


def score_finished(force=False) -> int:
    """Score previously-logged alerts whose matches have now finished.

    For each unscored alert: fetch the match result; if the match has a winner,
    mark the alert as correct/wrong (No Bet alerts are recorded but never count
    as a call). Returns the number newly scored."""
    scored = 0
    for alert in get_unscored_alerts():
        try:
            result = get_result(alert["cricbuzz_match_id"])
        except Exception as e:
            logger.warning("result fetch failed for %s: %s", alert["cricbuzz_match_id"], e)
            continue
        winner = (result or {}).get("winningTeam")
        if not winner:
            continue  # match not finished yet
        winner = _map_team(winner)  # Cricbuzz names may differ from DB canonical
        predicted = alert["predicted_winner"]
        # 'No Bet' rows are declines: record the result but never score them as
        # a correct/wrong call (is_correct NULL excludes them from accuracy).
        if predicted and predicted == "No Bet":
            is_correct = None
        else:
            is_correct = bool(predicted) and predicted == winner
        try:
            score_alert(alert["cricbuzz_match_id"], winner, is_correct)
            scored += 1
        except Exception as e:
            logger.warning("score error for %s: %s", alert["cricbuzz_match_id"], e)
    if scored:
        logger.info("scored %d finished match(es)", scored)
    return scored


def sweep(dry_run=False) -> int:
    """One pass over the CPL schedule; returns the number of alerts created.
    `get_series_matches()` yields flat matchInfo objects (top-level matchId)."""
    created = 0
    for match in get_series_matches():
        mid = match.get("matchId")
        if not mid:
            continue
        try:
            if process_match(
                str(mid),
                start_ms=match.get("startDate"),
                state=match.get("state"),
                dry_run=dry_run,
            ):
                created += 1
        except Exception as e:
            logger.warning("sweep error on %s: %s", mid, e)
    scored = score_finished()
    _STATUS["last_sweep"] = datetime.datetime.utcnow().isoformat()
    _STATUS["last_sweep_result"] = created
    _STATUS["last_scored"] = scored
    return created


def run_forever(interval: int | None = None):
    """Polling loop intended for a daemon thread. Never returns."""
    interval = interval or TOSS_POLL_INTERVAL
    from app.config import EMAIL_DISABLED, RESEND_API_KEY

    logger.info("toss watcher started (interval=%ss)", interval)
    _STATUS["thread_alive"] = True
    _STATUS["email_configured"] = bool(RESEND_API_KEY) and not EMAIL_DISABLED
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