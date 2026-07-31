from ..utils.data_loader import get_player_win_contribution
import psycopg2
import psycopg2.extras
from app.config import DATABASE_URL

RECENT_SEASONS = ['2024', '2025', '2026']

def calculate(team_a, team_b, venue):
    """Legacy method — kept for compatibility"""
    return calculate_with_players(None, None)

def calculate_with_players(team_a_players, team_b_players):
    """
    Layer 3: Win Contribution (12 points)
    Uses actual playing XII
    """
    MAX_POINTS = 12
    
    team_a_win_score = calculate_team_win_contribution(team_a_players) if team_a_players else 0
    team_b_win_score = calculate_team_win_contribution(team_b_players) if team_b_players else 0
    
    total = team_a_win_score + team_b_win_score
    
    if total > 0:
        points_a = (team_a_win_score / total) * MAX_POINTS
        points_b = (team_b_win_score / total) * MAX_POINTS
    else:
        points_a = MAX_POINTS / 2
        points_b = MAX_POINTS / 2
    
    return {
        "team_a_points": round(points_a, 2),
        "team_b_points": round(points_b, 2),
        "max_points": MAX_POINTS,
        "advantage": "team_a" if points_a > points_b else "team_b" if points_b > points_a else "neutral",
        "details": {
            "team_a_win_impact": round(team_a_win_score, 2),
            "team_b_win_impact": round(team_b_win_score, 2)
        }
    }

def calculate_team_win_contribution(players):
    """Calculate team's win contribution from actual 12 players — recent only"""
    if not players:
        return 0
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    total_score = 0
    count = 0
    
    for player in players[:8]:
        player_id = player.get('player_id')
        if not player_id:
            continue
        
        # Calculate win contribution from recent seasons only
        cursor.execute("""
            WITH player_innings AS (
                SELECT 
                    d.match_id,
                    d.innings,
                    d.batter_id,
                    d.batting_team,
                    SUM(d.runs_batter) as runs
                FROM deliveries d
                JOIN matches m ON d.match_id = m.match_id
                WHERE d.batter_id = %s AND m.season = ANY(%s)
                GROUP BY d.match_id, d.innings, d.batter_id, d.batting_team
                HAVING SUM(d.runs_batter) >= 30
            )
            SELECT 
                COUNT(DISTINCT pi.match_id) as matches_contributed,
                SUM(CASE WHEN m2.winner = pi.batting_team THEN 1 ELSE 0 END) as wins,
                CASE WHEN COUNT(DISTINCT pi.match_id) > 0 
                     THEN SUM(CASE WHEN m2.winner = pi.batting_team THEN 1 ELSE 0 END) * 100.0 / COUNT(DISTINCT pi.match_id)
                     ELSE 0 END as win_pct
            FROM player_innings pi
            JOIN matches m2 ON pi.match_id = m2.match_id
        """, (player_id, RECENT_SEASONS))
        
        contrib = cursor.fetchone()
        
        if contrib and contrib['matches_contributed'] >= 3:
            win_pct = contrib['win_pct']
            
            if win_pct > 70:
                score = 10
            elif win_pct > 60:
                score = 7
            elif win_pct > 50:
                score = 5
            elif win_pct > 40:
                score = 3
            else:
                score = 1
            
            total_score += score
            count += 1
    
    cursor.close()
    conn.close()
    
    if count > 0:
        return total_score / count
    return 0