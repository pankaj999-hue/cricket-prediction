import psycopg2.extras
from ..utils.data_loader import get_connection

RECENT_SEASONS = ['2024', '2025', '2026']

def calculate(team_a, team_b, venue=None):
    """Legacy method"""
    return calculate_with_players(None, None, team_a, team_b)

def calculate_with_players(team_a_players, team_b_players, team_a, team_b):
    """
    Layer 4: Player vs Player Matchups (16 points)
    Uses actual playing XII
    """
    MAX_POINTS = 16
    
    if not team_a_players or not team_b_players:
        return {
            "team_a_points": MAX_POINTS / 2,
            "team_b_points": MAX_POINTS / 2,
            "max_points": MAX_POINTS,
            "advantage": "neutral",
            "key_matchups": [],
            "details": {"message": "No player data available"}
        }
    
    # Separate batters and bowlers based on career runs/wickets (player-level,
    # not tied to this team so new-franchise players still have their history)
    team_a_batters = get_top_batters_from_12(team_a_players)
    team_b_batters = get_top_batters_from_12(team_b_players)
    team_a_bowlers = get_top_bowlers_from_12(team_a_players)
    team_b_bowlers = get_top_bowlers_from_12(team_b_players)
    
    # Calculate matchup scores
    team_a_result = calculate_batting_matchup_score(team_a_batters, team_b_bowlers)
    team_b_result = calculate_batting_matchup_score(team_b_batters, team_a_bowlers)
    
    team_a_score = team_a_result["score"]
    team_b_score = team_b_result["score"]
    key_matchups = team_a_result["key_matchups"] + team_b_result["key_matchups"]
    
    if team_a_score == 0 and team_b_score > 0:
        team_a_score = team_b_score * 0.8  # Slightly worse, not zero
    elif team_b_score == 0 and team_a_score > 0:
        team_b_score = team_a_score * 0.8
    
    total = team_a_score + team_b_score
    
    if total > 0:
        points_a = (team_a_score / total) * MAX_POINTS
        points_b = (team_b_score / total) * MAX_POINTS
    else:
        points_a = MAX_POINTS / 2
        points_b = MAX_POINTS / 2
    
    # Prevent extreme scores — floor of 20% each
    if points_a < MAX_POINTS * 0.2:
        points_a = MAX_POINTS * 0.2
        points_b = MAX_POINTS * 0.8
    if points_b < MAX_POINTS * 0.2:
        points_b = MAX_POINTS * 0.2
        points_a = MAX_POINTS * 0.8
    
    return {
        "team_a_points": round(points_a, 2),
        "team_b_points": round(points_b, 2),
        "max_points": MAX_POINTS,
        "advantage": "team_a" if points_a > points_b else "team_b" if points_b > points_a else "neutral",
        "key_matchups": key_matchups,
        "details": {
            "team_a_batting_score": round(team_a_score, 2),
            "team_b_batting_score": round(team_b_score, 2)
        }
    }

def get_top_batters_from_12(players):
    """From the 12 players, find the actual top batters by career runs.
    Player stats are used individually (not tied to this team) so that players
    who recently joined a new franchise still have their batting history."""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    player_ids = [p.get('player_id') for p in players if p.get('player_id')]
    
    if not player_ids:
        cursor.close()
        conn.close()
        return players[:6]
    
    cursor.execute("""
        SELECT batter_id as player_id, SUM(runs_batter) as total_runs
        FROM deliveries d
        JOIN matches m ON d.match_id = m.match_id
        WHERE batter_id = ANY(%s) 
          AND m.season = ANY(%s)
        GROUP BY batter_id
        ORDER BY total_runs DESC
        LIMIT 6
    """, (player_ids, RECENT_SEASONS))
    
    batters = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if len(batters) < 3:
        return players[:6]
    
    return batters

def get_top_bowlers_from_12(players):
    """From the 12 players, find the actual top bowlers by career wickets.
    Player stats are used individually (not tied to this team)."""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    player_ids = [p.get('player_id') for p in players if p.get('player_id')]
    
    if not player_ids:
        cursor.close()
        conn.close()
        return players[-6:]
    
    cursor.execute("""
        SELECT bowler_id as player_id, 
               COUNT(CASE WHEN is_wicket AND wicket_kind NOT IN ('run out') THEN 1 END) as wickets
        FROM deliveries d
        JOIN matches m ON d.match_id = m.match_id
        WHERE bowler_id = ANY(%s) 
          AND m.season = ANY(%s)
        GROUP BY bowler_id
        ORDER BY wickets DESC
        LIMIT 6
    """, (player_ids, RECENT_SEASONS))
    
    bowlers = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if len(bowlers) < 3:
        return players[-6:]
    
    return bowlers

def calculate_batting_matchup_score(batters, opposition_bowlers):
    """Calculate matchup score and return key matchups"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    total_score = 0
    matchups_count = 0
    key_matchups = []
    
    for batter in batters[:6]:
        batter_id = batter.get('player_id') or batter.get('batter_id')
        
        if not batter_id:
            continue
        
        # Get batter name
        cursor.execute("SELECT name FROM players WHERE player_id = %s", (batter_id,))
        name_result = cursor.fetchone()
        batter_name = name_result['name'] if name_result else 'Unknown'
        
        batter_scores = []
        
        for bowler in opposition_bowlers[:6]:
            bowler_id = bowler.get('player_id') or bowler.get('bowler_id')
            
            if not bowler_id:
                continue
            
            # Get bowler name
            cursor.execute("SELECT name FROM players WHERE player_id = %s", (bowler_id,))
            name_result = cursor.fetchone()
            bowler_name = name_result['name'] if name_result else 'Unknown'
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as balls_faced,
                    SUM(runs_batter) as runs_scored,
                    COUNT(CASE WHEN is_wicket AND player_out = batter THEN 1 END) as dismissals
                FROM deliveries d
                JOIN matches m ON d.match_id = m.match_id
                WHERE batter_id = %s AND bowler_id = %s
                  AND m.season = ANY(%s)
            """, (batter_id, bowler_id, RECENT_SEASONS))
            
            h2h = cursor.fetchone()
            
            if h2h and h2h['balls_faced'] >= 6:
                runs_per_ball = h2h['runs_scored'] / h2h['balls_faced']
                sr = runs_per_ball * 100
                
                if h2h['dismissals'] == 0:
                    if runs_per_ball > 1.5:
                        matchup_score = 10
                        dominance = f"{batter_name} DOMINATES {bowler_name} — {h2h['runs_scored']} runs in {h2h['balls_faced']} balls, never dismissed"
                    elif runs_per_ball > 1.0:
                        matchup_score = 8
                        dominance = f"{batter_name} scores freely vs {bowler_name} — {h2h['runs_scored']}({h2h['balls_faced']}), SR {sr:.0f}"
                    else:
                        matchup_score = 6
                        dominance = None
                elif h2h['dismissals'] == 1:
                    if runs_per_ball > 1.2:
                        matchup_score = 6
                        dominance = f"{batter_name} scores quick but {bowler_name} got him once"
                    else:
                        matchup_score = 4
                        dominance = f"{bowler_name} has edge over {batter_name}"
                else:
                    matchup_score = 2
                    dominance = f"{bowler_name} OWNS {batter_name} — dismissed {h2h['dismissals']} times"
                
                if dominance:
                    key_matchups.append(dominance)
                
                batter_scores.append(matchup_score)
        
        if batter_scores:
            total_score += sum(batter_scores) / len(batter_scores)
            matchups_count += 1
    
    cursor.close()
    conn.close()
    
    score = total_score / matchups_count if matchups_count > 0 else 0
    
    return {
        "score": score,
        "key_matchups": key_matchups
    }