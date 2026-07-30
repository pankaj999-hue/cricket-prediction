import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import psycopg2
import psycopg2.extras
from app.config import DATABASE_URL

RECENT_SEASONS = ['2024', '2025', '2026']

def get_connection():
    return psycopg2.connect(DATABASE_URL)

# ============================================
# PLAYING XI FUNCTIONS
# ============================================

def get_expected_xi(team_name):
    """Get most recent playing XII for a team (including impact sub)"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Get the most recent match for this team
    cursor.execute("""
        SELECT match_id, date
        FROM matches
        WHERE (team_a = %s OR team_b = %s)
        ORDER BY date DESC
        LIMIT 1
    """, (team_name, team_name))
    
    last_match = cursor.fetchone()
    
    if not last_match:
        cursor.close()
        conn.close()
        return get_team_players_all_time(team_name)[:12]
    
    match_id = last_match['match_id']
    
    # Get all players who played in this match
    cursor.execute("""
        SELECT DISTINCT ON (COALESCE(player_id, player_name)) 
            player_name, player_id
        FROM (
            SELECT DISTINCT d.batter as player_name, d.batter_id as player_id
            FROM deliveries d
            WHERE d.match_id = %s AND d.batting_team = %s
            UNION
            SELECT DISTINCT d.bowler as player_name, d.bowler_id as player_id
            FROM deliveries d
            WHERE d.match_id = %s AND d.bowling_team = %s
            UNION  
            SELECT DISTINCT d.non_striker as player_name, NULL as player_id
            FROM deliveries d
            WHERE d.match_id = %s AND d.batting_team = %s
        ) all_players
        WHERE player_name IS NOT NULL
        LIMIT 12
    """, (match_id, team_name, match_id, team_name, match_id, team_name))
    
    players = cursor.fetchall()
    cursor.close()
    conn.close()
        # Remove duplicates manually
    seen = set()
    unique_players = []
    for p in players:
        key = p.get('player_id') or p.get('player_name')
        if key and key not in seen:
            seen.add(key)
            unique_players.append(p)
    
    if len(unique_players) < 8:
        return get_team_players_all_time(team_name)[:12]
    
    return unique_players[:12]
    


def get_match_players(team_name, user_xi=None):
    """Get players for prediction — user XI or auto-fetch"""
    if user_xi and len(user_xi) >= 8:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        players = []
        for name in user_xi:
            cursor.execute("SELECT player_id, name FROM players WHERE name ILIKE %s LIMIT 1", (f"%{name}%",))
            result = cursor.fetchone()
            if result:
                players.append(result)
        
        cursor.close()
        conn.close()
        
        if len(players) >= 8:
            return players
    
    return get_expected_xi(team_name)

def get_team_players_all_time(team_name):
    """Fallback: get all players who ever played for a team"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cursor.execute("""
        SELECT DISTINCT p.player_id, p.name
        FROM players p
        JOIN deliveries d ON p.player_id = d.batter_id OR p.player_id = d.bowler_id
        JOIN matches m ON d.match_id = m.match_id
        WHERE (m.team_a = %s OR m.team_b = %s)
          AND (d.batting_team = %s OR d.bowling_team = %s)
    """, (team_name, team_name, team_name, team_name))
    
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

# ============================================
# TEAM & VENUE STATS (With Recency)
# ============================================

def get_team_venue_record(team, venue):
    """Get team's record at venue — recent first, fallback to all-time"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Try recent seasons first
    cursor.execute("""
        SELECT 
            venue,
            COUNT(*) as matches_played,
            SUM(CASE WHEN winner = %s THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN winner IS NOT NULL AND winner != %s THEN 1 ELSE 0 END) as losses,
            CASE WHEN COUNT(*) > 0 
                 THEN SUM(CASE WHEN winner = %s THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
                 ELSE 0 END as win_percentage
        FROM (
            SELECT team_a as team, venue, winner FROM matches 
            WHERE season = ANY(%s) AND venue = %s
            UNION ALL
            SELECT team_b as team, venue, winner FROM matches 
            WHERE season = ANY(%s) AND venue = %s
        ) tm
        WHERE team = %s
        GROUP BY venue
    """, (team, team, team, RECENT_SEASONS, venue, RECENT_SEASONS, venue, team))
    
    result = cursor.fetchone()
    
    # Fallback to all-time if not enough recent data
    if not result or result['matches_played'] < 3:
        cursor.execute("""
            SELECT 
                venue,
                COUNT(*) as matches_played,
                SUM(CASE WHEN winner = %s THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN winner IS NOT NULL AND winner != %s THEN 1 ELSE 0 END) as losses,
                CASE WHEN COUNT(*) > 0 
                     THEN SUM(CASE WHEN winner = %s THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
                     ELSE 0 END as win_percentage
            FROM (
                SELECT team_a as team, venue, winner FROM matches WHERE venue = %s
                UNION ALL
                SELECT team_b as team, venue, winner FROM matches WHERE venue = %s
            ) tm
            WHERE team = %s
            GROUP BY venue
        """, (team, team, team, venue, venue, team))
        
        result = cursor.fetchone()
    
    cursor.close()
    conn.close()
    return result

def get_team_h2h_record(team_a, team_b):
    """Get head-to-head record between two teams"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cursor.execute("""
        SELECT * FROM team_h2h_record
        WHERE (team_a = %s AND team_b = %s)
           OR (team_a = %s AND team_b = %s)
    """, (team_a, team_b, team_b, team_a))
    
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

def get_venue_pitch_profile(venue):
    """Get pitch characteristics for a venue"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cursor.execute("""
        SELECT * FROM venue_pitch_profile
        WHERE venue = %s
    """, (venue,))
    
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

# ============================================
# PLAYER STATS
# ============================================

def get_player_career_stats(player_id):
    """Get a player's career stats"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cursor.execute("""
        SELECT p.name, pcs.*
        FROM player_career_stats pcs
        JOIN players p ON pcs.player_id = p.player_id
        WHERE pcs.player_id = %s
    """, (player_id,))
    
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

def get_player_venue_stats(player_id, venue):
    """Get a player's stats at a specific venue"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cursor.execute("""
        SELECT * FROM player_venue_stats
        WHERE player_id = %s AND venue = %s
    """, (player_id, venue))
    
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

def get_player_recent_form(player_id):
    """Get a player's recent form"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cursor.execute("""
        SELECT * FROM player_recent_form
        WHERE player_id = %s
    """, (player_id,))
    
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

def get_player_win_contribution(player_id):
    """Get a player's win contribution stats"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cursor.execute("""
        SELECT * FROM player_win_contribution
        WHERE player_id = %s
    """, (player_id,))
    
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

def get_match_stage_pressure(stage):
    """Convert match stage to pressure multiplier"""
    pressure_map = {
        "Final": 1.3,
        "Qualifier": 1.2,
        "Eliminator": 1.2,
        "Semi-final": 1.2,
        "Qualifier 2": 1.15,
        "League": 1.0,
        "Group": 1.0,
    }
    return pressure_map.get(stage, 1.0)