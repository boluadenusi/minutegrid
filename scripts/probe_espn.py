#!/usr/bin/env python3
"""Probe ESPN's public soccer feed as a possible source for competitions
PitchAPI lacks (domestic cups, super cups, UEFA qualifiers, continental
tournaments). Read-only: it changes no site data.

ESPN's feed (site.api.espn.com) is undocumented and unofficial, with no
uptime promise or published rate limits. Read ESPN's terms before using it
for a public site. This probe is for evaluation only.

For each league code and date range it:
  1. loads the scoreboard and reports HTTP status, matches and finished matches;
  2. collects goal events from the scoreboard (competitions[0].details) or,
     if that is empty, from the match summary (keyEvents);
  3. prints each goal: league, date, match, team, scorer id and name, clock,
     parsed minute + added time, Minute Grid cell, penalty, own goal;
  4. prints the raw JSON of the first goal per league, to learn the schema;
  5. with --compare-tm, checks the minutes for days Transfermarkt also covers
     (on or before 2026-07-06) against goals_grid.parquet, per competition and day.

Responses are cached in data/espn_cache/ (ignored by git). Parsed goals are
written to data/espn_probe.json.

Usage:
  python scripts/probe_espn.py
  python scripts/probe_espn.py --league eng.fa:20261031-20261109 --league eng.1:20261108
  python scripts/probe_espn.py --compare-tm
  python scripts/probe_espn.py --list-leagues
  python scripts/probe_espn.py --round2 --compare-tm
"""

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "espn_cache"
OUT = DATA / "espn_probe.json"
BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS = {"User-Agent": "minutegrid-probe/0.1", "Accept": "application/json"}

# ESPN league code -> (Transfermarkt competition id, default date range YYYYMMDD[-YYYYMMDD]).
# The codes are best guesses; the probe reports which ones ESPN recognises.
DEFAULTS = {
    "eng.1": ("GB1", "20260524"),                        # Premier League final day 2025/26 (overlap with Transfermarkt)
    "esp.1": ("ES1", "20260524"),
    "eng.fa": ("FAC", "20261031-20261109"),              # FA Cup
    "esp.copa_del_rey": ("CDR", "20261027-20261106"),    # Copa del Rey
    "ger.dfb_pokal": ("DFB", "20261027-20261030"),       # DFB-Pokal
    "ita.coppa_italia": ("CIT", "20260808-20260820"),    # Coppa Italia
    "eng.charity": ("GBCS", "20260801-20260816"),        # Community Shield
    "uefa.super_cup": ("USC", "20260810-20260816"),      # UEFA Super Cup
    "uefa.champions_qual": ("CLQ", "20260707-20260826"), # Champions League qualifying
    "uefa.euro": ("EURO", "20240614-20240714"),          # Euro 2024 (overlap with Transfermarkt)
    "conmebol.america": ("COPA", "20240620-20240714"),   # Copa América 2024
    "caf.nations": ("AFCN", "20251221-20260118"),        # AFCON 2025
}

CORE = "https://sports.core.api.espn.com/v2/sports/soccer"

# Competitions still to place on ESPN: Transfermarkt id -> (name, ESPN country prefixes, name/slug keywords).
TARGETS = {
    "UKR1": ("Ukraine Premier Liga", ("ukr",), ("premier", "1")),
    "DKP": ("Danish Cup", ("den",), ("cup", "pokal")),
    "GRP": ("Greek Cup", ("gre",), ("cup",)),
    "NLP": ("KNVB Beker", ("ned",), ("cup", "beker")),
    "RUP": ("Russian Cup", ("rus",), ("cup",)),
    "SFA": ("Scottish Cup", ("sco",), ("cup", "tennents")),
    "UKRP": ("Ukrainian Cup", ("ukr",), ("cup",)),
    "BESC": ("Belgian Super Cup", ("bel",), ("super",)),
    "FRCH": ("Trophée des Champions", ("fra",), ("super", "trophee", "champions")),
    "DFL": ("German Super Cup", ("ger",), ("super",)),
    "SCI": ("Supercoppa Italiana", ("ita",), ("super",)),
    "NLSC": ("Johan Cruijff Schaal", ("ned",), ("super", "shield", "schaal")),
    "POSU": ("Portuguese Super Cup", ("por",), ("super",)),
    "RUSS": ("Russian Super Cup", ("rus",), ("super",)),
    "SUC": ("Supercopa de España", ("esp",), ("super",)),
    "ELQ": ("Europa League qualifying", ("uefa",), ("europa", "qual")),
    "ECLQ": ("Conference League qualifying", ("uefa",), ("conf", "qual")),
    "AFAC": ("AFC Asian Cup", ("afc",), ("asian",)),
}

SLUG = re.compile(r"/leagues/([^/?]+)")


def slug_from_ref(ref):
    """ "http://sports.core.api.espn.com/v2/sports/soccer/leagues/eng.fa?lang=en" -> "eng.fa"."""
    match = SLUG.search(ref or "")
    return match.group(1) if match else None


def suggest(code, leagues):
    """Candidate ESPN leagues for a TARGETS entry: same country prefix and every
    keyword group satisfied by the slug or name (any keyword per entry)."""
    _name, prefixes, keywords = TARGETS[code]
    found = []
    for slug, name in leagues.items():
        if slug.split(".")[0] not in prefixes:
            continue
        text = f"{slug} {name or ''}".lower()
        if code == "UKR1":
            hit = slug == "ukr.1"
        elif code in ("ELQ", "ECLQ"):
            hit = all(word in text for word in keywords)
            if code == "ELQ" and "conf" in text:  # Conference League codes can start with "europa"
                hit = False
        else:
            hit = any(word in text for word in keywords)
            if "cup" in keywords and "super" in text:  # a domestic cup is not its super cup
                hit = False
        if hit:
            found.append((slug, name))
    return sorted(found)


def discover(max_names):
    """List ESPN's soccer leagues from the core API and name the ones that matter here."""
    status, body = get_json(f"{CORE}/leagues?limit=1000")
    if status != 200:
        print(f"League list: HTTP {status} {str(body)[:160]}")
        return
    slugs = sorted({s for s in (slug_from_ref(item.get("$ref")) for item in body.get("items", [])) if s})
    print(f"ESPN lists {len(slugs)} soccer leagues (count reported: {body.get('count')}).")
    prefixes = {p for _n, ps, _k in TARGETS.values() for p in ps}
    wanted = [s for s in slugs if s.split(".")[0] in prefixes]
    names = {}
    for slug in wanted[:max_names]:
        league_status, league = get_json(f"{CORE}/leagues/{slug}")
        names[slug] = league.get("name") if league_status == 200 and isinstance(league, dict) else None
    if len(wanted) > max_names:
        print(f"Named {max_names} of {len(wanted)} relevant leagues (raise --max-names to name the rest).")
    print("\n--- leagues for the countries and bodies we still need ---")
    for prefix in sorted(prefixes):
        rows = [f"{s} ({names.get(s) or '?'})" for s in wanted if s.split(".")[0] == prefix]
        print(f"{prefix}: {', '.join(rows) if rows else '(none)'}")
    print("\n--- suggested codes for the untested competitions ---")
    for code, (name, _p, _k) in TARGETS.items():
        found = suggest(code, names)
        shown = "; ".join(f"{slug} = {league or '?'}" for slug, league in found) if found else "no match found"
        print(f"{code:5} {name}: {shown}")
    print("\nTry a suggestion with, for example: python scripts/probe_espn.py --league ned.cup:20261028-20261030")


# Second set, found with --list-leagues. Dates before 2026-07-06 overlap Transfermarkt (minute check).
ROUND2 = {
    "ned.cup": ("NLP", "20261027-20261030"),                 # KNVB Beker first round
    "sco.tennents": ("SFA", "20260801-20261115"),            # Scottish Cup early rounds
    "fra.super_cup": ("FRCH", "20260720-20260820"),          # Trophée des Champions
    "ger.super_cup": ("DFL", "20260808-20260818"),           # German Supercup
    "ita.super_cup": ("SCI", "20251217-20251223"),           # Supercoppa 2025 (overlap)
    "ned.supercup": ("NLSC", "20260725-20260810"),           # Johan Cruijff Schaal
    "esp.super_cup": ("SUC", "20260106-20260112"),           # Supercopa 2026 (overlap)
    "uefa.europa_qual": ("ELQ", "20260709-20260828"),        # Europa League qualifying
    "uefa.europa.conf_qual": ("ECLQ", "20260709-20260828"),  # Conference League qualifying
    "afc.asian.cup": ("AFAC", "20240112-20240210"),          # Asian Cup 2023, played 2024 (overlap)
}
KNOWN = {**DEFAULTS, **ROUND2}

CLOCK = re.compile(r"^\s*(\d{1,3})'?\s*(?:\+\s*(\d{1,2})'?)?\s*$")


def parse_clock(display):
    """ "45'+2'" -> (45, 2); "90'" -> (90, 0); "105'" -> (105, 0); anything else -> None."""
    match = CLOCK.match(display or "")
    if not match:
        return None
    return int(match.group(1)), int(match.group(2) or 0)


def minute_cell(minute, added):
    """Minute Grid rules, as for PitchAPI: 45+x -> cell 45 and 90+x -> cell 90, both
    flagged as added time; past 90 is extra time (105', 120'+1').
    Returns (cell, extra_time, includes_added), or None for a minute outside 1-120."""
    if not 1 <= minute <= 120:
        return None
    if minute > 90:
        return minute, True, bool(added)
    return minute, False, bool(added) and minute in (45, 90)


def get_json(url):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (hashlib.sha256(url.encode("utf-8")).hexdigest() + ".json")
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        return cached["status"], cached["body"]
    response = None
    for attempt, wait in enumerate((0.5, 2, 5, 10), start=1):  # be gentle: ESPN publishes no rate limits
        time.sleep(wait)
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            break
        except requests.RequestException as error:
            if attempt == 4:
                return None, {"error": f"{type(error).__name__} after 4 attempts"}
    try:
        body = response.json()
    except ValueError:
        body = {"error": "not JSON", "text": response.text[:200]}
    if response.status_code == 200:
        path.write_text(json.dumps({"status": 200, "body": body}), encoding="utf-8")
    return response.status_code, body


def match_goals(event):
    """Total score of a scoreboard event (shootout kicks are not in the score)."""
    competitors = (event.get("competitions") or [{}])[0].get("competitors", [])
    total = 0
    for competitor in competitors:
        try:
            total += int(competitor.get("score") or 0)
        except (TypeError, ValueError):
            return 1  # unknown score: allow the lookup
    return total


def goal_details(event):
    """Goal-like entries from a scoreboard event (competitions[0].details)."""
    competition = (event.get("competitions") or [{}])[0]
    return [d for d in competition.get("details", []) if d.get("scoringPlay") or "goal" in str(d.get("type", {}).get("text", "")).lower()]


def summary_goals(league, event_id):
    status, body = get_json(f"{BASE}/{league}/summary?event={event_id}")
    if status != 200:
        return status, []
    events = body.get("keyEvents") or []
    return status, [e for e in events if e.get("scoringPlay") or "goal" in str(e.get("type", {}).get("text", "")).lower()]


def describe(league, competition_id, day, event, detail):
    teams = {c.get("team", {}).get("id"): c.get("team", {}).get("displayName")
             for c in (event.get("competitions") or [{}])[0].get("competitors", [])}
    athletes = detail.get("athletesInvolved") or detail.get("participants") or []
    athlete = athletes[0] if athletes else {}
    athlete = athlete.get("athlete", athlete)
    clock = (detail.get("clock") or {}).get("displayValue")
    parsed = parse_clock(clock)
    kind = str((detail.get("type") or {}).get("text", ""))
    own = bool(detail.get("ownGoal")) or "own" in kind.lower()
    penalty = bool(detail.get("penaltyKick")) or "penalty" in kind.lower()
    shootout = bool(detail.get("shootout"))
    team_id = (detail.get("team") or {}).get("id")
    cell = minute_cell(*parsed) if parsed else None
    return {
        "league": league, "competition_id": competition_id, "date": day, "match_id": event.get("id"),
        "match": event.get("name"), "team_id": team_id, "team": teams.get(team_id),
        "athlete_id": athlete.get("id"), "athlete": athlete.get("displayName") or athlete.get("fullName"),
        "clock": clock, "minute": parsed[0] if parsed else None, "minute_added": parsed[1] if parsed else None,
        "cell": cell[0] if cell else None, "extra_time": cell[1] if cell else None,
        "type": kind, "penalty": penalty, "own_goal": own, "shootout": shootout,
    }


def days_in(dates):
    """ "20261101" or "20261101-20261103" -> ["20261101", "20261102", "20261103"] (at most 120 days)."""
    first, _, last = dates.partition("-")
    start = date(int(first[:4]), int(first[4:6]), int(first[6:8]))
    end = date(int(last[:4]), int(last[4:6]), int(last[6:8])) if last else start
    if end < start or (end - start).days > 120:
        raise ValueError(f"Date range must be forward and at most 120 days: {dates}")
    return [date.fromordinal(day).strftime("%Y%m%d") for day in range(start.toordinal(), end.toordinal() + 1)]


def error_text(body):
    if isinstance(body, dict):
        for key in ("error", "message", "detail"):
            if body.get(key):
                return str(body[key])[:160]
        return json.dumps(body)[:160]
    return str(body)[:160]


def probe(league, competition_id, dates, summary_budget):
    report = {"league": league, "competition_id": competition_id, "dates": dates, "status": None,
              "events": 0, "finished": 0, "goals": [], "raw_example": None, "from_summary": 0}
    # Is the league code known at all? (Scoreboard without a date: current fixtures.)
    code_status, code_body = get_json(f"{BASE}/{league}/scoreboard")
    report["code_status"] = code_status
    if code_status != 200:
        report["status"] = code_status
        report["error"] = (f"connection failed, rerun to retry: {error_text(code_body)}" if code_status is None
                           else f"league code not recognised by ESPN (HTTP {code_status}): {error_text(code_body)}")
        return report
    report["league_name"] = ((code_body.get("leagues") or [{}])[0]).get("name")
    # One request per day: a YYYYMMDD-YYYYMMDD range came back HTTP 400.
    events, statuses = {}, Counter()
    for day in days_in(dates):
        status, body = get_json(f"{BASE}/{league}/scoreboard?dates={day}&limit=200")
        statuses[status] += 1
        if status != 200:
            report.setdefault("error", f"{day}: HTTP {status} {error_text(body)}")
            continue
        for event in body.get("events", []):
            events[event.get("id")] = event
    report["status"] = dict(statuses)
    report["events"] = len(events)
    for event in events.values():
        if not ((event.get("status") or {}).get("type") or {}).get("completed"):
            continue
        report["finished"] += 1
        day = (event.get("date") or "")[:10]
        details = goal_details(event)
        if not details and match_goals(event) > 0 and summary_budget[0] > 0:  # 0-0: nothing to look up
            summary_budget[0] -= 1
            _status, details = summary_goals(league, event.get("id"))
            report["from_summary"] += bool(details)
        for detail in details:
            if report["raw_example"] is None:
                report["raw_example"] = detail
            report["goals"].append(describe(league, competition_id, day, event, detail))
    return report


def compare_with_transfermarkt(goals):
    """Per competition and day (on or before 2026-07-06), compare multisets of (cell, extra) minutes."""
    import duckdb

    pipeline = ROOT.parent / "footy-pipeline"
    days = sorted({(g["competition_id"], g["date"]) for g in goals if g["date"] and g["date"] <= "2026-07-06"})
    if not days:
        print("\nNo goals on days Transfermarkt covers (<= 2026-07-06); nothing to compare.")
        return
    with duckdb.connect(str(pipeline / "transfermarkt-datasets.duckdb"), read_only=True) as con:
        rows = con.execute(f"""
            SELECT gm.competition_id, strftime(g.date, '%Y-%m-%d'), g.minute, g.is_extra_time
            FROM '{str(pipeline / "goals_grid.parquet").replace(chr(92), "/")}' g
            JOIN games gm ON g.game_id = gm.game_id
            WHERE gm.competition_id IN ({",".join("?" * len({c for c, _ in days}))})
        """, sorted({c for c, _ in days})).fetchall()
    tm = defaultdict(Counter)
    for cid, day, minute, extra in rows:
        tm[(cid, day)][(minute, bool(extra))] += 1
    print("\n--- minutes vs Transfermarkt (same competition and day; own goals and shootouts excluded) ---")
    total = matched = 0
    for key in days:
        espn = Counter((g["cell"], g["extra_time"]) for g in goals
                       if (g["competition_id"], g["date"]) == key and not g["own_goal"] and not g["shootout"]
                       and g["cell"] is not None)
        both = sum((espn & tm[key]).values())
        total += sum(espn.values())
        matched += both
        print(f"{key[0]} {key[1]}: ESPN {sum(espn.values())}, Transfermarkt {sum(tm[key].values())}, same minute {both}")
    if total:
        print(f"Overall: {matched}/{total} ESPN goals ({100 * matched / total:.1f}%) have a Transfermarkt goal at the same minute that day")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--league", action="append", metavar="CODE[:DATES]",
                        help="ESPN league code with optional YYYYMMDD[-YYYYMMDD]; repeatable (default: a built-in set)")
    parser.add_argument("--summaries", type=int, default=40,
                        help="max match-summary requests when a scoreboard has no goal details (default 40)")
    parser.add_argument("--compare-tm", action="store_true", help="compare minutes with Transfermarkt on overlap days")
    parser.add_argument("--round2", action="store_true",
                        help="probe the second set of competitions found with --list-leagues")
    parser.add_argument("--list-leagues", action="store_true",
                        help="list ESPN's soccer league codes and suggest codes for the competitions still untested")
    parser.add_argument("--max-names", type=int, default=250, help="max league names to look up with --list-leagues")
    args = parser.parse_args()
    if args.list_leagues:
        discover(args.max_names)
        return

    targets = []
    default_set = ROUND2 if args.round2 else DEFAULTS
    for item in args.league or [f"{code}:{dates}" for code, (_cid, dates) in default_set.items()]:
        code, _, dates = item.partition(":")
        cid = KNOWN.get(code, ("?", ""))[0]
        targets.append((code, cid, dates or KNOWN.get(code, ("", date.today().strftime("%Y%m%d")))[1]))

    budget = [args.summaries]
    reports, all_goals = [], []
    for code, cid, dates in targets:
        report = probe(code, cid, dates, budget)
        reports.append(report)
        all_goals.extend(report["goals"])

    print("--- goals ---")
    for goal in all_goals:
        flags = " ".join(flag for flag, on in (("PEN", goal["penalty"]), ("OG", goal["own_goal"]),
                                               ("SHOOTOUT", goal["shootout"])) if on)
        cell = f"cell {goal['cell']}{' ET' if goal['extra_time'] else ''}" if goal["cell"] is not None else "cell ?"
        print(f"{goal['league']} {goal['date']} {goal['match']} | {goal['team']} | {goal['athlete']} "
              f"[espn {goal['athlete_id']}] | clock {goal['clock']!r} -> {goal['minute']}+{goal['minute_added']} "
              f"{cell} | {goal['type']} {flags}".rstrip())

    print("\n--- first raw goal entry per league (schema) ---")
    for report in reports:
        if report["raw_example"] is not None:
            print(f"{report['league']}: {json.dumps(report['raw_example'], ensure_ascii=False)[:1200]}")

    print("\n--- summary ---")
    for r in reports:
        goals = r["goals"]
        parsed = [g for g in goals if g["minute"] is not None]
        print(f"{r['league']:22} ({r['competition_id']}) {r['dates']}: HTTP {r['status']}, "
              f"{r.get('league_name') or '-'}, matches {r['events']}, finished {r['finished']}, goals {len(goals)} "
              f"(with scorer id {sum(1 for g in goals if g['athlete_id'])}, clock parsed {len(parsed)}, "
              f"added time {sum(1 for g in parsed if g['minute_added'])}, penalties {sum(g['penalty'] for g in goals)}, "
              f"own goals {sum(g['own_goal'] for g in goals)}, shootout {sum(g['shootout'] for g in goals)}, "
              f"matches needing summary {r['from_summary']})"
              + (f" ERROR {r['error']}" if r.get("error") else ""))
    unparsed = Counter(g["clock"] for g in all_goals if g["minute"] is None)
    if unparsed:
        print(f"Unparsed clock values: {dict(unparsed.most_common(10))}")
    print(f"Summary requests left: {budget[0]} of {args.summaries}")

    OUT.write_text(json.dumps({"probed": date.today().isoformat(), "goals": all_goals,
                               "reports": [{k: v for k, v in r.items() if k not in ("goals", "raw_example")} for r in reports]},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    if args.compare_tm:
        compare_with_transfermarkt(all_goals)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
