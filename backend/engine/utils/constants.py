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

# CPL gate is stricter than IPL: CPL medium calls near 8-10 gaps landed near
# coin-flip (40%) in backtests. Sweep of 2024-25 CPL found threshold 12 gives
# 85.7% call accuracy while keeping decline at 47% (vs 54.5% at 15, 73.3% at 8).
# IPL keeps Medium as a valid call (validated ~85% across 2024-25/2026).
CONFIDENCE_MEDIUM_CPL = 12  # CPL requires a High-grade gap to make a call

# Gating — only emit a team call when confidence is High or Medium.
# Low-confidence games are "No Bet": not betting is still profit.
GATE_LOW_CONFIDENCE = True
NO_BET_LABEL = "No Bet"

# Form thresholds
FORM_MATCHES_COUNT = 5  # Look at last 5 matches
MIN_MATCHES_VENUE = 3   # Minimum matches at venue for reliable stats