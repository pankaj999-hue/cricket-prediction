from ..utils.data_loader import get_player_win_contribution

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
    """Calculate team's win contribution from actual 12 players"""
    if not players:
        return 0
    
    total_score = 0
    count = 0
    
    for player in players[:8]:
        contrib = get_player_win_contribution(player.get('player_id'))
        
        if contrib and contrib.get('win_percentage'):
            win_pct = contrib['win_percentage']
            matches = contrib.get('matches_with_contribution', 0)
            
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
            
            if matches > 20:
                score *= 1.2
            
            total_score += score
            count += 1
    
    if count > 0:
        return total_score / count
    return 0