from .layers import (layer1_venue_compatibility, layer2_recent_form, 
                      layer3_win_contribution, layer4_player_matchups,
                      layer5_team_h2h,layer6_toss_conditions,layer7_team_balance, layer8_player_venue_specialists,
                      layer9_pressure_index, layer10_fatigue_travel)
from .utils.data_loader import get_match_players
from .utils import data_loader

from .utils.constants import CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_MEDIUM_CPL, GATE_LOW_CONFIDENCE, NO_BET_LABEL

def predict_match(team_a, team_b, venue, match_date=None, stage="League", 
                  team_a_xi=None, team_b_xi=None, toss_winner=None,toss_decision=None,league='IPL',
                  pitch_type=None):
    """
    Main prediction function.
    Runs all 10 layers and returns final prediction.

    pitch_type: 'batting' | 'bowling' | 'neutral' | None — supplied in real time
    (e.g. from the frontend) so Layer 6 can judge which lineup the pitch favors.
    """
    data_loader.LEAGUE = league
    
    print(f"\n{'='*50}")
    print(f"PREDICTION: {team_a} vs {team_b}")
    print(f"Venue: {venue}")
    print(f"Stage: {stage}")
    print(f"{'='*50}\n")
    
    # Get playing XIs
    print("Fetching playing XIs...")
    team_a_players = get_match_players(team_a, team_a_xi)
    team_b_players = get_match_players(team_b, team_b_xi)
    
    if team_a_players:
        print(f"  {team_a}: {min(len(team_a_players), 11)} active players")
        names = []
        for p in team_a_players[:5]:
            name = p.get('player_name') or p.get('name', 'Unknown')
            if name and name != 'Unknown':
                names.append(str(name))
        if names:
            print(f"    Players: {', '.join(names)}")
    
    if team_b_players:
        print(f"  {team_b}: {min(len(team_b_players), 11)} active players")
        names = []
        for p in team_b_players[:5]:
            name = p.get('player_name') or p.get('name', 'Unknown')
            if name and name != 'Unknown':
                names.append(str(name))
        if names:
            print(f"    Players: {', '.join(names)}")
        print()
    
    results = {}
    total_a = 0
    total_b = 0
    
    # Layer 1: Venue Compatibility (15 points)
    print("[Layer 1] Venue Compatibility...")
    l1 = layer1_venue_compatibility.calculate(team_a, team_b, venue)
    results["layer1"] = l1
    total_a += l1["team_a_points"]
    total_b += l1["team_b_points"]
    print(f"  {team_a}: {l1['team_a_points']} | {team_b}: {l1['team_b_points']} (max {l1['max_points']})")
    
    # Layer 2: Recent Form (12 points)
    print("[Layer 2] Recent Form...")
    l2 = layer2_recent_form.calculate_with_players(team_a_players, team_b_players)
    results["layer2"] = l2
    total_a += l2["team_a_points"]
    total_b += l2["team_b_points"]
    print(f"  {team_a}: {l2['team_a_points']} | {team_b}: {l2['team_b_points']} (max {l2['max_points']})")
    
    # Layer 3: Win Contribution (12 points)
    print("[Layer 3] Win Contribution...")
    l3 = layer3_win_contribution.calculate_with_players(team_a_players, team_b_players)
    results["layer3"] = l3
    total_a += l3["team_a_points"]
    total_b += l3["team_b_points"]
    print(f"  {team_a}: {l3['team_a_points']} | {team_b}: {l3['team_b_points']} (max {l3['max_points']})")
    
    # Layer 4: Player Matchups (15 points)
    print("[Layer 4] Player Matchups...")
    l4 = layer4_player_matchups.calculate_with_players(team_a_players, team_b_players, team_a, team_b)
    results["layer4"] = l4
    total_a += l4["team_a_points"]
    total_b += l4["team_b_points"]
    print(f"  {team_a}: {l4['team_a_points']} | {team_b}: {l4['team_b_points']} (max {l4['max_points']})")
    
    # Print key matchups
    if l4.get("key_matchups"):
        print("\n  ** Key Player Matchups:")
        for matchup in l4["key_matchups"][:5]:
            print(f"     - {matchup}")
        print()
    
    print("[Layer 5] Team H2H Record...")
    l5 = layer5_team_h2h.calculate(team_a, team_b, venue)
    results["layer5"] = l5
    total_a += l5["team_a_points"]
    total_b += l5["team_b_points"]
    print(f"  {team_a}: {l5['team_a_points']} | {team_b}: {l5['team_b_points']} (max {l5['max_points']})")
    
    print("[Layer 6] Toss & Conditions...")
    l6 = layer6_toss_conditions.calculate(team_a, team_b, venue, match_date, toss_winner, toss_decision,
                                          pitch_type, team_a_players, team_b_players)
    results["layer6"] = l6
    total_a += l6["team_a_points"]
    total_b += l6["team_b_points"]
    print(f"  {team_a}: {l6['team_a_points']} | {team_b}: {l6['team_b_points']} (max {l6['max_points']})")
    
    print("[Layer 7] Team Balance...")
    l7 = layer7_team_balance.calculate(team_a, team_b, team_a_players, team_b_players)
    results["layer7"] = l7
    total_a += l7["team_a_points"]
    total_b += l7["team_b_points"]
    print(f"  {team_a}: {l7['team_a_points']} | {team_b}: {l7['team_b_points']} (max {l7['max_points']})")
    
        # Layer 8: Player Venue Specialists (7 points)
    print("[Layer 8] Player Venue Specialists...")
    l8 = layer8_player_venue_specialists.calculate(team_a, team_b, venue, team_a_players, team_b_players)
    results["layer8"] = l8
    total_a += l8["team_a_points"]
    total_b += l8["team_b_points"]
    print(f"  {team_a}: {l8['team_a_points']} | {team_b}: {l8['team_b_points']} (max {l8['max_points']})")
    
    # Layer 9: Pressure Index (5 points)
    print("[Layer 9] Pressure Index...")
    l9 = layer9_pressure_index.calculate(team_a, team_b, stage)
    results["layer9"] = l9
    total_a += l9["team_a_points"]
    total_b += l9["team_b_points"]
    print(f"  {team_a}: {l9['team_a_points']} | {team_b}: {l9['team_b_points']} (max {l9['max_points']})")
    
    # Layer 10: Fatigue & Travel (3 points)
    print("[Layer 10] Fatigue & Travel...")
    l10 = layer10_fatigue_travel.calculate(team_a, team_b, match_date)
    results["layer10"] = l10
    total_a += l10["team_a_points"]
    total_b += l10["team_b_points"]
    print(f"  {team_a}: {l10['team_a_points']} | {team_b}: {l10['team_b_points']} (max {l10['max_points']})")
    
    # Calculate confidence
    gap = abs(total_a - total_b)
    medium_threshold = CONFIDENCE_MEDIUM_CPL if (league or '').upper() == 'CPL' else CONFIDENCE_MEDIUM
    if gap >= CONFIDENCE_HIGH:
        confidence = "High"
    elif gap >= medium_threshold:
        confidence = "Medium"
    else:
        confidence = "Low"
    
    # Determine winner
    if total_a > total_b:
        winner = team_a
    elif total_b > total_a:
        winner = team_b
    else:
        winner = "Tie"

    # Gate: Low-confidence matchups are too close to call -> "No Bet"
    no_bet = False
    if GATE_LOW_CONFIDENCE and confidence == "Low":
        no_bet = True
        winner = NO_BET_LABEL

    # Convert to percentage
    max_possible = 9 + 14 + 13 + 16 + 6 + 8 + 8 + 14 + 4 + 3 # Update as layers are added
    team_a_pct = round((total_a / max_possible) * 100, 1)
    team_b_pct = round((total_b / max_possible) * 100, 1)

    result = {
        "team_a": team_a,
        "team_b": team_b,
        "venue": venue,
        "team_a_score": team_a_pct,
        "team_b_score": team_b_pct,
        "predicted_winner": winner,
        "confidence": confidence,
        "no_bet": no_bet,
        "point_gap": round(gap, 1),
        "layer_breakdown": results,
        "key_factors": generate_key_factors(results, team_a, team_b, no_bet)
    }
    
    print(f"\n{'='*50}")
    print(f"RESULT: {team_a} {team_a_pct}% vs {team_b} {team_b_pct}%")
    print(f"Winner: {winner} | Confidence: {confidence} | No Bet: {no_bet}")
    print(f"{'='*50}\n")
    
    return result

def generate_key_factors(results, team_a, team_b, no_bet=False):
    """Generate human-readable key factors from layer results"""
    factors = []
    
    if no_bet:
        factors.append("No Bet: match is too close to call with confidence")
    
    if "layer1" in results:
        l1 = results["layer1"]
        if l1["advantage"] != "neutral":
            advantage_team = team_a if l1["advantage"] == "team_a" else team_b
            pct = l1["details"][f"{l1['advantage']}_win_pct"]
            factors.append(f"Venue advantage: {advantage_team} has {pct}% win rate at this ground")
    
    if "layer2" in results:
        l2 = results["layer2"]
        if l2["advantage"] != "neutral":
            advantage_team = team_a if l2["advantage"] == "team_a" else team_b
            factors.append(f"Form advantage: {advantage_team} players are in better recent touch")
    
    if "layer3" in results:
        l3 = results["layer3"]
        if l3["advantage"] != "neutral":
            advantage_team = team_a if l3["advantage"] == "team_a" else team_b
            factors.append(f"Clutch factor: {advantage_team} players win more matches when they perform")
    
    if "layer4" in results:
        l4 = results["layer4"]
        if l4["advantage"] != "neutral":
            advantage_team = team_a if l4["advantage"] == "team_a" else team_b
            factors.append(f"Matchup advantage: {advantage_team} batters match up better against opposition bowlers")
        
        if l4.get("key_matchups"):
            factors.append("--- Key Player Matchups ---")
            for matchup in l4["key_matchups"][:5]:
                factors.append(matchup)
    if "layer5" in results:
        l5 = results["layer5"]
        details = l5["details"]
        if details.get("matches_played", 0) > 0:
            factors.append(
                f"Recent H2H: {team_a} {details['team_a_wins']}-{details['team_b_wins']} {team_b} "
                f"({details['matches_played']} meetings, last 3 seasons)"
            )
    if "layer6" in results:
        l6 = results["layer6"]
        details = l6["details"]
        if details.get("pitch_edge"):
            pt = details["pitch_edge"]
            ratio_a = details.get("team_a_pitch_ratio")
            ratio_b = details.get("team_b_pitch_ratio")
            if ratio_a is not None and ratio_b is not None:
                stronger = team_a if ratio_a >= ratio_b else team_b
                factors.append(
                    f"Pitch ({pt}-friendly): {stronger} lineup better suited "
                    f"({ratio_a*100:.0f}% vs {ratio_b*100:.0f}% strength)"
                )
        elif details.get("venue_bias") and details["venue_bias"] != "neutral":
            bias = "batting first" if details["venue_bias"] == "bat_first" else "chasing"
            key = "bat_first_win_pct" if details["venue_bias"] == "bat_first" else "chase_win_pct"
            pct = details.get(key, "?")
            factors.append(f"Venue bias: {bias} wins {pct}% here")
        if details.get("toss_known"):
            factors.append(f"Toss factor included in prediction")
            
    if "layer7" in results:
        l7 = results["layer7"]
        if l7["advantage"] != "neutral":
            advantage_team = team_a if l7["advantage"] == "team_a" else team_b
            factors.append(f"Team balance advantage: {advantage_team} has a more balanced XI")
            
    if "layer8" in results:
        l8 = results["layer8"]
        if l8["advantage"] != "neutral":
            advantage_team = team_a if l8["advantage"] == "team_a" else team_b
            factors.append(f"Venue specialists: {advantage_team} has more players who perform at this ground")
    
    if "layer9" in results:
        l9 = results["layer9"]
        if l9["details"]["stage"] != "League":
            factors.append(f"Pressure match: {l9['details']['stage']} stage")
    
    if "layer10" in results:
        l10 = results["layer10"]
        if l10["advantage"] != "neutral":
            advantage_team = team_a if l10["advantage"] == "team_a" else team_b
            factors.append(f"Fatigue edge: {advantage_team} is better rested")
    

    return factors