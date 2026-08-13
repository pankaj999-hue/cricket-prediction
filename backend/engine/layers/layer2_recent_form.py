from ..utils.data_loader import get_player_recent_form, get_connection
from ..utils import data_loader

CURRENT_SEASON = '2026'

def calculate(team_a, team_b, venue):
    """Legacy method — kept for compatibility"""
    return calculate_with_players(None, None)

def calculate_with_players(team_a_players, team_b_players):
    """
    Layer 2: Recent Form (14 points)
    Uses actual playing XII
    """
    MAX_POINTS = 14
    
    team_a_form = calculate_team_form(team_a_players) if team_a_players else 0
    team_b_form = calculate_team_form(team_b_players) if team_b_players else 0
    
    total = team_a_form + team_b_form
    
    if total > 0:
        points_a = (team_a_form / total) * MAX_POINTS
        points_b = (team_b_form / total) * MAX_POINTS
    else:
        points_a = MAX_POINTS / 2
        points_b = MAX_POINTS / 2
    
    # Early-season damp: player "form" mostly aggregates innings from previous
    # seasons until the current one has a real sample. Pull the form edge
    # toward 50-50 while the current season is young.
    current_season_matches = _current_season_match_count()
    swing_scale = 0.6 + 0.4 * min(1.0, current_season_matches / 12.0)
    points_a = MAX_POINTS/2 + (points_a - MAX_POINTS/2) * swing_scale
    points_b = MAX_POINTS/2 + (points_b - MAX_POINTS/2) * swing_scale
    
    return {
        "team_a_points": round(points_a, 2),
        "team_b_points": round(points_b, 2),
        "max_points": MAX_POINTS,
        "advantage": "team_a" if points_a > points_b else "team_b" if points_b > points_a else "neutral",
        "details": {
            "team_a_form_score": round(team_a_form, 2),
            "team_b_form_score": round(team_b_form, 2),
            "current_season_matches": current_season_matches,
            "swing_scale": round(swing_scale, 2)
        }
    }

def _current_season_match_count():
    """Number of finished (result-present) matches this season for the league."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM matches WHERE season = %s AND league = %s",
            (CURRENT_SEASON, data_loader.LEAGUE),
        )
        row = cursor.fetchone()
        cursor.close()
        return int(row[0]) if row else 0
    finally:
        conn.close()

def calculate_team_form(players):
    """Calculate team form from actual 12 players"""
    if not players:
        return 0
    
    form_score = 0
    players_with_data = 0
    
    for player in players[:8]:  # Analyze top 8
        form = get_player_recent_form(player.get('player_id'))
        
        if form and form.get('avg_last_5'):
            avg = form['avg_last_5']
            trend = form.get('form_trend', 'stable')
            
            if avg > 40:
                player_score = 10
            elif avg > 30:
                player_score = 8
            elif avg > 20:
                player_score = 5
            elif avg > 10:
                player_score = 3
            else:
                player_score = 1
            
            if trend == 'rising':
                player_score *= 1.3
            elif trend == 'falling':
                player_score *= 0.7
            
            if form.get('consistency_score') and form['consistency_score'] < 20:
                player_score *= 1.2
            
            form_score += player_score
            players_with_data += 1
    
    if players_with_data > 0:
        return form_score / players_with_data
    return 0