from ..utils.data_loader import get_team_venue_record, get_venue_pitch_profile
from ..utils.constants import MIN_MATCHES_VENUE

def calculate(team_a, team_b, venue):
    """
    Layer 1: Venue Compatibility
    Max points: 9
    """
    MAX_POINTS = 9
    
    team_a_venue = get_team_venue_record(team_a, venue)
    team_b_venue = get_team_venue_record(team_b, venue)
    
    # Default values
    a_win_pct = 50.0
    b_win_pct = 50.0
    a_matches = 0
    b_matches = 0
    
    if team_a_venue and team_a_venue["matches_played"] >= MIN_MATCHES_VENUE:
        a_win_pct = float(team_a_venue["win_percentage"] or 50.0)
        a_matches = team_a_venue["matches_played"]
    
    if team_b_venue and team_b_venue["matches_played"] >= MIN_MATCHES_VENUE:
        b_win_pct = float(team_b_venue["win_percentage"] or 50.0)
        b_matches = team_b_venue["matches_played"]
    
    # If one team has no data, give home team advantage
    if a_matches == 0 and b_matches == 0:
        home = get_home_team(venue)
        if home == team_a:
            a_win_pct = 60.0
            b_win_pct = 40.0
        elif home == team_b:
            a_win_pct = 40.0
            b_win_pct = 60.0
    
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
    
    # Dampen toward 50-50 when the venue sample is thin — prevents a stale or
    # lopsided historical record from creating false confidence (the main
    # driver of confident wrong calls on upsets).
    combined = a_matches + b_matches
    damp = min(1.0, combined / 8.0) if combined > 0 else 0.5
    points_a = MAX_POINTS/2 + (points_a - MAX_POINTS/2) * damp
    points_b = MAX_POINTS/2 + (points_b - MAX_POINTS/2) * damp
    
    return {
        "team_a_points": round(float(points_a), 2),
        "team_b_points": round(float(points_b), 2),
        "max_points": MAX_POINTS,
        "advantage": "team_a" if points_a > points_b else "team_b" if points_b > points_a else "neutral",
        "details": {
            "team_a_win_pct": round(float(a_win_pct), 1),
            "team_b_win_pct": round(float(b_win_pct), 1),
            "team_a_venue_matches": int(a_matches),
            "team_b_venue_matches": int(b_matches)
        }
    }
def get_home_team(venue):
    """Map venue to home team"""
    home_map = {
        'M Chinnaswamy Stadium, Bengaluru': 'Royal Challengers Bengaluru',
        'Wankhede Stadium, Mumbai': 'Mumbai Indians',
        'MA Chidambaram Stadium, Chepauk, Chennai': 'Chennai Super Kings',
        'Eden Gardens, Kolkata': 'Kolkata Knight Riders',
        'Arun Jaitley Stadium, Delhi': 'Delhi Capitals',
        'Rajiv Gandhi International Stadium, Hyderabad': 'Sunrisers Hyderabad',
        'Narendra Modi Stadium, Ahmedabad': 'Gujarat Titans',
        'Sawai Mansingh Stadium, Jaipur': 'Rajasthan Royals',
        'BRSABV Ekana Cricket Stadium, Lucknow': 'Lucknow Super Giants',
        'Punjab Cricket Association Stadium, Mohali': 'Punjab Kings',
        'Maharaja Yadavindra Singh International Cricket Stadium, New Chandigarh': 'Punjab Kings',
        
        #cpl team
        'Kensington Oval, Bridgetown': 'Barbados Tridents',
        'Providence Stadium, Georgetown': 'Guyana Amazon Warriors',
        'Sabina Park, Kingston': 'Jamaica Kingsmen',
        'Warner Park Sporting Complex, Basseterre': 'St Kitts and Nevis Patriots',
        'Daren Sammy Cricket Ground, Gros Islet': 'St Lucia Kings',
        'Queen\'s Park Oval, Port of Spain': 'Trinbago Knight Riders',
        'Brian Lara Cricket Academy, Tarouba': 'Trinbago Knight Riders',
        'Sir Vivian Richards Stadium, North Sound': 'Antigua and Barbuda Falcons',
    }
    
    return home_map.get(venue)