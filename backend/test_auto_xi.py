# backend/test_auto_xi.py
"""End-to-end check for the live-XI feature: goes through PredictRequest ->
run_prediction (Cricbuzz fetch + engine + cache). Requires a loaded Postgres.
Run from repo root: SECRET_KEY=xxx .venv\\Scripts\\python.exe backend\\test_auto_xi.py"""

import os
import sys

sys.path.insert(0, "backend")
os.environ.setdefault("SECRET_KEY", "dev-test-secret")

from app.core.schemas import PredictRequest
from app.services.predictions import run_prediction

if __name__ == "__main__":
    req = PredictRequest(
        team_a="St Lucia Kings",
        team_b="Antigua and Barbuda Falcons",
        venue="Sir Vivian Richards Stadium, North Sound",
        league="CPL",
        stage="League",
        pitch_type="neutral",
        auto_xi=True,
    )
    result = run_prediction(req)
    print("xi_note :", result.get("xi_note"))
    print("xi_a    :", req.team_a_xi)
    print("xi_b    :", req.team_b_xi)
    print("winner  :", result.get("predicted_winner"), result.get("confidence"))
    print("scores  :", result.get("team_a_score"), "-", result.get("team_b_score"))