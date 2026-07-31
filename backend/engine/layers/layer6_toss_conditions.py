import psycopg2
import psycopg2.extras
from app.config import DATABASE_URL

RECENT_SEASONS = ['2024', '2025', '2026']

def calculate(team_a, team_b, venue, match_date=None, toss_winner=None, toss_decision=None):
    """
    Layer 6: Toss & Conditions
    Max points: 8
    
    Recent toss impact, chasing vs defending advantage at this venue.
    Rewards correct toss decisions, penalizes wrong ones.
    """
    MAX_POINTS = 8
    venue_bias = "neutral"  # DEFAULT SET HERE FIRST
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Get venue stats from recent seasons
    cursor.execute("""
        SELECT 
            COUNT(*) as total_matches,
            SUM(CASE WHEN toss_decision = 'bat' THEN 1 ELSE 0 END) as bat_first_matches,
            SUM(CASE WHEN toss_decision = 'field' THEN 1 ELSE 0 END) as chase_matches,
            SUM(CASE WHEN toss_decision = 'bat' AND winner = toss_winner THEN 1 ELSE 0 END) * 100.0 / 
                NULLIF(SUM(CASE WHEN toss_decision = 'bat' THEN 1 ELSE 0 END), 0) as bat_first_win_pct,
            SUM(CASE WHEN toss_decision = 'field' AND winner = toss_winner THEN 1 ELSE 0 END) * 100.0 / 
                NULLIF(SUM(CASE WHEN toss_decision = 'field' THEN 1 ELSE 0 END), 0) as chase_win_pct,
            SUM(CASE WHEN winner = toss_winner THEN 1 ELSE 0 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as toss_win_match_pct
        FROM matches
        WHERE venue = %s AND season = ANY(%s)
    """, (venue, RECENT_SEASONS))
    
    profile = cursor.fetchone()
    
    # Fallback to all-time if no recent data
    if not profile or (profile['total_matches'] or 0) < 3:
        cursor.execute("""
            SELECT 
                COUNT(*) as total_matches,
                SUM(CASE WHEN toss_decision = 'bat' THEN 1 ELSE 0 END) as bat_first_matches,
                SUM(CASE WHEN toss_decision = 'field' THEN 1 ELSE 0 END) as chase_matches,
                SUM(CASE WHEN toss_decision = 'bat' AND winner = toss_winner THEN 1 ELSE 0 END) * 100.0 / 
                    NULLIF(SUM(CASE WHEN toss_decision = 'bat' THEN 1 ELSE 0 END), 0) as bat_first_win_pct,
                SUM(CASE WHEN toss_decision = 'field' AND winner = toss_winner THEN 1 ELSE 0 END) * 100.0 / 
                    NULLIF(SUM(CASE WHEN toss_decision = 'field' THEN 1 ELSE 0 END), 0) as chase_win_pct,
                SUM(CASE WHEN winner = toss_winner THEN 1 ELSE 0 END) * 100.0 / 
                    NULLIF(COUNT(*), 0) as toss_win_match_pct
            FROM matches
            WHERE venue = %s
        """, (venue,))
        
        profile = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if not profile or (profile['total_matches'] or 0) == 0:
        return {
            "team_a_points": round(MAX_POINTS / 2, 2),
            "team_b_points": round(MAX_POINTS / 2, 2),
            "max_points": MAX_POINTS,
            "advantage": "neutral",
            "details": {
                "venue_bias": "neutral",
                "message": "No venue data available"
            }
        }
    
    bat_first_pct = profile.get('bat_first_win_pct', 50) or 50
    chase_pct = profile.get('chase_win_pct', 50) or 50
    toss_impact = profile.get('toss_win_match_pct', 50) or 50
    bat_first_matches = profile.get('bat_first_matches', 0) or 0
    chase_matches = profile.get('chase_matches', 0) or 0
    
    # Determine venue bias
    if bat_first_matches >= 2 and bat_first_pct > chase_pct + 10:
        venue_bias = "bat_first"
    elif chase_matches >= 2 and chase_pct > bat_first_pct + 10:
        venue_bias = "chase"
    else:
        venue_bias = "neutral"
    
    # Calculate points based on toss
    if toss_winner and toss_decision:
        if venue_bias == "bat_first" and toss_decision == "bat":
            advantage_team = toss_winner
        elif venue_bias == "chase" and toss_decision == "field":
            advantage_team = toss_winner
        elif venue_bias == "bat_first" and toss_decision == "field":
            advantage_team = team_a if toss_winner == team_b else team_b
        elif venue_bias == "chase" and toss_decision == "bat":
            advantage_team = team_a if toss_winner == team_b else team_b
        else:
            advantage_team = None
        
        if advantage_team == team_a:
            points_a = MAX_POINTS * 0.75
            points_b = MAX_POINTS * 0.25
        elif advantage_team == team_b:
            points_a = MAX_POINTS * 0.25
            points_b = MAX_POINTS * 0.75
        else:
            points_a = MAX_POINTS / 2
            points_b = MAX_POINTS / 2
    else:
        points_a = MAX_POINTS / 2
        points_b = MAX_POINTS / 2
    
    return {
        "team_a_points": round(points_a, 2),
        "team_b_points": round(points_b, 2),
        "max_points": MAX_POINTS,
        "advantage": "team_a" if points_a > points_b else "team_b" if points_b > points_a else "neutral",
        "details": {
            "venue_bias": venue_bias,
            "bat_first_win_pct": round(bat_first_pct, 1),
            "chase_win_pct": round(chase_pct, 1),
            "toss_match_win_pct": round(toss_impact, 1),
            "toss_known": toss_winner is not None,
            "toss_winner": toss_winner,
            "toss_decision": toss_decision,
            "matches_analyzed": profile['total_matches']
        }
    }