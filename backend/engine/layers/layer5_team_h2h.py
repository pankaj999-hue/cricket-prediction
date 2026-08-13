import psycopg2.extras
from ..utils import data_loader
from ..utils.data_loader import get_connection
RECENT_SEASONS = ['2024', '2025', '2026']


def calculate(team_a, team_b, venue=None):
    """
    Layer 5: Team Head-to-Head Record (Recent)
    Max points: 6
    
    H2H record from last 3 seasons only.
    """
    MAX_POINTS = 6
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Get recent H2H only, per season so current-season meetings out-weight
    # older ones (squads change season to season under the same team name).
    cursor.execute("""
        SELECT 
            season,
            COUNT(*) as total_matches,
            SUM(CASE WHEN winner = %s THEN 1 ELSE 0 END) as a_wins,
            SUM(CASE WHEN winner = %s THEN 1 ELSE 0 END) as b_wins
        FROM matches
        WHERE ((team_a = %s AND team_b = %s) OR (team_a = %s AND team_b = %s))
          AND season = ANY(%s)
          AND league = %s
        GROUP BY season
    """, (team_a, team_b, team_a, team_b, team_b, team_a, RECENT_SEASONS, data_loader.LEAGUE))
    
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if not rows or sum((r['total_matches'] or 0) for r in rows) == 0:
        return {
            "team_a_points": round(MAX_POINTS / 2, 2),
            "team_b_points": round(MAX_POINTS / 2, 2),
            "max_points": MAX_POINTS,
            "advantage": "neutral",
            "details": {"message": "No recent head-to-head data"}
        }

    # Effective H2H weights the current season double (squads drift yearly).
    effective_total = 0
    a_wins = 0
    b_wins = 0
    for r in rows:
        season_weight = 2 if r['season'] == '2026' else 1
        n = r['total_matches'] or 0
        effective_total += season_weight * n
        a_wins += season_weight * (r['a_wins'] or 0)
        b_wins += season_weight * (r['b_wins'] or 0)

    total = effective_total
    raw_total_games = sum((r['total_matches'] or 0) for r in rows)
    
    a_win_pct = (a_wins / total) * 100
    b_win_pct = (b_wins / total) * 100
    advantage = a_win_pct - b_win_pct
    
    # Distribute points
    if advantage > 40:
        points_a = MAX_POINTS * 0.9
        points_b = MAX_POINTS * 0.1
    elif advantage > 25:
        points_a = MAX_POINTS * 0.75
        points_b = MAX_POINTS * 0.25
    elif advantage > 10:
        points_a = MAX_POINTS * 0.6
        points_b = MAX_POINTS * 0.4
    elif advantage > 0:
        points_a = MAX_POINTS * 0.55
        points_b = MAX_POINTS * 0.45
    elif advantage > -10:
        points_a = MAX_POINTS * 0.45
        points_b = MAX_POINTS * 0.55
    elif advantage > -25:
        points_a = MAX_POINTS * 0.4
        points_b = MAX_POINTS * 0.6
    elif advantage > -40:
        points_a = MAX_POINTS * 0.25
        points_b = MAX_POINTS * 0.75
    else:
        points_a = MAX_POINTS * 0.1
        points_b = MAX_POINTS * 0.9
    
    # Small sample penalty — dampen toward 50-50. A 1-0 or 2-0 recent
    # H2H is noisy (and often against different-squad teams), and was a
    # big source of confident wrong calls. Weighted-current-season count
    # needs to reach 8 for full weight.
    damp = min(1.0, total / 8.0)
    points_a = MAX_POINTS/2 + (points_a - MAX_POINTS/2) * damp
    points_b = MAX_POINTS/2 + (points_b - MAX_POINTS/2) * damp
    
    return {
        "team_a_points": round(points_a, 2),
        "team_b_points": round(points_b, 2),
        "max_points": MAX_POINTS,
        "advantage": "team_a" if points_a > points_b else "team_b" if points_b > points_a else "neutral",
        "details": {
            "matches_played": raw_total_games,
            "effective_matches": total,
            "team_a_wins": a_wins,
            "team_b_wins": b_wins,
            "team_a_win_pct": round(a_win_pct, 1),
            "team_b_win_pct": round(b_win_pct, 1),
            "seasons": RECENT_SEASONS
        }
    }