import sys
import os

# Add backend folder to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now import directly
from engine.predictor import predict_match

import psycopg2.extras

# Test prediction
result = predict_match(
    team_a="Royal Challengers Bengaluru",
    team_b="Mumbai Indians",
    venue="Wankhede Stadium, mumbai",
    stage="League"
)

print("\nFull Result:")
print(f"Winner: {result['predicted_winner']}")
print(f"Score: {result['team_a_score']}% - {result['team_b_score']}%")
print(f"Confidence: {result['confidence']}")
print(f"\nKey Factors:")
for factor in result['key_factors']:
    print(f"  • {factor}")