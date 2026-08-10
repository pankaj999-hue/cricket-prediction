# backend/test_cricbuzz_xi.py
"""Verify the live-XI auto-fetch: locate today's CPL match on Cricbuzz and pull
the actual playing XI for both teams (no DB/network-free unit test — hits the
live site). Usage: python test_cricbuzz_xi.py"""
import sys
sys.path.append('.')
sys.path.append('app')

from app.services.cricbuzz import fetch_today_xi, get_live_matches, get_match_squads

if __name__ == '__main__':
    live = get_live_matches()
    cpl = [m for m in live if 'cpl' in (m['seriesName'] or '').lower() or 'caribbean' in (m['seriesName'] or '').lower()]
    print(f"live-scores slate: {len(live)} matches, CPL: {len(cpl)}")
    for m in cpl:
        print(f"  match {m['matchId']} ({m['state']}) {m['team1']} vs {m['team2']}")

    squads = get_match_squads(cpl[0]['matchId']) if cpl else []
    for s in squads:
        print(f"\n{s['team']} XI ({len(s['players'])})")
        for p in s['players']:
            print(f"  {p['name']} ({p['role']})")

    print("\n--- fetch_today_xi('CPL', 'St Lucia Kings', 'Antigua and Barbuda Falcons') ---")
    xi = fetch_today_xi('CPL', 'St Lucia Kings', 'Antigua and Barbuda Falcons')
    if xi:
        print("Team A:", xi[0])
        print("Team B:", xi[1])
    else:
        print("No lineup (expected when match not live / not announced yet)")