import psycopg2
import psycopg2.extras
from app.config import DATABASE_URL
from datetime import datetime, timedelta

def calculate(team_a, team_b, match_date=None):
    """
    Layer 10: Fatigue & Travel
    Max points: 3
    
    Teams playing back-to-back or with heavy travel get penalized.
    """
    MAX_POINTS = 3
    
    if not match_date:
        return {
            "team_a_points": round(MAX_POINTS / 2, 2),
            "team_b_points": round(MAX_POINTS / 2, 2),
            "max_points": MAX_POINTS,
            "advantage": "neutral",
            "details": {"message": "No match date provided"}
        }
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Check matches in last 5 days for each team
    match_date_obj = match_date if isinstance(match_date, str) else match_date.strftime('%Y-%m-%d')
    five_days_ago = (datetime.strptime(match_date_obj, '%Y-%m-%d') - timedelta(days=5)).strftime('%Y-%m-%d')
    
    cursor.execute("""
        SELECT 
            CASE WHEN team_a = %s OR team_b = %s THEN 'A' ELSE 'B' END as team,
            COUNT(*) as recent_matches
        FROM matches
        WHERE date BETWEEN %s AND %s
          AND (team_a = %s OR team_b = %s OR team_a = %s OR team_b = %s)
        GROUP BY CASE WHEN team_a = %s OR team_b = %s THEN 'A' ELSE 'B' END
    """, (team_a, team_a, five_days_ago, match_date_obj, 
          team_a, team_a, team_b, team_b, team_a, team_a))
    
    fatigue = {"A": 0, "B": 0}
    for row in cursor.fetchall():
        fatigue[row['team']] = row['recent_matches']
    
    cursor.close()
    conn.close()
    
    # Score: less fatigue = more points
    team_a_fatigue = fatigue.get('A', 0)
    team_b_fatigue = fatigue.get('B', 0)
    
    if team_a_fatigue == 0 and team_b_fatigue == 0:
        points_a = MAX_POINTS / 2
        points_b = MAX_POINTS / 2
    elif team_a_fatigue < team_b_fatigue:
        points_a = MAX_POINTS * 0.65
        points_b = MAX_POINTS * 0.35
    elif team_b_fatigue < team_a_fatigue:
        points_a = MAX_POINTS * 0.35
        points_b = MAX_POINTS * 0.65
    else:
        points_a = MAX_POINTS / 2
        points_b = MAX_POINTS / 2
    
    return {
        "team_a_points": round(points_a, 2),
        "team_b_points": round(points_b, 2),
        "max_points": MAX_POINTS,
        "advantage": "team_a" if points_a > points_b else "team_b" if points_b > points_a else "neutral",
        "details": {
            "team_a_recent_matches": team_a_fatigue,
            "team_b_recent_matches": team_b_fatigue
        }
    }