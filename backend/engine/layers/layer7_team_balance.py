import psycopg2
import psycopg2.extras
from app.config import DATABASE_URL
from ..utils import data_loader

RECENT_SEASONS = ['2024', '2025', '2026']

def calculate(team_a, team_b, team_a_players=None, team_b_players=None):
    """
    Layer 7: Team Balance
    Max points: 8
    
    Analyzes structural strength of the starting XI only (11 players).
    Impact player excluded. Properly identifies all-rounders.
    """
    MAX_POINTS = 8
    
    team_a_score = analyze_balance(team_a_players, team_a) if team_a_players else 5
    team_b_score = analyze_balance(team_b_players, team_b) if team_b_players else 5
    
    total = team_a_score + team_b_score
    
    if total > 0:
        points_a = (team_a_score / total) * MAX_POINTS
        points_b = (team_b_score / total) * MAX_POINTS
    else:
        points_a = MAX_POINTS / 2
        points_b = MAX_POINTS / 2
    
    return {
        "team_a_points": round(points_a, 2),
        "team_b_points": round(points_b, 2),
        "max_points": MAX_POINTS,
        "advantage": "team_a" if points_a > points_b else "team_b" if points_b > points_a else "neutral",
        "details": {
            "team_a_balance": round(team_a_score, 2),
            "team_b_balance": round(team_b_score, 2)
        }
    }

def analyze_balance(players, team_name):
    """Score a team's structural balance out of 10 — starting XI only"""
    if not players:
        return 5
    
    # Only analyze first 11 players (starting XI, exclude 12th man/impact sub)
    active_players = players[:11] if len(players) >= 11 else players
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    player_ids = [p.get('player_id') for p in active_players if p.get('player_id')]
    
    if len(player_ids) < 8:
        cursor.close()
        conn.close()
        return 5
    
    # Get batting and bowling stats for these players
    cursor.execute("""
        SELECT 
            p.player_id,
            p.name,
            COALESCE(SUM(d_bat.runs_batter), 0) as batting_runs,
            COUNT(d_bat.id) as balls_faced,
            COUNT(DISTINCT CASE WHEN d_bowl.is_wicket AND d_bowl.wicket_kind NOT IN ('run out') THEN d_bowl.id END) as wickets
        FROM players p
        LEFT JOIN deliveries d_bat ON p.player_id = d_bat.batter_id 
            AND d_bat.match_id IN (SELECT match_id FROM matches WHERE season = ANY(%s) AND league = %s)
        LEFT JOIN deliveries d_bowl ON p.player_id = d_bowl.bowler_id 
            AND d_bowl.match_id IN (SELECT match_id FROM matches WHERE season = ANY(%s) AND league = %s)
        WHERE p.player_id = ANY(%s)
        GROUP BY p.player_id, p.name
    """, (RECENT_SEASONS, data_loader.LEAGUE, RECENT_SEASONS, data_loader.LEAGUE, player_ids))
    
    stats = cursor.fetchall()
    cursor.close()
    conn.close()
    
    all_rounders = 0
    part_time_all_rounders = 0
    pure_batters = 0
    pure_bowlers = 0
    
    for s in stats:
        runs = s['batting_runs'] or 0
        wickets = s['wickets'] or 0
        balls = s['balls_faced'] or 0
        
        # Genuine all-rounder: scores runs AND takes wickets
        if runs > 150 and wickets > 5:
            all_rounders += 1
        # Part-time all-rounder: contributes with both
        elif runs > 100 and wickets > 3:
            part_time_all_rounders += 0.5
        elif runs > 80 and wickets > 2:
            part_time_all_rounders += 0.25
        # Pure batter
        elif runs > 100 and balls > 50:
            pure_batters += 1
        # Pure bowler
        elif wickets > 5:
            pure_bowlers += 1
        # Determine by role if stats unclear
        elif balls > 100:
            pure_batters += 1
        elif wickets > 2:
            pure_bowlers += 1
    
    # Scoring
    score = 4  # baseline
    
    # Batting depth (need at least 5 proper batters)
    total_batters = pure_batters + all_rounders + (part_time_all_rounders * 0.5)
    if total_batters >= 6:
        score += 1.5
    elif total_batters >= 5:
        score += 1.0
    elif total_batters >= 4:
        score += 0.5
    
    # Bowling depth (need at least 5 bowling options)
    total_bowlers = pure_bowlers + all_rounders + (part_time_all_rounders * 0.5)
    if total_bowlers >= 6:
        score += 1.5
    elif total_bowlers >= 5:
        score += 1.0
    elif total_bowlers >= 4:
        score += 0.5
    elif total_bowlers < 4:
        score -= 1  # Penalty for too few bowlers
    
    # All-rounders bonus
    score += all_rounders * 1.0
    score += part_time_all_rounders * 0.5
    
    return min(10, max(1, score))