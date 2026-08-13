# backend/app/services/ingest.py
"""Manual match-data ingest: accept a full Cricsheet v1.2.0 JSON object (the
same format the `data/cpl_json/*.json` archives use), insert it into
matches/players/deliveries, then rebuild the pre-computed aggregation tables so
the engine sees the new match immediately.

Replaces the need to copy JSON files onto the server and run the loader scripts
by hand — the admin panel calls this instead.
"""
import hashlib

from app.core.db import get_db_connection
from engine.utils.data_loader import normalize_venue

# Cricbuzz/Cricsheet team names -> the canonical name the DB stores. Historical
# CPL names are mapped so renamed 2026 squads still join their history for
# H2H/venue/aggregation queries.
TEAM_MAP = {
    "Jamaica Tallawahs": "Jamaica Kingsmen",
    "Barbados Royals": "Barbados Tridents",
    "Trinidad & Tobago Red Steel": "Trinbago Knight Riders",
    "Trinidad and Tobago Red Steel": "Trinbago Knight Riders",
    "T&T Red Steel": "Trinbago Knight Riders",
    "St Lucia Zouks": "St Lucia Kings",
    "St Lucia Stars": "St Lucia Kings",
    "Saint Lucia Kings": "St Lucia Kings",
    "Antigua Hawksbills": "Antigua and Barbuda Falcons",
    "St Kitts and Nevis Patriots": "St Kitts & Nevis Patriots",
}


def _map_team(name):
    return TEAM_MAP.get(name, name) if name else name


def _clean_player_name(name):
    return name.strip() if name else None


def _derive_match_id(info: dict) -> str:
    """Deterministic match_id from the JSON contents. Stable across repeated
    pastes, so re-submitting the same match is a clean no-op instead of a
    duplicate row."""
    teams = [_map_team(t) for t in (info.get("teams") or [])]
    date = (info.get("dates") or [""])[0]
    seed = f"{date}|{teams[0]}|{teams[1]}"
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
    return f"cpl_{date}_{digest}"


def _build_match(info: dict, match_id: str) -> dict:
    teams = info.get("teams") or [None, None]
    toss = info.get("toss") or {}
    outcome = info.get("outcome") or {}
    by = outcome.get("by") or {}
    return {
        "match_id": match_id,
        "season": info.get("season", ""),
        "date": (info.get("dates") or [None])[0],
        "format": info.get("match_type", "T20"),
        "event": (info.get("event") or {}).get("name", ""),
        "stage": (info.get("event") or {}).get("stage", ""),
        "venue": normalize_venue(info.get("venue", "")),
        "city": info.get("city", ""),
        "team_a": _map_team(teams[0]),
        "team_b": _map_team(teams[1]),
        "toss_winner": _map_team(toss.get("winner")),
        "toss_decision": toss.get("decision"),
        "winner": _map_team(outcome.get("winner")),
        "win_margin": list(by.values())[0] if by else None,
        "win_type": list(by.keys())[0] if by else None,
        "player_of_match": (info.get("player_of_match") or [None])[0],
        "league": "CPL",
    }


def _build_deliveries(match_id: str, data: dict, team_a: str, team_b: str) -> list[dict]:
    registry = ((data.get("info") or {}).get("registry") or {}).get("people", {})
    teams = (team_a, team_b)
    deliveries = []
    for innings_num, innings in enumerate(data.get("innings", []), 1):
        batting_team = _map_team(innings.get("team", ""))
        bowling_team = teams[0] if batting_team == teams[1] else teams[1]
        for over_data in innings.get("overs", []):
            over_num = over_data.get("over", 0)
            for ball in over_data.get("deliveries", []):
                batter = _clean_player_name(ball.get("batter", ""))
                bowler = _clean_player_name(ball.get("bowler", ""))
                extras = ball.get("extras", {})
                wickets = ball.get("wickets") or [{}]
                deliveries.append({
                    "match_id": match_id,
                    "innings": innings_num,
                    "batting_team": batting_team,
                    "bowling_team": bowling_team,
                    "over_num": over_num,
                    "ball_num": ball.get("actual_delivery", ""),
                    "batter": batter,
                    "batter_id": registry.get(batter),
                    "bowler": bowler,
                    "bowler_id": registry.get(bowler),
                    "non_striker": _clean_player_name(ball.get("non_striker")),
                    "runs_batter": ball.get("runs", {}).get("batter", 0),
                    "runs_extras": ball.get("runs", {}).get("extras", 0),
                    "runs_total": ball.get("runs", {}).get("total", 0),
                    "is_wicket": "wickets" in ball,
                    "wicket_kind": wickets[0].get("kind"),
                    "player_out": _clean_player_name(wickets[0].get("player_out")),
                    "is_wide": "wides" in extras,
                    "is_noball": "noballs" in extras,
                    "is_bye": "byes" in extras,
                    "is_legbye": "legbyes" in extras,
                })
    return deliveries


def _build_players(data: dict) -> list[dict]:
    """Registry entries that actually appear in a playing XI."""
    info = data.get("info") or {}
    registry = (info.get("registry") or {}).get("people", {})
    squads = info.get("players") or {}
    players = []
    for name, player_id in registry.items():
        if any(name in squad for squad in squads.values()):
            players.append({"player_id": player_id, "name": name})
    return players


def ingest_match(data: dict, match_id: str | None = None) -> dict:
    """Insert a full Cricsheet match JSON into the DB and refresh aggregations.

    Returns a summary dict: {match_id, teams, venue, date, players, deliveries,
    inserted, reason}. Raises ValueError on malformed payloads.
    """
    info = data.get("info") or {}
    if not info:
        raise ValueError("Not a Cricsheet match JSON: missing the 'info' object.")

    teams = info.get("teams") or [None, None]
    team_a, team_b = _map_team(teams[0]), _map_team(teams[1])
    if not team_a or not team_b:
        raise ValueError("Match must list two teams.")
    if not (info.get("dates") or [None])[0]:
        raise ValueError("Match must have a date.")
    venue = normalize_venue(info.get("venue", ""))
    if not venue:
        raise ValueError("Match must have a venue.")

    match_id = match_id or _derive_match_id(info)

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT match_id FROM matches WHERE match_id = %s", (match_id,))
    if cur.fetchone():
        cur.close()
        conn.close()
        return {"match_id": match_id, "inserted": False, "reason": "match_id already exists"}

    cur.execute(
        "SELECT match_id FROM matches WHERE team_a = %s AND team_b = %s AND date = %s AND league = 'CPL'",
        (team_a, team_b, (info.get("dates") or [None])[0]),
    )
    dup = cur.fetchone()
    if dup:
        cur.close()
        conn.close()
        return {"match_id": dup[0], "inserted": False, "reason": "same teams + date already loaded"}

    match = _build_match(info, match_id)
    deliveries = _build_deliveries(match_id, data, team_a, team_b)
    players = _build_players(data)

    try:
        cur.execute(
            """
            INSERT INTO matches (match_id, season, date, format, event, stage, venue, city,
                team_a, team_b, toss_winner, toss_decision, winner, win_margin, win_type, player_of_match, league)
            VALUES (%(match_id)s, %(season)s, %(date)s, %(format)s, %(event)s, %(stage)s, %(venue)s, %(city)s,
                %(team_a)s, %(team_b)s, %(toss_winner)s, %(toss_decision)s, %(winner)s, %(win_margin)s, %(win_type)s, %(player_of_match)s, %(league)s)
            """,
            match,
        )
        for player in players:
            cur.execute(
                "INSERT INTO players (player_id, name) VALUES (%(player_id)s, %(name)s) ON CONFLICT (player_id) DO NOTHING",
                player,
            )
        for d in deliveries:
            cur.execute(
                """
                INSERT INTO deliveries (match_id, innings, batting_team, bowling_team, over_num, ball_num,
                    batter, batter_id, bowler, bowler_id, non_striker, runs_batter, runs_extras, runs_total,
                    is_wicket, wicket_kind, player_out, is_wide, is_noball, is_bye, is_legbye)
                VALUES (%(match_id)s, %(innings)s, %(batting_team)s, %(bowling_team)s, %(over_num)s, %(ball_num)s,
                    %(batter)s, %(batter_id)s, %(bowler)s, %(bowler_id)s, %(non_striker)s, %(runs_batter)s, %(runs_extras)s, %(runs_total)s,
                    %(is_wicket)s, %(wicket_kind)s, %(player_out)s, %(is_wide)s, %(is_noball)s, %(is_bye)s, %(is_legbye)s)
                """,
                d,
            )
        conn.commit()
    except Exception:
        conn.rollback()
        cur.close()
        conn.close()
        raise

    cur.close()
    conn.close()

    from app.database.refresh_aggregation import refresh_all
    refresh_all()

    return {
        "match_id": match_id,
        "teams": [team_a, team_b],
        "venue": venue,
        "date": (info.get("dates") or [None])[0],
        "players": len(players),
        "deliveries": len(deliveries),
        "inserted": True,
    }


def refresh_aggregations() -> None:
    """Re-run the aggregation rebuild (admin 'Refresh' button)."""
    from app.database.refresh_aggregation import refresh_all
    refresh_all()


def recent_matches(limit: int = 10) -> list[dict]:
    """Most recently created CPL matches (for the dedup check on the admin page)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT match_id, date, team_a, team_b, venue, created_at
        FROM matches
        WHERE league = 'CPL'
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (max(1, min(limit, 50)),),
    )
    rows = [
        {
            "match_id": r[0],
            "date": r[1].isoformat() if r[1] else None,
            "team_a": r[2],
            "team_b": r[3],
            "venue": r[4],
            "created_at": r[5].isoformat() if r[5] else None,
        }
        for r in cur.fetchall()
    ]
    cur.close()
    conn.close()
    return rows
