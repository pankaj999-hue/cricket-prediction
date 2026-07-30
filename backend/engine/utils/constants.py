# Layer weights (total = 100 points)
LAYER_WEIGHTS = {
    "layer1_venue_compatibility": 15,
    "layer2_recent_form": 12,
    "layer3_win_contribution": 12,
    "layer4_h2h_record": 10,
    "layer5_archetype_matchup": 10,
    "layer6_toss_conditions": 8,
    "layer7_team_balance": 8,
    "layer8_player_venue_specialists": 7,
    "layer9_pressure_index": 5,
    "layer10_fatigue_travel": 3,
}

# Confidence thresholds
CONFIDENCE_HIGH = 15   # Gap of 15+ points between teams
CONFIDENCE_MEDIUM = 8  # Gap of 8-14 points
# Below 8 = Low confidence (close to 50-50)

# Form thresholds
FORM_MATCHES_COUNT = 5  # Look at last 5 matches
MIN_MATCHES_VENUE = 3   # Minimum matches at venue for reliable stats