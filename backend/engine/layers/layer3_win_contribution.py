from ..utils.data_loader import get_connection
import psycopg2.extras

RECENT_SEASONS = ['2024', '2025', '2026']

MATCHES_FLOOR = 3

def calculate(team_a, team_b, venue):
    """Legacy method — kept for compatibility"""
    return calculate_with_players(None, None)

def calculate_with_players(team_a_players, team_b_players):
    """
    Layer 3: Win Contribution (13 points)
    Uses actual playing XII.

    Contribution is the average of a "batting" contribution (innings where the
    player scored 30+, weighted by the win% of those matches) and a "bowling"
    contribution (matches where the player took 3+ wickets, weighted by the
    win% of those matches) — so a team's bowling attack is no longer invisible
    to the model.
    """
    MAX_POINTS = 13

    team_a_stats = calculate_team_win_contribution(team_a_players) if team_a_players else {"score": 0}
    team_b_stats = calculate_team_win_contribution(team_b_players) if team_b_players else {"score": 0}

    team_a_win_score = team_a_stats["score"]
    team_b_win_score = team_b_stats["score"]

    total = team_a_win_score + team_b_win_score

    if total > 0:
        # If one team has no data, use a baseline of 5
        if team_a_win_score == 0:
            team_a_win_score = 5
        if team_b_win_score == 0:
            team_b_win_score = 5
        total = team_a_win_score + team_b_win_score
        points_a = (team_a_win_score / total) * MAX_POINTS
        points_b = (team_b_win_score / total) * MAX_POINTS
    else:
        # Both teams have zero data — neutral
        points_a = MAX_POINTS / 2
        points_b = MAX_POINTS / 2
    return {
        "team_a_points": round(points_a, 2),
        "team_b_points": round(points_b, 2),
        "max_points": MAX_POINTS,
        "advantage": "team_a" if points_a > points_b else "team_b" if points_b > points_a else "neutral",
        "details": {
            "team_a_win_impact": round(team_a_win_score, 2),
            "team_b_win_impact": round(team_b_win_score, 2),
            "team_a_batting_impact": round(team_a_stats.get("batting", 0) or 0, 2),
            "team_a_bowling_impact": round(team_a_stats.get("bowling", 0) or 0, 2),
            "team_b_batting_impact": round(team_b_stats.get("batting", 0) or 0, 2),
            "team_b_bowling_impact": round(team_b_stats.get("bowling", 0) or 0, 2),
        }
    }

def calculate_team_win_contribution(players):
    """Average of per-player batting + bowling win contribution (recent only)."""
    if not players:
        return {"score": 0}

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    total_score = 0
    batting_total = 0
    bowling_total = 0
    batting_count = 0
    bowling_count = 0
    count = 0

    for player in players[:8]:
        player_id = player.get('player_id')
        if not player_id:
            continue

        bat_score = _batting_win_score(cursor, player_id)
        bowl_score = _bowling_win_score(cursor, player_id)

        if bat_score is not None:
            batting_count += 1
            batting_total += bat_score
        if bowl_score is not None:
            bowling_count += 1
            bowling_total += bowl_score

        scores = [s for s in (bat_score, bowl_score) if s is not None]
        if scores:
            total_score += sum(scores) / len(scores)
            count += 1

    cursor.close()
    conn.close()

    return {
        "score": total_score / count if count > 0 else 0,
        "batting": batting_total / batting_count if batting_count > 0 else 0,
        "bowling": bowling_total / bowling_count if bowling_count > 0 else 0,
    }

def _bucket_win_pct(win_pct):
    """Map a contribution win% to the 1-10 match-winning scale."""
    if win_pct > 70:
        return 10
    if win_pct > 60:
        return 7
    if win_pct > 50:
        return 5
    if win_pct > 40:
        return 3
    return 1

def _batting_win_score(cursor, player_id):
    """Innings where the player scored 30+ in recent seasons; win% of those
    matches bucketed. None when the player has too few qualifying innings."""
    cursor.execute("""
        WITH player_innings AS (
            SELECT
                d.match_id,
                d.batting_team,
                SUM(d.runs_batter) as runs
            FROM deliveries d
            JOIN matches m ON d.match_id = m.match_id
            WHERE d.batter_id = %s AND m.season = ANY(%s)
            GROUP BY d.match_id, d.batting_team
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
    if not contrib or contrib['matches_contributed'] < MATCHES_FLOOR:
        return None
    return _bucket_win_pct(contrib['win_pct'])

def _bowling_win_score(cursor, player_id):
    """Matches where the player took 3+ wickets in recent seasons; win% of
    those matches bucketed. None when the player has too few such matches."""
    cursor.execute("""
        WITH bowler_wickets AS (
            SELECT
                d.match_id,
                d.bowling_team,
                COUNT(*) FILTER (WHERE d.is_wicket AND d.wicket_kind NOT IN ('run out')) as wkts
            FROM deliveries d
            JOIN matches m ON d.match_id = m.match_id
            WHERE d.bowler_id = %s AND m.season = ANY(%s)
            GROUP BY d.match_id, d.bowling_team
            HAVING COUNT(*) FILTER (WHERE d.is_wicket AND d.wicket_kind NOT IN ('run out')) >= 3
        )
        SELECT
            COUNT(DISTINCT bw.match_id) as matches_contributed,
            SUM(CASE WHEN m2.winner = bw.bowling_team THEN 1 ELSE 0 END) as wins,
            CASE WHEN COUNT(DISTINCT bw.match_id) > 0
                 THEN SUM(CASE WHEN m2.winner = bw.bowling_team THEN 1 ELSE 0 END) * 100.0 / COUNT(DISTINCT bw.match_id)
                 ELSE 0 END as win_pct
        FROM bowler_wickets bw
        JOIN matches m2 ON bw.match_id = m2.match_id
    """, (player_id, RECENT_SEASONS))

    contrib = cursor.fetchone()
    if not contrib or contrib['matches_contributed'] < MATCHES_FLOOR:
        return None
    return _bucket_win_pct(contrib['win_pct'])