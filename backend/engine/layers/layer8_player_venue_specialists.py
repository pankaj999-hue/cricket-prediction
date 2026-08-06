from ..utils.data_loader import get_player_venue_stats

def calculate(team_a, team_b, venue, team_a_players=None, team_b_players=None):
    """
    Layer 8: Player Venue Specialists
    Max points: 14
    
    Identifies players with exceptional records at this specific ground.
    A player averaging 55 at Chepauk when career avg is 30 = venue specialist.
    """
    MAX_POINTS = 14
    
    team_a_score = find_venue_specialists(team_a_players, venue) if team_a_players else 0
    team_b_score = find_venue_specialists(team_b_players, venue) if team_b_players else 0
    
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
            "team_a_specialist_score": round(team_a_score, 2),
            "team_b_specialist_score": round(team_b_score, 2)
        }
    }

def find_venue_specialists(players, venue):
    """Score a team based on venue specialist players"""
    if not players:
        return 0
    
    total_score = 0
    count = 0
    
    for player in players:
        player_id = player.get('player_id')
        if not player_id:
            continue
        
        venue_stats = get_player_venue_stats(player_id, venue)
        
        if venue_stats and venue_stats.get('matches_played', 0) >= 2:
            venue_avg = venue_stats.get('batting_average', 0) or 0
            venue_sr = venue_stats.get('strike_rate', 0) or 0
            venue_wickets = venue_stats.get('wickets_taken', 0) or 0
            venue_economy = venue_stats.get('economy_rate', 0) or 0
            
            # Batter specialist
            if venue_avg > 35 and venue_sr > 135:
                total_score += 3  # Elite venue batter
            elif venue_avg > 28 and venue_sr > 125:
                total_score += 2  # Good venue batter
            elif venue_avg > 22:
                total_score += 1  # Decent venue batter
            
            # Bowler specialist
            if venue_wickets >= 3 and venue_economy < 7.5:
                total_score += 3  # Elite venue bowler
            elif venue_wickets >= 2 and venue_economy < 8.5:
                total_score += 2  # Good venue bowler
            elif venue_wickets >= 1:
                total_score += 1  # Decent venue bowler
            
            count += 1
    
    if count > 0:
        return total_score / count
    return 0