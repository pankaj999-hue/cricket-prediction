import psycopg2.extras
from ..utils import data_loader
from ..utils.data_loader import get_connection, get_player_career_stats
RECENT_SEASONS = ['2024', '2025', '2026']

# Pitch types a user can supply in real time (frontend / live data):
#   'batting'  -> the pitch favors the stronger batting lineup
#   'bowling'  -> the pitch favors the stronger bowling attack
#   'neutral'  -> no meaningful pitch edge (or unknown)


def calculate(team_a, team_b, venue, match_date=None, toss_winner=None, toss_decision=None,
              pitch_type=None, team_a_players=None, team_b_players=None):
    """
    Layer 6: Toss & Pitch Conditions
    Max points: 8

    Primary signal: real-time pitch type. When a pitch_type is supplied, the
    engine reads the two lineups and figures out WHICH team the pitch favors:
      - batting pitch  -> higher batting rating holds the edge
      - bowling pitch  -> stronger bowling attack holds the edge
    The toss then compounds it: making the correct call for the pitch rewards
    the toss winner, a wrong call gives the edge to the opposition.

    Fallback (no pitch_type): historical venue bias (chase vs defend) at the
    ground, rewarding correct toss decisions the way it used to.
    """
    MAX_POINTS = 8
    venue_bias = "neutral"
    pitch_bias = None
    pitch_kind = None

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # ---------- 1. Pitch-driven edge (real-time input) ----------
    if pitch_type in ("batting", "bowling"):
        if pitch_type == "batting":
            a_rating = team_batting_rating(team_a_players)
            b_rating = team_batting_rating(team_b_players)
        else:
            a_rating = team_bowling_rating(team_a_players)
            b_rating = team_bowling_rating(team_b_players)

        total = a_rating + b_rating
        if total > 0:
            pitch_bias = (a_rating / total, b_rating / total)
            pitch_kind = pitch_type
            venue_bias = "bat_first" if pitch_type == "batting" else "chase"

    # ---------- 2. Fallback: historical venue bias ----------
    if pitch_bias is None:
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
            WHERE venue = %s AND league = %s
        """, (venue, data_loader.LEAGUE))

        profile = cursor.fetchone()

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

        if profile and (profile['total_matches'] or 0) > 0:
            bat_first_pct = profile.get('bat_first_win_pct', 50) or 50
            chase_pct = profile.get('chase_win_pct', 50) or 50
            bat_first_matches = profile.get('bat_first_matches', 0) or 0
            chase_matches = profile.get('chase_matches', 0) or 0

            if bat_first_matches >= 2 and bat_first_pct > chase_pct + 10:
                venue_bias = "bat_first"
            elif chase_matches >= 2 and chase_pct > bat_first_pct + 10:
                venue_bias = "chase"

    cursor.close()
    conn.close()

    # ---------- 3. Build points ----------
    # Base: the edge from pitch (or 50-50 if no pitch data)
    if pitch_bias:
        points_a = MAX_POINTS * pitch_bias[0]
        points_b = MAX_POINTS * pitch_bias[1]
    else:
        points_a = MAX_POINTS / 2
        points_b = MAX_POINTS / 2

    # Toss compounds the pitch edge
    if toss_winner and toss_decision and pitch_kind:
        ideal = "bat" if pitch_kind == "batting" else "field"
        if toss_decision == ideal:
            # Right call — toss winner gets a swing toward them
            if toss_winner == team_a:
                points_a = points_a + (MAX_POINTS - points_a) * 0.25
            else:
                points_b = points_b + (MAX_POINTS - points_b) * 0.25
        else:
            # Wrong call — edge swings to the opposition
            if toss_winner == team_a:
                points_a = points_a - points_a * 0.25
            else:
                points_b = points_b - points_b * 0.25
        total_p = points_a + points_b
        if total_p > 0:
            points_a, points_b = points_a / total_p * MAX_POINTS, points_b / total_p * MAX_POINTS

    # Fallback venue-bias toss logic (no pitch_type supplied)
    elif toss_winner and toss_decision and venue_bias != "neutral":
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

    # Floor: never fully crush a team on this layer
    if points_a < MAX_POINTS * 0.2:
        points_a = MAX_POINTS * 0.2
    if points_b < MAX_POINTS * 0.2:
        points_b = MAX_POINTS * 0.2
    total_p = points_a + points_b
    if total_p > 0:
        points_a, points_b = points_a / total_p * MAX_POINTS, points_b / total_p * MAX_POINTS

    return {
        "team_a_points": round(points_a, 2),
        "team_b_points": round(points_b, 2),
        "max_points": MAX_POINTS,
        "advantage": "team_a" if points_a > points_b else "team_b" if points_b > points_a else "neutral",
        "details": {
            "venue_bias": venue_bias,
            "pitch_type": pitch_type,
            "pitch_edge": pitch_kind,
            "toss_known": toss_winner is not None,
            "toss_winner": toss_winner,
            "toss_decision": toss_decision,
            "team_a_pitch_ratio": round(pitch_bias[0], 3) if pitch_bias else None,
            "team_b_pitch_ratio": round(pitch_bias[1], 3) if pitch_bias else None,
        }
    }


def team_batting_rating(players):
    """Average normalized batting strength of a lineup (avg + strike rate)."""
    if not players:
        return 0
    values = []
    for p in players[:7]:
        pid = p.get('player_id')
        if not pid:
            continue
        stats = get_player_career_stats(pid)
        if not stats:
            continue
        avg = float(stats.get('batting_average') or 0)
        sr = float(stats.get('strike_rate') or 0)
        mp = float(stats.get('matches_played') or 0)
        if mp >= 3 and avg > 0 and sr > 0:
            avg_n = min(1.0, avg / 40.0)
            sr_n = min(1.0, sr / 150.0)
            values.append(avg_n * 0.4 + sr_n * 0.6)
    return sum(values) / len(values) if values else 0


def team_bowling_rating(players):
    """Average normalized bowling strength of a lineup (economy + wickets/match)."""
    if not players:
        return 0
    values = []
    for p in players[:7]:
        pid = p.get('player_id')
        if not pid:
            continue
        stats = get_player_career_stats(pid)
        if not stats:
            continue
        w = float(stats.get('wickets_taken') or 0)
        mp = float(stats.get('matches_played') or 0)
        econ = float(stats.get('economy_rate') or 0)
        if mp >= 3 and w > 0 and econ > 0:
            econ_n = max(0.0, 1.0 - (econ - 6.0) / 8.0)
            wpm = min(1.0, (w / mp) / 2.0)
            values.append(econ_n * 0.5 + wpm * 0.5)
    return sum(values) / len(values) if values else 0
