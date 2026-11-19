"""ESPN's public soccer feed: requests and parsing (no site data is written here).

The feed (site.api.espn.com) is unofficial and undocumented. Scoreboards are
fetched one day at a time (date ranges return HTTP 400). Goal events come
from the scoreboard (competitions[0].details) or, when that is empty, from
the match summary (keyEvents). Own goals and penalty shoot-out kicks never
count; penalties do. 45+x goes to cell 45 and 90+x to cell 90.
"""

import hashlib
import json
import re
import time
from datetime import date, timedelta

import requests

if __package__:
    from .probe_espn import ROOT, describe, goal_details, match_goals
else:
    from probe_espn import ROOT, describe, goal_details, match_goals

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
CORE = "https://sports.core.api.espn.com/v2/sports/soccer"
CACHE = ROOT / "data" / "espn_cache"
HEADERS = {"User-Agent": "minutegrid/1.0", "Accept": "application/json"}
RETRY_WAITS = (0, 2, 5, 10)
PAUSE = 0.2  # between network requests; ESPN publishes no rate limits

stats = {"requests": 0, "cached": 0, "failed": 0}


def get_json(url, cache=True):
    """(status, body). Only successful responses are cached, and only when
    cache=True (recent days are always fetched fresh). status None = no connection."""
    path = CACHE / (hashlib.sha256(url.encode("utf-8")).hexdigest() + ".json")
    if cache and path.exists():
        stats["cached"] += 1
        stored = json.loads(path.read_text(encoding="utf-8"))
        return stored["status"], stored["body"]
    response = None
    for attempt, wait in enumerate(RETRY_WAITS, start=1):
        time.sleep(wait or PAUSE)
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
        except requests.RequestException as error:
            if attempt == len(RETRY_WAITS):
                stats["failed"] += 1
                return None, {"error": f"{type(error).__name__} after {attempt} attempts"}
            continue
        if response.status_code in (429, 500, 502, 503, 504) and attempt < len(RETRY_WAITS):
            continue
        break
    stats["requests"] += 1
    try:
        body = response.json()
    except ValueError:
        body = {"error": "not JSON"}
    if response.status_code == 200 and cache:
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"status": 200, "body": body}), encoding="utf-8")
    if response.status_code != 200:
        stats["failed"] += 1
    return response.status_code, body


def scoreboard(code, day, cache=True):
    """day: YYYYMMDD."""
    return get_json(f"{BASE}/{code}/scoreboard?dates={day}&limit=200", cache=cache)


def iso(day):
    """ "20170107" -> "2017-01-07"."""
    return f"{day[:4]}-{day[4:6]}-{day[6:8]}"


def compact(iso_day):
    return iso_day.replace("-", "")


def days_between(first, last):
    """ISO dates, inclusive -> list of YYYYMMDD."""
    start, end = date.fromisoformat(first), date.fromisoformat(last)
    return [(start + timedelta(days=n)).strftime("%Y%m%d") for n in range((end - start).days + 1)]


MONTHS = {m: n for n, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}
DETAIL_RANGE = re.compile(r"^\s*([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2})(?:\s*-\s*(?:([A-Za-z]{3})[a-z]*\.?\s+)?(\d{1,2}))?\s*$")
MARGIN = 1  # days either side of a round's match days (ESPN's dates are US time)


def _day(value):
    return date.fromisoformat(value[:10]) if isinstance(value, str) and len(value) >= 10 and value[4] == "-" else None


def round_days(entry):
    """Days to read for one calendar round. Cup and UEFA calendars give each
    round as a range (startDate..endDate, often months long) plus a 'detail'
    such as "Dec 16-19" or "Jan 3-Feb 7" naming the actual match days; the
    detail is used when it reads cleanly and lies inside the range, else the
    whole range. Returns a list of dates."""
    start, end = _day(entry.get("startDate")), _day(entry.get("endDate"))
    if not start:
        return []
    end = max(end or start, start)
    match = DETAIL_RANGE.match(str(entry.get("detail") or ""))
    if match and match.group(1).lower() in MONTHS and (not match.group(3) or match.group(3).lower() in MONTHS):
        month1, day1 = MONTHS[match.group(1).lower()], int(match.group(2))
        month2 = MONTHS[match.group(3).lower()] if match.group(3) else month1
        day2 = int(match.group(4)) if match.group(4) else day1
        for year in range(start.year - 1, end.year + 1):
            try:
                first = date(year, month1, day1)
                last = date(year + (month2 < month1), month2, day2)
            except ValueError:
                break
            if last >= first and start - timedelta(days=7) <= first and last <= end + timedelta(days=7):
                first, last = first - timedelta(days=MARGIN), last + timedelta(days=MARGIN)
                return [first + timedelta(days=n) for n in range((last - first).days + 1)]
    return [start + timedelta(days=n) for n in range((end - start).days + 1)]


def calendar_days(body):
    """Match days ESPN lists for the season of a scoreboard response, as YYYYMMDD.
    League calendars are plain dates; cup and UEFA calendars are rounds."""
    days = set()
    for league in (body or {}).get("leagues") or []:
        for entry in league.get("calendar") or []:
            if isinstance(entry, str):
                if _day(entry):
                    days.add(compact(entry[:10]))
                continue
            if not isinstance(entry, dict):
                continue
            rounds = [e for e in entry.get("entries") or [] if isinstance(e, dict)]
            if rounds:
                for item in rounds:
                    days.update(d.strftime("%Y%m%d") for d in round_days(item))
            elif _day(entry.get("value")):
                days.add(compact(entry["value"][:10]))
            elif _day(entry.get("startDate")):
                days.update(d.strftime("%Y%m%d") for d in round_days(entry))
    return sorted(days)


def _competitors(event):
    competitors = (event.get("competitions") or [{}])[0].get("competitors") or []
    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0] if competitors else {})
    away = next((c for c in competitors if c.get("homeAway") == "away"),
                competitors[1] if len(competitors) > 1 else {})
    return home, away


def _score(competitor):
    try:
        return int(competitor.get("score"))
    except (TypeError, ValueError):
        return None


def parse_match(competition_id, event):
    home, away = _competitors(event)
    status = ((event.get("status") or {}).get("type") or {})
    return {
        "competition_id": competition_id,
        "match_id": str(event.get("id")),
        "date": (event.get("date") or "")[:10],
        "home_team_id": str((home.get("team") or {}).get("id") or ""),
        "home": (home.get("team") or {}).get("displayName") or "",
        "away_team_id": str((away.get("team") or {}).get("id") or ""),
        "away": (away.get("team") or {}).get("displayName") or "",
        "home_score": _score(home),
        "away_score": _score(away),
        "completed": bool(status.get("completed")),
    }


def is_shootout(detail):
    period = detail.get("period") or {}
    return bool(detail.get("shootout")) or (isinstance(period, dict) and period.get("number") == 5)


def _total_minute(goal):
    return (goal["minute"] or 0) + (goal["minute_added"] or 0)


def drop_duplicates(described, match):
    """Some older ESPN matches list every goal twice (two feeds merged; the
    copy may be a minute apart). Only when the goal events outnumber the
    scoreline, a second event by the same player for the same team within a
    minute of the first is dropped."""
    home, away = match.get("home_score"), match.get("away_score")
    if home is None or away is None or len(described) <= home + away:
        return described
    kept = []
    for goal in described:
        if any(k["team_id"] == goal["team_id"] and k["athlete_id"] == goal["athlete_id"]
               and k["own_goal"] == goal["own_goal"] and abs(_total_minute(k) - _total_minute(goal)) <= 1
               for k in kept):
            continue
        kept.append(goal)
    return kept


def parse_goals(code, match, event, details):
    """Counted goals of one match, plus the number of goal events ESPN gave
    (own goals included, shoot-out kicks and duplicates not), to measure
    detail coverage."""
    described = []
    for detail in details:
        if is_shootout(detail):
            continue
        goal = describe(code, match["competition_id"], match["date"], event, detail)
        if not goal["shootout"]:
            described.append(goal)
    described = drop_duplicates(described, match)
    goals = []
    for goal in described:
        if goal["own_goal"] or goal["cell"] is None or not goal["athlete_id"]:
            continue
        team_id = str(goal["team_id"] or "")
        if team_id == match["home_team_id"]:
            team, opponent = match["home"], match["away"]
        elif team_id == match["away_team_id"]:
            team, opponent = match["away"], match["home"]
        else:
            team, opponent = goal["team"] or "", ""
        goals.append({
            "competition_id": match["competition_id"], "match_id": match["match_id"], "date": match["date"],
            "team_id": team_id, "team": team, "opponent": opponent,
            "athlete_id": str(goal["athlete_id"]), "athlete": goal["athlete"] or "",
            "minute": goal["minute"], "minute_added": goal["minute_added"] or 0,
            "cell": goal["cell"], "extra": bool(goal["extra_time"]),
            "added_time": bool(goal["minute_added"]) and goal["minute"] in (45, 90),
            "penalty": bool(goal["penalty"]),
        })
    return goals, len(described)


def summary_details(code, match_id, cache=True):
    status, body = get_json(f"{BASE}/{code}/summary?event={match_id}", cache=cache)
    if status != 200:
        return None
    events = body.get("keyEvents") or []
    return [e for e in events if e.get("scoringPlay") or "goal" in str((e.get("type") or {}).get("text", "")).lower()]


def read_day(code, competition_id, day, cache, summary_budget):
    """Completed matches and goals for one day. Returns (matches, goals, ok)."""
    status, body = scoreboard(code, day, cache=cache)
    if status != 200:
        return [], [], False
    matches, goals = [], []
    for event in body.get("events") or []:
        match = parse_match(competition_id, event)
        if not match["completed"]:
            continue
        details = goal_details(event)
        if not details and match_goals(event) > 0 and summary_budget[0] > 0:
            summary_budget[0] -= 1
            details = summary_details(code, match["match_id"], cache=cache) or []
        match_goal_rows, events = parse_goals(code, match, event, details)
        match["goal_events"] = events
        matches.append(match)
        goals.extend(match_goal_rows)
    return matches, goals, True


def league_teams(code):
    """[(team_id, name, logo)] of a league's current season, or None on failure."""
    status, body = get_json(f"{BASE}/{code}/teams", cache=False)
    if status != 200:
        return None
    teams = []
    for sport in body.get("sports") or []:
        for league in sport.get("leagues") or []:
            for item in league.get("teams") or []:
                team = item.get("team") or item
                logos = team.get("logos") or []
                teams.append((str(team.get("id")), team.get("displayName") or team.get("name") or "",
                              logos[0].get("href") if logos else None))
    return teams


def roster_athletes(body):
    """Athletes of a team roster response (flat or grouped by position)."""
    out = []
    for item in (body or {}).get("athletes") or []:
        group = item.get("items") if isinstance(item, dict) and "items" in item else [item]
        for athlete in group:
            if not isinstance(athlete, dict) or not athlete.get("id"):
                continue
            citizenship = athlete.get("citizenship")
            if isinstance(citizenship, dict):
                citizenship = citizenship.get("name") or citizenship.get("abbreviation")
            if not citizenship:
                country = athlete.get("citizenshipCountry") or {}
                citizenship = country.get("name") or country.get("abbreviation")
            out.append({
                "athlete_id": str(athlete["id"]),
                "name": athlete.get("displayName") or athlete.get("fullName") or "",
                "full_name": athlete.get("fullName") or "",
                "dob": (athlete.get("dateOfBirth") or "")[:10],
                "nationality": citizenship or "",
            })
    return out


def team_roster(code, team_id):
    status, body = get_json(f"{BASE}/{code}/teams/{team_id}/roster", cache=False)
    return roster_athletes(body) if status == 200 else None


def code_works(code):
    status, _body = get_json(f"{BASE}/{code}/scoreboard", cache=False)
    return status == 200
