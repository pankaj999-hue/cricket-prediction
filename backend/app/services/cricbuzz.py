# backend/app/services/cricbuzz.py
"""Unofficial Cricbuzz client.

Cricbuzz's old JSON endpoints are gone; match/series data is embedded as
escaped JSON inside Next.js flight payloads on the pages themselves. This
module fetches those pages and recovers the JSON via the same `self.__next_f`
decode + a string-aware brace scanner. No API key required.
"""
import json
import re
import threading
import time
import urllib.request

CPL_SERIES_ID = 12123
CPL_SCHEDULE_URL = f"https://www.cricbuzz.com/cricket-series/{CPL_SERIES_ID}/caribbean-premier-league-2026/matches"
MATCH_PAGE_URL = "https://www.cricbuzz.com/live-cricket-scores/{match_id}"
LIVE_SCORES_URL = "https://www.cricbuzz.com/cricket-match/live-scores"
SQUADS_URL = "https://www.cricbuzz.com/cricket-match-squads/{match_id}"

# How long a scraped lineup is trusted before re-fetching. Lineups can change
# up to toss time, so keep this short (same class as the predict cache).
XI_CACHE_SECONDS = 600

_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def _fetch(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


# ---------------------------------------------------------------------------
# Flight-payload extraction (same primitives the probe scripts validated)
# ---------------------------------------------------------------------------
_PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,"((?:\\.|[^"\\])*)"\]\)')


def decode_next_payload(html: str) -> str:
    """Concatenate Next.js flight-data string chunks into one decoded string."""
    chunks = []
    for m in _PUSH_RE.finditer(html):
        try:
            chunks.append(json.loads('"' + m.group(1) + '"'))
        except Exception:
            pass
    return "".join(chunks)


def balanced_json(text: str, start: int) -> int:
    """Return end index (exclusive) of balanced object starting at `start`
    (index of '{'). Braces inside quoted strings are skipped."""
    i, n, depth, in_str = start, len(text), 0, False
    while i < n:
        ch = text[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    return -1


def _first_object(flight: str, regex: re.Pattern):
    """Parse the first JSON object whose opening '{' is part of the first
    regex hit (so the '{' can precede the matched tail, e.g. '"matchId":')."""
    m = regex.search(flight)
    if not m:
        return None
    start = m.start() + m.group(0).rfind("{")
    end = balanced_json(flight, start)
    if end < 0:
        return None
    try:
        return json.loads(flight[start:end])
    except Exception:
        return None


MATCH_INFO_RE = re.compile(r'"matchInfo":\{"matchId":\d+')
TOSS_RE = re.compile(r'"tossResults":\{')
RESULT_RE = re.compile(r'"result":\{')


# ---------------------------------------------------------------------------
# Public accessors
# ---------------------------------------------------------------------------
def get_match_info(match_id: int) -> dict:
    """Fetch a match page and return its embedded matchInfo block."""
    html = _fetch(MATCH_PAGE_URL.format(match_id=match_id))
    flight = decode_next_payload(html)
    return _first_object(flight, re.compile(r'"matchInfo":\{"matchId":%d' % int(match_id))) or {}


def get_toss(match_id: int) -> dict:
    """Fetch a match page and return its tossResults block ({} if none yet)."""
    html = _fetch(MATCH_PAGE_URL.format(match_id=match_id))
    flight = decode_next_payload(html)
    return _first_object(flight, TOSS_RE) or {}


def get_result(match_id: int) -> dict:
    """Fetch a match page and return its result block ({} if not finished).
    Contains e.g. {"resultType":"win","winningTeam":"Trinbago Knight Riders",
    "winningMargin":19,"winByRuns":true}."""
    html = _fetch(MATCH_PAGE_URL.format(match_id=match_id))
    flight = decode_next_payload(html)
    return _first_object(flight, RESULT_RE) or {}


def get_series_matches(series_id: int = CPL_SERIES_ID) -> list[dict]:
    """Fetch the series matches page and return every CPL matchInfo block
    (the page embeds the whole schedule incl. playoffs)."""
    html = _fetch(CPL_SCHEDULE_URL)
    flight = decode_next_payload(html)
    out = []
    seen = set()
    for m in re.finditer(r'"matchInfo":\{"matchId":(\d+),"seriesId":%d,' % series_id, flight):
        mid = int(m.group(1))
        start = m.start() + m.group(0).rfind("{")
        end = balanced_json(flight, start)
        if end < 0:
            continue
        try:
            obj = json.loads(flight[start:end])
        except Exception:
            continue
        if mid in seen:
            continue
        seen.add(mid)
        out.append(obj)
    return out


def upcoming_matches(series_id: int = CPL_SERIES_ID) -> list[dict]:
    """Upcoming/live CPL matches ordered by start time (earliest first)."""
    items = []
    for m in get_series_matches(series_id):
        state = (m.get("state") or "").lower()
        if state in ("complete", "abandoned"):
            continue
        try:
            start = float(m.get("startDate"))
        except (TypeError, ValueError):
            continue
        items.append((start, m))
    items.sort(key=lambda x: x[0])
    return [m for _, m in items]


# ---------------------------------------------------------------------------
# Live lineup auto-fetch: recover the ACTUAL playing XI for a match so the
# engine doesn't rely on the static squad table (which is roster, not XI).
# ---------------------------------------------------------------------------
CURRENT_MATCHES_RE = re.compile(r'"currentMatchesList":\{')

# Cricbuzz team name -> canonical name the app stores for that team. Matching
# is order-insensitive and name-dirt resistant; this table covers renames
# (Barbados Royals -> Tridents, Saint Lucia -> St Lucia, & -> and, ...).
TEAM_NAME_ALIASES = {
    "Saint Lucia Kings": "St Lucia Kings",
    "St Kitts and Nevis Patriots": "St Kitts & Nevis Patriots",
    "Barbados Royals": "Barbados Tridents",
}

# In-memory cache {league, team_a, team_b -> ([xi_a], [xi_b]) | None}.
# Guards both the prediction flow and repeated frontend hits against hammering
# Cricbuzz on every request.
_xi_cache = {}
_xi_cache_lock = threading.Lock()


def _norm_team(name: str) -> str:
    if not name:
        return ""
    name = TEAM_NAME_ALIASES.get(name, name)
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _xi_cache_get(key):
    with _xi_cache_lock:
        item = _xi_cache.get(key)
        if not item:
            return None
        expires_at, value = item
        if time.time() > expires_at:
            _xi_cache.pop(key, None)
            return None
        return value


def _xi_cache_put(key, value):
    with _xi_cache_lock:
        _xi_cache[key] = (time.time() + XI_CACHE_SECONDS, value)


def get_live_matches() -> list[dict]:
    """The 'current' slate (today's completed/live/upcoming fixtures) for every
    league, parsed from the live-scores page's embedded JSON. Each entry has
    matchId, seriesId/Name, state, startDate and full team names."""
    html = _fetch(LIVE_SCORES_URL)
    flight = decode_next_payload(html)
    m = CURRENT_MATCHES_RE.search(flight)
    if not m:
        return []
    start = m.start() + m.group(0).rfind("{")
    if start < 0:
        return []
    end = balanced_json(flight, start)
    if end < 0:
        return []
    try:
        data = json.loads(flight[start:end])
    except Exception:
        return []
    out = []
    for tm in data.get("typeMatches", []):
        for sm in tm.get("seriesMatches", []):
            sw = sm.get("seriesAdWrapper") or {}
            for match in sw.get("matches", []):
                mi = match.get("matchInfo") or {}
                t1 = mi.get("team1") or {}
                t2 = mi.get("team2") or {}
                out.append({
                    "seriesId": sw.get("seriesId"),
                    "seriesName": sw.get("seriesName"),
                    "matchId": mi.get("matchId"),
                    "state": mi.get("state"),
                    "startDate": mi.get("startDate"),
                    "team1": t1.get("teamName"),
                    "team2": t2.get("teamName"),
                })
    return out


def get_match_squads(match_id) -> list[dict]:
    """Playing XI (and role) per team for a match, from the Squads tab page."""
    html = _fetch(SQUADS_URL.format(match_id=int(match_id)))
    flight = decode_next_payload(html)
    out = []
    for team_field in (r'"team1":\{"team":', r'"team2":\{"team":'):
        obj = _first_object(flight, re.compile(team_field))
        if not obj:
            continue
        team = ((obj.get("team")) or {}).get("teamName")
        players = ((obj.get("players")) or {}).get("playing XI") or []
        out.append({
            "team": team,
            "players": [
                {"name": p.get("name"), "role": p.get("role")}
                for p in players
                if p.get("name")
            ],
        })
    return out


def fetch_today_xi(league, team_a, team_b):
    """Actual playing XI for today's match between team_a and team_b.

    Returns (xi_a_names, xi_b_names) when Cricbuzz has both lineups (>= 8
    names each), otherwise None so callers can fall back to the expected-XI
    logic. The match is located from today's live-scores slate and matched by
    team name (order-insensitive, rename-resilient)."""
    key = (str(league).upper(), team_a, team_b)
    cached = _xi_cache_get(key)
    if cached is not None:
        return cached

    n_a, n_b = _norm_team(team_a), _norm_team(team_b)

    def same_pair(m):
        t1, t2 = _norm_team(m.get("team1")), _norm_team(m.get("team2"))
        return {t1, t2} == {n_a, n_b} if (t1 and t2) else False

    try:
        matches = [m for m in (get_live_matches() or []) if same_pair(m)]
    except Exception:
        _xi_cache_put(key, None)
        return None

    if not matches:
        _xi_cache_put(key, None)
        return None

    def priority(m):
        state = (m.get("state") or "").lower()
        done = 1 if state in ("complete", "abandoned") else 0
        try:
            start = float(m.get("startDate") or 0)
        except (TypeError, ValueError):
            start = 0
        return (done, -start)  # live/preview first, then latest start

    matches.sort(key=priority)
    chosen = matches[0]

    try:
        squads = get_match_squads(chosen["matchId"]) or []
    except Exception:
        _xi_cache_put(key, None)
        return None

    xi_by_team = {}
    for s in squads:
        xi_by_team[_norm_team(s.get("team"))] = [p["name"] for p in s.get("players", [])]

    xi_a, xi_b = xi_by_team.get(n_a, []), xi_by_team.get(n_b, [])
    result = (xi_a, xi_b) if len(xi_a) >= 8 and len(xi_b) >= 8 else None
    _xi_cache_put(key, result)
    return result