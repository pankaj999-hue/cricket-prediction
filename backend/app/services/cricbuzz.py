# backend/app/services/cricbuzz.py
"""Unofficial Cricbuzz client.

Cricbuzz's old JSON endpoints are gone; match/series data is embedded as
escaped JSON inside Next.js flight payloads on the pages themselves. This
module fetches those pages and recovers the JSON via the same `self.__next_f`
decode + a string-aware brace scanner. No API key required.
"""
import json
import re
import urllib.request

CPL_SERIES_ID = 12123
CPL_SCHEDULE_URL = f"https://www.cricbuzz.com/cricket-series/{CPL_SERIES_ID}/caribbean-premier-league-2026/matches"
MATCH_PAGE_URL = "https://www.cricbuzz.com/live-cricket-scores/{match_id}"

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