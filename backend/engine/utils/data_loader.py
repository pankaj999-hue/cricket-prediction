
import sys
import os
import threading
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool
from app.config import DATABASE_URL

RECENT_SEASONS = ['2024', '2025', '2026']
LEAGUE = 'IPL'  # Default, overridden by predictor

_POOL = None
_POOL_LOCK = threading.Lock()


def _get_pool():
    """Lazily build a shared PostgreSQL connection pool."""
    global _POOL
    if _POOL is None:
        with _POOL_LOCK:
            if _POOL is None:
                _POOL = ThreadedConnectionPool(1, 20, DATABASE_URL)
    return _POOL


class _PooledConnection:
    """Wrapper around a pooled psycopg2 connection. Exposes the same API but
    `close()` returns the connection to the pool instead of destroying it, so
    every existing caller (routers, services, layers) gets pooling for free."""

    __slots__ = ("_conn",)

    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        conn, self._conn = self._conn, None
        if conn is None:
            return
        try:
            conn.rollback()
        except Exception:
            _get_pool().putconn(conn, close=True)
            return
        _get_pool().putconn(conn)


def get_connection():
    return _PooledConnection(_get_pool().getconn())

def normalize_venue(venue_name):
    """Map all venue name variations to a standard name"""
    if not venue_name:
        return venue_name
    
    v = venue_name.lower()
    
    if 'wankhede' in v: return 'Wankhede Stadium, Mumbai'
    if 'brabourne' in v: return 'Brabourne Stadium, Mumbai'
    if 'dy patil' in v: return 'DY Patil Stadium, Navi Mumbai'
    if 'chinnaswamy' in v: return 'M Chinnaswamy Stadium, Bengaluru'
    if 'chepauk' in v or 'chidambaram' in v: return 'MA Chidambaram Stadium, Chepauk, Chennai'
    if 'eden' in v: return 'Eden Gardens, Kolkata'
    if 'arun' in v or 'kotla' in v or 'feroz' in v: return 'Arun Jaitley Stadium, Delhi'
    if 'dehradun' in v: return 'Rajiv Gandhi International Cricket Stadium, Dehradun'
    if 'rajiv gandhi' in v or 'uppal' in v: return 'Rajiv Gandhi International Stadium, Hyderabad'
    if 'narendra modi' in v or 'motera' in v: return 'Narendra Modi Stadium, Ahmedabad'
    if 'sawai' in v or 'mansingh' in v: return 'Sawai Mansingh Stadium, Jaipur'
    if 'dharamsala' in v or 'hpca' in v: return 'HPCA Stadium, Dharamsala'
    if 'mohali' in v or 'punjab cricket' in v or 'pca' in v: return 'Punjab Cricket Association Stadium, Mohali'
    if 'maharaja yadavindra' in v or 'new chandigarh' in v: return 'Maharaja Yadavindra Singh International Cricket Stadium, New Chandigarh'
    if 'ekana' in v or 'atal bihari' in v: return 'BRSABV Ekana Cricket Stadium, Lucknow'
    if 'guwahati' in v or 'barsapara' in v: return 'Barsapara Cricket Stadium, Guwahati'
    if 'indore' in v or 'holkar' in v: return 'Holkar Cricket Stadium, Indore'
    if 'raipur' in v or 'shaheed' in v: return 'Shaheed Veer Narayan Singh International Stadium, Raipur'
    if 'ranchi' in v or 'jsca' in v: return 'JSCA International Stadium Complex, Ranchi'
    if 'visakhapatnam' in v or 'vizag' in v or 'dr ys' in v: return 'Dr YS Rajasekhara Reddy Cricket Stadium, Visakhapatnam'
    if 'pune' in v or 'maharashtra cricket' in v or 'mca' in v: return 'Maharashtra Cricket Association Stadium, Pune'
    if 'thiruvananthapuram' in v or 'trivandrum' in v or 'greenfield' in v: return 'Greenfield International Stadium, Thiruvananthapuram'
    if 'cuttack' in v or 'barabati' in v: return 'Barabati Stadium, Cuttack'
    if 'kochi' in v or 'jawaharlal' in v: return 'Jawaharlal Nehru Stadium, Kochi'
    if 'nagpur' in v or 'vidarbha' in v or 'vca' in v: return 'Vidarbha Cricket Association Stadium, Nagpur'
    if 'green park' in v: return 'Green Park, Kanpur'
    if 'nehru' in v: return 'Nehru Stadium, Kochi'
    if 'saurashtra' in v: return 'Saurashtra Cricket Association Stadium, Rajkot'
    if 'sahara' in v: return 'Subrata Roy Sahara Stadium, Pune'
    if 'dubai' in v: return 'Dubai International Cricket Stadium, Dubai'
    if 'abu dhabi' in v: return 'Sheikh Zayed Stadium, Abu Dhabi'
    if 'sharjah' in v: return 'Sharjah Cricket Stadium, Sharjah'
    
    # CPL Venues
    if 'kensington' in v or 'bridgetown' in v:
        return 'Kensington Oval, Bridgetown'
    if 'sabina' in v or 'kingston' in v:
        return 'Sabina Park, Kingston'
    if 'daren' in v or 'gros islet' in v or 'st lucia' in v:
        return 'Daren Sammy Cricket Ground, Gros Islet'
    if 'providence' in v or 'guyana' in v or 'georgetown' in v:
        return 'Providence Stadium, Georgetown'
    if 'warner' in v or 'basseterre' in v or 'st kitts' in v:
        return 'Warner Park Sporting Complex, Basseterre'
    if 'brian lara' in v or 'tarouba' in v:
        return 'Brian Lara Cricket Academy, Tarouba'
    if 'queen\'s park' in v or 'port of spain' in v:
        return 'Queen\'s Park Oval, Port of Spain'
    if 'arnos' in v or 'kingstown' in v or 'st vincent' in v:
        return 'Arnos Vale Stadium, Kingstown'
    if 'vivian richards' in v or 'north sound' in v or 'antigua' in v:
        return 'Sir Vivian Richards Stadium, North Sound'
    
    return venue_name

# ============================================
# PLAYING XI FUNCTIONS
# ============================================
def get_squad_players(team_name, season='2026'):
    """Get players from pre-loaded squad table with fuzzy name matching"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cursor.execute("""
        SELECT s.player_name, p.player_id, p.name
        FROM squads s
        LEFT JOIN players p ON LOWER(p.name) = LOWER(s.player_name)
        WHERE s.team = %s AND s.season = %s AND s.league = %s
    """, (team_name, season, LEAGUE))
    
    results = cursor.fetchall()
    
    for r in results:
        if r['player_id'] is None:
            parts = r['player_name'].split()
            if len(parts) >= 2:
                last_name = parts[-1]
                first_name = parts[0].lower()
                first_initial = first_name[0]

                # Candidates who actually played FOR this team (role-aware)
                cursor.execute("""
                    SELECT DISTINCT p.player_id, p.name
                    FROM players p
                    JOIN deliveries d ON p.player_id = d.batter_id OR p.player_id = d.bowler_id
                    JOIN matches m ON d.match_id = m.match_id
                    WHERE p.name ILIKE %s
                      AND m.league = %s
                      AND ((p.player_id = d.batter_id AND d.batting_team = %s)
                        OR (p.player_id = d.bowler_id AND d.bowling_team = %s))
                    ORDER BY p.name
                """, (f"%{last_name}%", LEAGUE, team_name, team_name))
                candidates = cursor.fetchall()

                # Fallback: search surname globally (players new to this team)
                if not candidates:
                    cursor.execute("""
                        SELECT player_id, name FROM players
                        WHERE name ILIKE %s
                        ORDER BY name
                    """, (f"%{last_name}%",))
                    candidates = cursor.fetchall()

                match = None
                if candidates:
                    # Player's first name must appear (or share an initial) in the
                    # matched name, otherwise a same-surname player may be picked.
                    preferred = [
                        c for c in candidates
                        if first_name in c['name'].lower() or first_initial in c['name'].lower()
                    ]
                    pool = preferred if preferred else []
                    if len(pool) == 1:
                        match = pool[0]
                    elif len(pool) > 1:
                        full_name = ' '.join(parts).lower()
                        for c in pool:
                            if full_name in c['name'].lower() or c['name'].lower() in full_name:
                                match = c
                                break
                        # Still ambiguous — leave unresolved rather than guess.

                if match:
                    r['player_id'] = match['player_id']
                    r['name'] = match['name']
    
    cursor.close()
    conn.close()
    return results
def get_expected_xi(team_name):
    """Get most recent playing XII for a team (including impact sub)"""
    
    squad = get_squad_players(team_name)
    if squad and len(squad) >= 8:
        return squad[:12]
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    

    
    cursor.execute("""
        SELECT match_id, date
        FROM matches
        WHERE (team_a = %s OR team_b = %s)
          AND league = %s
        ORDER BY date DESC
        LIMIT 1
    """, (team_name, team_name, LEAGUE))
    
    last_match = cursor.fetchone()
    
    if not last_match:
        cursor.close()
        conn.close()
        return get_team_players_all_time(team_name)[:12]
    
    match_id = last_match['match_id']
    
    cursor.execute("""
        SELECT player_name, MAX(player_id) as player_id
        FROM (
            SELECT d.batter as player_name, d.batter_id as player_id
            FROM deliveries d
            WHERE d.match_id = %s AND d.batting_team = %s
            UNION
            SELECT d.bowler as player_name, d.bowler_id as player_id
            FROM deliveries d
            WHERE d.match_id = %s AND d.bowling_team = %s
            UNION
            SELECT d.non_striker as player_name, NULL as player_id
            FROM deliveries d
            WHERE d.match_id = %s AND d.batting_team = %s
        ) all_players
        WHERE player_name IS NOT NULL
        GROUP BY player_name
        ORDER BY player_name
        LIMIT 12
    """, (match_id, team_name, match_id, team_name, match_id, team_name))
    
    players = cursor.fetchall()
    cursor.close()
    conn.close()
    
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
          AND m.league = %s
    """, (team_name, team_name, team_name, team_name, LEAGUE))
    
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

# ============================================
# TEAM & VENUE STATS (With Recency)
# ============================================

def get_team_venue_record(team, venue):
    """Get team's record at venue — recent first, fallback to all-time"""
    venue = normalize_venue(venue)
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
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
            WHERE season = ANY(%s) AND venue = %s AND league = %s
            UNION ALL
            SELECT team_b as team, venue, winner FROM matches 
            WHERE season = ANY(%s) AND venue = %s AND league = %s
        ) tm
        WHERE team = %s
        GROUP BY venue
    """, (team, team, team, RECENT_SEASONS, venue, LEAGUE, RECENT_SEASONS, venue, LEAGUE, team))
    
    result = cursor.fetchone()
    
    if not result or result['matches_played'] == 0:
        cursor.close()
        conn.close()
        return None
    
    if result['matches_played'] < 3:
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
                SELECT team_a as team, venue, winner FROM matches WHERE venue = %s AND league = %s
                UNION ALL
                SELECT team_b as team, venue, winner FROM matches WHERE venue = %s AND league = %s
            ) tm
            WHERE team = %s
            GROUP BY venue
        """, (team, team, team, venue, LEAGUE, venue, LEAGUE, team))
        
        all_time = cursor.fetchone()
        if all_time and all_time['matches_played'] > result['matches_played']:
            result = all_time
    
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
    venue = normalize_venue(venue)
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
    venue = normalize_venue(venue)
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