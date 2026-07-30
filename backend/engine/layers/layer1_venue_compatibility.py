from ..utils.data_loader import get_team_venue_record, get_venue_pitch_profile
from ..utils.constants import MIN_MATCHES_VENUE

def calculate(team_a, team_b, venue):
    """
    Layer 1: Venue Compatibility
    Max points: 15
    
    Compares both teams' historical performance at this venue.
    Factors in win percentage and pitch compatibility.
    """
    MAX_POINTS = 15
    
    # Get team records at this venue
    team_a_venue = get_team_venue_record(team_a, venue)
    team_b_venue = get_team_venue_record(team_b, venue)
    venue_profile = get_venue_pitch_profile(venue)
    
    # Default if no data
    a_win_pct = 50.0
    b_win_pct = 50.0
    a_matches = 0
    b_matches = 0
    
    if team_a_venue and team_a_venue["matches_played"] >= MIN_MATCHES_VENUE:
        a_win_pct = team_a_venue["win_percentage"] or 50.0
        a_matches = team_a_venue["matches_played"]
    
    if team_b_venue and team_b_venue["matches_played"] >= MIN_MATCHES_VENUE:
        b_win_pct = team_b_venue["win_percentage"] or 50.0
        b_matches = team_b_venue["matches_played"]
    
    # Calculate the gap
    advantage = a_win_pct - b_win_pct
    
    # Convert to points
    if advantage > 20:
        points_a = MAX_POINTS
        points_b = 0
    elif advantage > 10:
        points_a = MAX_POINTS * 0.75
        points_b = MAX_POINTS * 0.25
    elif advantage > 0:
        points_a = MAX_POINTS * 0.6
        points_b = MAX_POINTS * 0.4
    elif advantage > -10:
        points_a = MAX_POINTS * 0.4
        points_b = MAX_POINTS * 0.6
    elif advantage > -20:
        points_a = MAX_POINTS * 0.25
        points_b = MAX_POINTS * 0.75
    else:
        points_a = 0
        points_b = MAX_POINTS
    
    # Reduce confidence if low sample size
    if a_matches < MIN_MATCHES_VENUE and b_matches < MIN_MATCHES_VENUE:
        # Both teams have low data — split evenly
        points_a = MAX_POINTS / 2
        points_b = MAX_POINTS / 2
    
    return {
        "team_a_points": round(points_a, 2),
        "team_b_points": round(points_b, 2),
        "max_points": MAX_POINTS,
        "advantage": "team_a" if points_a > points_b else "team_b" if points_b > points_a else "neutral",
        "details": {
            "team_a_win_pct": round(a_win_pct, 1),
            "team_b_win_pct": round(b_win_pct, 1),
            "team_a_venue_matches": a_matches,
            "team_b_venue_matches": b_matches
        }
    }