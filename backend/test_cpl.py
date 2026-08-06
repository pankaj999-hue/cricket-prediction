import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.predictor import predict_match

result = predict_match(
    team_a="Jamaica Kingsmen",
    team_b="Antigua and Barbuda Falcons",
    venue="Arnos Vale Stadium, Kingstown",
    stage="League",
    match_date="2026-08-08",
    league='CPL',
    toss_winner="Antigua and Barbuda Falcons",
    toss_decision="field"
)
print(f"\nWinner: {result['predicted_winner']}")
print(f"Score: {result['team_a_score']}% - {result['team_b_score']}%")
print(f"Confidence: {result['confidence']}")
for f in result['key_factors']:
    print(f"  • {f}")