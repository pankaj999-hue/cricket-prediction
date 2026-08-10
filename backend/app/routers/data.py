# backend/app/routers/data.py
"""Read-only data endpoints: teams, venues, and squad-strength leaderboard."""
from fastapi import APIRouter

from app.core.db import get_db_connection

router = APIRouter(prefix="/api", tags=["data"])

RECENT_SEASONS = ["2024", "2025", "2026"]


@router.get("/teams")
def get_teams(league: str = "IPL", season: str = "2026"):
    """Distinct teams that played in a given league/season, plus any known squads
    (so new first-season franchises like Jamaica Kingsmen still appear before
    their first loaded match row exists)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT team_a FROM matches WHERE league = %s AND season = %s "
        "UNION SELECT DISTINCT team_b FROM matches WHERE league = %s AND season = %s "
        "UNION SELECT DISTINCT team FROM squads WHERE league = %s "
        "ORDER BY team_a",
        (league, season, league, season, league),
    )
    teams = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return {"league": league, "season": season, "teams": teams}


@router.get("/venues")
def get_venues(league: str = "IPL", season: str = "2026"):
    """Distinct venues for a league/season. Falls back to the most recent season
    that has data when the requested season has no matches yet (e.g. CPL 2026)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT venue FROM matches WHERE league = %s AND season = %s ORDER BY venue",
        (league, season),
    )
    venues = [r[0] for r in cur.fetchall()]
    if not venues:
        cur.execute(
            "SELECT COALESCE(MAX(season), %s) FROM matches WHERE league = %s",
            (season, league),
        )
        latest = cur.fetchone()[0]
        cur.execute(
            "SELECT DISTINCT venue FROM matches WHERE league = %s AND season = %s ORDER BY venue",
            (league, latest),
        )
        venues = [r[0] for r in cur.fetchall()]
        season = latest

    # Known new-season venues that host their first matches in a season not yet
    # loaded into the DB — surface them so the UI can still offer them. (venues
    # still work with neutral history until their match data arrives.)
    if league == "CPL":
        debut = ["Arnos Vale Stadium, Kingstown", "Sabina Park, Kingston"]
        venues = sorted(set(venues) | set(debut))

    cur.close()
    conn.close()
    return {"league": league, "season": season, "venues": venues}


@router.get("/team-strength")
def get_team_strength(league: str = "IPL", season: str = "2026"):
    """Real squad strength over RECENT_SEASONS only (2024-2026).

    Each team's roster = players who represented it in the recent-season window,
    each scored from their stats accumulated *within that window only* (not their
    all-time career), averaged over the top 11. This keeps the leaderboard
    aligned with the engine's recency window so past-era careers don't inflate
    current strength. New franchises with no recent history score null.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # ---- 1. Roster: players who actually played for each team in recent seasons ----
    cur.execute(
        """
        SELECT d.batting_team, d.batter_id
        FROM deliveries d
        JOIN matches m ON d.match_id = m.match_id
        WHERE m.league = %s AND m.season = ANY(%s)
        GROUP BY d.batting_team, d.batter_id
        """,
        (league, RECENT_SEASONS),
    )
    roster = {}
    for team, pid in cur.fetchall():
        roster.setdefault(team, set()).add(pid)

    # ---- 2. Recent-season per-player stats (batting + bowling) ----
    cur.execute(
        """
        SELECT
            COALESCE(b.player_id, w.player_id) AS player_id,
            COALESCE(b.matches, 0) AS bat_matches,
            COALESCE(b.runs, 0) AS runs,
            COALESCE(b.balls, 0) AS balls,
            b.batting, b.sr,
            COALESCE(w.wickets, 0) AS wickets,
            COALESCE(w.balls_bowled, 0) AS balls_bowled,
            w.econ
        FROM (
            SELECT d.batter_id AS player_id,
                   COUNT(DISTINCT d.match_id) AS matches,
                   SUM(d.runs_batter) AS runs,
                   COUNT(*) AS balls,
                   SUM(d.runs_batter) * 1.0 / NULLIF(
                       COUNT(CASE WHEN d.is_wicket AND d.player_out = d.batter THEN 1 ELSE NULL END), 0)
                       AS batting,
                   SUM(d.runs_batter) * 100.0 / NULLIF(COUNT(*), 0) AS sr
            FROM deliveries d
            JOIN matches m ON d.match_id = m.match_id
            WHERE m.league = %s AND m.season = ANY(%s)
            GROUP BY d.batter_id
        ) b
        FULL OUTER JOIN (
            SELECT d.bowler_id AS player_id,
                   COUNT(CASE WHEN d.is_wicket AND d.wicket_kind NOT IN ('run out') THEN 1 ELSE NULL END) AS wickets,
                   COUNT(*) AS balls_bowled,
                   SUM(d.runs_total) * 6.0 / NULLIF(COUNT(*), 0) AS econ
            FROM deliveries d
            JOIN matches m ON d.match_id = m.match_id
            WHERE m.league = %s AND m.season = ANY(%s)
            GROUP BY d.bowler_id
        ) w ON b.player_id = w.player_id
        """,
        (league, RECENT_SEASONS, league, RECENT_SEASONS),
    )
    recent = {}
    cols = [d[0] for d in cur.description]
    for row in cur.fetchall():
        recent[row[0]] = dict(zip(cols, row))

    # ---- 3. Team result strength (recent win rate + margins), same window ----
    cur.execute(
        """
        SELECT team,
               COUNT(*) AS games,
               COUNT(*) FILTER (WHERE winner = team) AS wins,
               COUNT(*) FILTER (WHERE winner IS NOT NULL) AS decided,
               COALESCE(AVG(CASE WHEN winner = team AND win_margin IS NOT NULL
                                 THEN win_margin ELSE NULL END), 0) AS avg_margin
        FROM (
            SELECT league, season, team_a AS team, winner, win_margin FROM matches
            UNION ALL
            SELECT league, season, team_b AS team, winner, win_margin FROM matches
        ) t
        WHERE league = %s AND season IN ('2024', '2025', '2026')
        GROUP BY team
        """,
        (league,),
    )
    teams_record = {}
    for row in cur.fetchall():
        games = row[1] or 0
        wins = row[2] or 0
        wr = (wins / games * 100.0) if games else 0.0
        margin = float(row[4] or 0)
        # blend raw win% with margin signal; clamp/scale to 0-100 comparable to
        # the 0-100 player-rating axis
        result_score = wr * 0.7 + min(100.0, margin * 10.0) * 0.3
        teams_record[row[0]] = result_score
    cur.close()
    conn.close()

    rows = []
    for team, pids in roster.items():
        scores = []
        for pid in list(pids)[:40]:
            s = recent.get(pid)
            if not s:
                continue
            bat_matches = float(s.get("bat_matches") or 0)
            runs = float(s.get("runs") or 0)
            balls = float(s.get("balls") or 0)
            batting = s.get("batting")
            sr = s.get("sr")
            wickets = float(s.get("wickets") or 0)
            balls_bowled = float(s.get("balls_bowled") or 0)
            econ = s.get("econ")
            bat = 0.0
            if bat_matches >= 3 and batting and balls > 0 and sr:
                avgn = min(1.0, float(batting) / 40.0)
                srn = min(1.0, float(sr) / 150.0)
                bat = (avgn * 0.4 + srn * 0.6) * 100.0
            bowl = 0.0
            if balls_bowled >= 9 and wickets > 0 and econ:
                econ_n = max(0.0, 1.0 - (float(econ) - 6.0) / 8.0)
                wpm = min(1.0, (wickets / (balls_bowled / 6.0)) / 5.0)
                bowl = (econ_n * 0.5 + wpm * 0.5) * 100.0
            sc = bat * 0.6 + bowl * 0.4
            if sc > 0:
                scores.append(round(sc, 1))
        if not scores:
            rows.append({"team": team, "rating": None, "players": len(pids), "data": 0})
            continue
        top = sorted(scores, reverse=True)[:11]
        squad = sum(top) / len(top)
        result = teams_record.get(team, 0.0)
        rating = 0.7 * squad + 0.3 * result
        rows.append({"team": team, "rating": round(rating, 1),
                     "squad": round(squad, 1), "result": round(result, 1),
                     "players": len(pids), "data": len(scores)})

    rows.sort(key=lambda r: r["rating"] if r["rating"] is not None else -1, reverse=True)
    return {"league": league, "season": season, "teams": rows}