import psycopg2
import psycopg2.extras
from app.config import DATABASE_URL

RECENT_SEASONS = ['2024', '2025', '2026']

def calculate(team_a, team_b, venue=None):
    """
    Layer 5: Team Head-to-Head Record (Recent)
    Max points: 10
    
    H2H record from last 3 seasons only.
    """
    MAX_POINTS = 10
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Get recent H2H only
    cursor.execute("""
        SELECT 
            COUNT(*) as total_matches,
            SUM(CASE WHEN winner = %s THEN 1 ELSE 0 END) as a_wins,
            SUM(CASE WHEN winner = %s THEN 1 ELSE 0 END) as b_wins
        FROM matches
        WHERE ((team_a = %s AND team_b = %s) OR (team_a = %s AND team_b = %s))
          AND season = ANY(%s)
    """, (team_a, team_b, team_a, team_b, team_b, team_a, RECENT_SEASONS))
    
    h2h = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not h2h or h2h['total_matches'] == 0:
        return {
            "team_a_points": round(MAX_POINTS / 2, 2),
            "team_b_points": round(MAX_POINTS / 2, 2),
            "max_points": MAX_POINTS,
            "advantage": "neutral",
            "details": {"message": "No recent head-to-head data"}
        }
    
    total = h2h['total_matches']
    a_wins = h2h['a_wins'] or 0
    b_wins = h2h['b_wins'] or 0
    
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
    
    # Small sample penalty
    if total < 3:
        points_a = (points_a + MAX_POINTS/2) / 2
        points_b = (points_b + MAX_POINTS/2) / 2
    
    return {
        "team_a_points": round(points_a, 2),
        "team_b_points": round(points_b, 2),
        "max_points": MAX_POINTS,
        "advantage": "team_a" if points_a > points_b else "team_b" if points_b > points_a else "neutral",
        "details": {
            "matches_played": total,
            "team_a_wins": a_wins,
            "team_b_wins": b_wins,
            "team_a_win_pct": round(a_win_pct, 1),
            "team_b_win_pct": round(b_win_pct, 1),
            "seasons": RECENT_SEASONS
        }
    }