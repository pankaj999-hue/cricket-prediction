import psycopg2
import psycopg2.extras
from app.config import DATABASE_URL

def calculate(team_a, team_b, stage="League"):
    """
    Layer 9: Pressure Index
    Max points: 4
    
    League matches: slight edge to more experienced team.
    Knockout matches: rewards strong knockout records.
    """
    # Import here to get current value
    from ..utils.data_loader import LEAGUE
    
    MAX_POINTS = 4
    
    if stage in ("League", "Group", None, ""):
        # League match — edge to more experienced team
        a_exp = get_team_experience(team_a)
        b_exp = get_team_experience(team_b)
        
        total = a_exp + b_exp
        
        if total > 0:
            points_a = (a_exp / total) * MAX_POINTS
            points_b = (b_exp / total) * MAX_POINTS
        else:
            points_a = MAX_POINTS / 2
            points_b = MAX_POINTS / 2
        
        return {
            "team_a_points": round(points_a, 2),
            "team_b_points": round(points_b, 2),
            "max_points": MAX_POINTS,
            "advantage": "team_a" if points_a > points_b else "team_b" if points_b > points_a else "neutral",
            "details": {
                "stage": stage,
                "team_a_experience": a_exp,
                "team_b_experience": b_exp
            }
        }
    
    # Knockout matches — check historical knockout performance
    team_a_knockout_pct = get_knockout_win_pct(team_a)
    team_b_knockout_pct = get_knockout_win_pct(team_b)
    
    a_pct = team_a_knockout_pct if team_a_knockout_pct is not None else 50.0
    b_pct = team_b_knockout_pct if team_b_knockout_pct is not None else 50.0
    
    total = a_pct + b_pct
    
    if total > 0:
        points_a = (a_pct / total) * MAX_POINTS
        points_b = (b_pct / total) * MAX_POINTS
    else:
        points_a = MAX_POINTS / 2
        points_b = MAX_POINTS / 2
    
    return {
        "team_a_points": round(points_a, 2),
        "team_b_points": round(points_b, 2),
        "max_points": MAX_POINTS,
        "advantage": "team_a" if points_a > points_b else "team_b" if points_b > points_a else "neutral",
        "details": {
            "stage": stage,
            "team_a_knockout_win_pct": round(a_pct, 1),
            "team_b_knockout_win_pct": round(b_pct, 1)
        }
    }

def get_team_experience(team):
    """Get total matches played by this team in this league"""
    from ..utils.data_loader import LEAGUE
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cursor.execute("""
        SELECT COUNT(*) as total_matches
        FROM matches
        WHERE (team_a = %s OR team_b = %s)
          AND league = %s
          AND winner IS NOT NULL
    """, (team, team, LEAGUE))
    
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return result['total_matches'] if result else 0

def get_knockout_win_pct(team):
    """Get team's win percentage in knockout matches"""
    from ..utils.data_loader import LEAGUE
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total_knockouts,
            SUM(CASE WHEN winner = %s THEN 1 ELSE 0 END) as wins
        FROM matches
        WHERE (team_a = %s OR team_b = %s)
          AND stage IN ('Final', 'Semi-final', 'Qualifier', 'Qualifier 2', 'Eliminator')
          AND league = %s
          AND winner IS NOT NULL
    """, (team, team, team, LEAGUE))
    
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if result and result['total_knockouts'] > 0:
        return round((result['wins'] / result['total_knockouts']) * 100, 1)
    
    return None