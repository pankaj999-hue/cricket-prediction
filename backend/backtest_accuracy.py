"""Measure prediction-call accuracy against the live DB.

Replays scored toss_alerts through predict_match (with the stored toss /
decision / XIs) and reports, per match, whether the call was right, and — for
wrong calls — which layers favored the losing side and by how much.

Unscored alerts whose result IS KNOWN but not yet auto-scored (e.g. matches
finished in the last poll window) can be supplied via KNOWN_RESULTS below so
they participate in the run and get layer blame today.

Run from repo root with the venv active:
    python backend/backtest_accuracy.py [--no-bets-as-wrong]
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.predictor import predict_match
from app.config import DATABASE_URL
import psycopg2

NO_BETS_AS_WRONG = "--no-bets-as-wrong" in sys.argv

# cricbuzz_match_id -> actual winner for alerts that have finished but whose
# result hasn't been auto-scored yet. Update as matches finish.
KNOWN_RESULTS = {
    "154359": "St Kitts and Nevis Patriots",  # SLK vs SKN Patriots, Aug 12
}


def _connect():
    return psycopg2.connect(DATABASE_URL)


def _fetch_alerts(conn):
    cur = conn.cursor()
    cur.execute(
        """SELECT cricbuzz_match_id, match_name, team_a, team_b, venue,
                  toss_winner, toss_decision, predicted_winner,
                  team_a_score, team_b_score, confidence,
                  result_winner
           FROM toss_alerts
           WHERE result_winner IS NOT NULL
           ORDER BY created_at ASC"""
    )
    scored = cur.fetchall()

    cur.execute(
        """SELECT cricbuzz_match_id, match_name, team_a, team_b, venue,
                  toss_winner, toss_decision, predicted_winner,
                  team_a_score, team_b_score, confidence,
                  result_winner
           FROM toss_alerts
           WHERE result_winner IS NULL
           ORDER BY created_at ASC"""
    )
    unscored = cur.fetchall()
    cur.close()

    rows = list(scored)
    for r in unscored:
        mid = r[0]
        actual = KNOWN_RESULTS.get(mid)
        if not actual:
            continue
        rows.append((mid, r[1], r[2], r[3], r[4], r[5], r[6], r[7],
                     r[8], r[9], r[10], actual))
    return rows


def _layer_blame(team_a, team_b, layer_breakdown):
    """For each layer, report which side it favored and by how many points."""
    out = []
    for key, lb in layer_breakdown.items():
        a = lb.get("team_a_points", 0)
        b = lb.get("team_b_points", 0)
        margin = abs(a - b)
        if margin < 0.01:
            continue
        favored = team_a if a > b else team_b
        out.append((key, favored, round(margin, 2)))
    out.sort(key=lambda x: -x[2])
    return out


def main():
    conn = _connect()
    alerts = _fetch_alerts(conn)

    print(f"Relevant alerts: {len(alerts)}\n")
    if not alerts:
        conn.close()
        return

    total_calls = 0
    correct = 0
    wrong = 0
    declines = 0

    for (mid, name, team_a, team_b, venue, toss_winner, toss_decision,
         pred_winner, a_score, b_score, confidence, actual) in alerts:

        predicted = pred_winner
        scored = actual is not None

        print("=" * 70)
        print(f"{name} ({mid}) | {venue}")
        print(f"  stored call : {predicted} | {a_score}-{b_score} | {confidence}")
        print(f"  actual      : {actual if scored else 'UNKNOWN (skipped)'}")

        no_bet = bool(predicted and predicted == "No Bet")

        if no_bet:
            declines += 1
            if NO_BETS_AS_WRONG:
                wrong += 1
                reason = "WRONG (No Bet counted as wrong)"
            else:
                reason = "DECLINE (No Bet skipped)"
            print(f"  => {reason}")
        elif not scored:
            print("  => UNSCOPED (result not known yet)")
        else:
            total_calls += 1
            ok = predicted.strip().lower() == actual.strip().lower() if actual else False
            if ok:
                correct += 1
                print("  => CORRECT")
            else:
                wrong += 1
                print("  => WRONG")

                try:
                    res = None
                    last_err = None
                    # Pooled conns go stale on Neon; retry mirrors toss_watcher.
                    for attempt in range(3):
                        try:
                            res = predict_match(
                                team_a=team_a, team_b=team_b, venue=venue,
                                stage="League", league="CPL",
                                toss_winner=toss_winner, toss_decision=toss_decision,
                                match_date=None,
                            )
                            break
                        except psycopg2.OperationalError as e:
                            last_err = e
                            print(f"    (engine retry {attempt + 1} after DB error)")
                            time.sleep(2)
                    if res is None:
                        raise last_err
                except Exception as e:
                    print(f"    (engine replay failed: {e})")
                    continue

                lb = res.get("layer_breakdown", {})
                print(f"    repro     : {res['predicted_winner']} | "
                      f"{res['team_a_score']}-{res['team_b_score']} | {res['confidence']}")
                blame = _layer_blame(team_a, team_b, lb)
                if blame:
                    print("    layer blame (largest gaps first):")
                    for key, favored, margin in blame:
                        tag = "  <- favored loser" if favored == actual else ""
                        print(f"      {key}: favored {favored} by {margin} pts{tag}")

    conn.close()

    print("\n" + "=" * 70)
    print("SUMMARY")
    print(f"  Declines (No Bet):      {declines}")
    print(f"  Calls made:             {total_calls}")
    print(f"  Correct:                {correct}")
    print(f"  Wrong:                  {wrong}")
    if total_calls:
        print(f"  Call accuracy:          {correct/total_calls*100:.1f}%")
    else:
        print("  Call accuracy:          n/a (no calls yet)")
    if total_calls + declines:
        print(f"  Decline rate:           {declines/(total_calls+declines)*100:.1f}%")


if __name__ == "__main__":
    main()