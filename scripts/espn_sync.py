#!/usr/bin/env python3
"""Fetch goals and squads from ESPN for the launch competitions (scope.py) and
match ESPN players to Transfermarkt. This is the only live source; PitchAPI
is retired (its scripts are kept, unused).

Modes:
  python scripts/espn_sync.py --backfill   once: every season from 2016/17 for
        the cups and super cups (and the EFL Cup / Coupe de France / Coupe de
        la Ligue, which only ESPN has), from 2025/26 for the leagues and UEFA.
        Uses ESPN's season calendar, so only match days are fetched; finished
        seasons are cached in data/espn_cache/ and marked done.
  python scripts/espn_sync.py              the scheduled update: the last few
        days of every competition (fresh, never cached), the squads once a
        day, then matching. This is what .github/workflows/update-data.yml runs.
  python scripts/espn_sync.py --report     no requests: per competition and
        season, ESPN matches / goal detail / goals against Transfermarkt's
        goals, and which source prep.py will use.

Writes data/espn/: matches.csv, goals.csv, rosters.csv, teams.csv,
athlete_map.csv, new_players.csv, review.csv, state.json.
Then run python scripts/prep.py to rebuild the site data.
"""

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

if __package__:
    from . import espn_feed as feed
    from . import espn_map, tm_base
    from .grid_rules import choose_sources
    from .scope import BY_ID, COMPETITIONS, LEAGUES, fetch_from, season_of
else:
    import espn_feed as feed
    import espn_map
    import tm_base
    from grid_rules import choose_sources
    from scope import BY_ID, COMPETITIONS, LEAGUES, fetch_from, season_of

DIR = tm_base.ROOT / "data" / "espn"
MATCH_FIELDS = ["competition_id", "match_id", "date", "home_team_id", "home", "away_team_id", "away",
                "home_score", "away_score", "goal_events"]
GOAL_FIELDS = ["competition_id", "match_id", "date", "team_id", "team", "opponent", "athlete_id", "athlete",
               "minute", "minute_added", "cell", "extra", "added_time", "penalty"]
ROSTER_FIELDS = ["competition_id", "team_id", "team", "athlete_id", "name", "full_name", "dob", "nationality",
                 "first_seen", "last_seen"]
TEAM_FIELDS = ["competition_id", "team_id", "name", "logo", "tm_club_id"]
MAP_FIELDS = ["athlete_id", "tm_player_id", "method", "espn_name", "tm_name", "mapped_on"]
NEW_FIELDS = ["athlete_id", "name", "dob", "team", "competition_id"]
REVIEW_FIELDS = ["athlete_id", "name", "dob", "team", "competition_id", "reason"]
CALENDAR_VERSION = 2   # bump to read every season again (cached days cost nothing)
RECENT_DAYS = 4        # every scheduled run re-reads this many days back (late corrections)
FRESH_DAYS = 4         # days this recent are never cached
ROSTER_HOURS = 20      # squads are refreshed at most about once a day


def read_csv(name):
    path = DIR / name
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(name, fields, rows):
    DIR.mkdir(parents=True, exist_ok=True)
    with open(DIR / name, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load_state():
    path = DIR / "state.json"
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"codes": {}, "done": {}}
    if state.get("calendar_version") != CALENDAR_VERSION:
        # Version 1 read only the first day of each cup/UEFA round and kept
        # duplicated goal events: every season is read again.
        state["done"] = {}
        state["calendar_version"] = CALENDAR_VERSION
    return state


def save_state(state):
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / "state.json").write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")


def utc_today():
    return datetime.now(timezone.utc).date()


def resolve_code(competition, state):
    if state["codes"].get(competition.id):
        return state["codes"][competition.id]
    for code in competition.espn:
        if feed.code_works(code):
            state["codes"][competition.id] = code
            return code
    print(f"  {competition.id}: ESPN does not recognise {', '.join(competition.espn)}; skipped")
    return None


def last_day(competition, today):
    return min(today.isoformat(), competition.until or "9999-12-31")


def season_days(code, competition, season, today, report):
    """Match days (YYYYMMDD) of one season: ESPN's calendar, else every day."""
    first = max(f"{season}-07-01", fetch_from(competition))
    last = min(f"{season + 1}-06-30", last_day(competition, today))
    if first > last:
        return []
    seed = max(first, min(f"{season}-10-01", last))
    fresh = date.fromisoformat(last) >= today - timedelta(days=FRESH_DAYS)
    status, body = feed.scoreboard(code, feed.compact(seed), cache=not fresh)
    lo, hi = feed.compact(first), feed.compact(last)
    days = [d for d in feed.calendar_days(body if status == 200 else {}) if lo <= d <= hi]
    if days:
        report["calendar"] += 1
        return days
    report["scanned"] += 1
    print(f"    {competition.id} {season}: no ESPN calendar, scanning every day ({first} to {last})", flush=True)
    return feed.days_between(first, last)


def fetch_days(code, competition, days, today, budget):
    """A match listed on two days' scoreboards (time zones) is kept once."""
    matches, goals, failed, seen = [], [], 0, set()
    fresh_from = (today - timedelta(days=FRESH_DAYS)).strftime("%Y%m%d")
    for day in days:
        day_matches, day_goals, ok = feed.read_day(code, competition.id, day, cache=day < fresh_from,
                                                   summary_budget=budget)
        failed += not ok
        new_ids = {m["match_id"] for m in day_matches} - seen
        matches.extend(m for m in day_matches if m["match_id"] in new_ids)
        goals.extend(g for g in day_goals if g["match_id"] in new_ids)
        seen |= new_ids
    return matches, goals, failed


def merge(matches, goals, new_matches, new_goals):
    """Replace every re-fetched match (and its goals)."""
    refreshed = {(m["competition_id"], m["match_id"]) for m in new_matches}
    kept = [m for m in matches if (m["competition_id"], m["match_id"]) not in refreshed]
    kept_goals = [g for g in goals if (g["competition_id"], g["match_id"]) not in refreshed]
    by_key = {(m["competition_id"], m["match_id"]): m for m in new_matches}
    all_matches = sorted(kept + list(by_key.values()), key=lambda m: (m["date"], m["competition_id"], m["match_id"]))
    all_goals = sorted(kept_goals + new_goals,
                       key=lambda g: (g["date"], g["competition_id"], g["match_id"], int(g["minute"]), g["athlete_id"]))
    return all_matches, all_goals


def sync_goals(args, state, today):
    matches, goals = read_csv("matches.csv"), read_csv("goals.csv")
    budget = [8000 if args.backfill else 200]
    new_matches, new_goals, failures = [], [], 0
    report = {"calendar": 0, "scanned": 0}
    if not args.backfill and not state.get("synced_through"):
        sys.exit("ERROR: no ESPN data yet. Run python scripts/espn_sync.py --backfill once first.")
    for competition in COMPETITIONS:
        code = resolve_code(competition, state)
        if not code:
            continue
        if args.backfill:
            done = set(state["done"].get(competition.id, []))
            first_season = season_of(fetch_from(competition))
            last_season = season_of(last_day(competition, today))
            for season in range(first_season, last_season + 1):
                if season in done:
                    continue
                days = season_days(code, competition, season, today, report)
                m, g, failed = fetch_days(code, competition, days, today, budget)
                new_matches += m
                new_goals += g
                failures += failed
                print(f"  {competition.id} {season}/{str(season + 1)[2:]}: {len(days)} days, {len(m)} matches, "
                      f"{len(g)} goals" + (f", {failed} days failed (rerun)" if failed else ""), flush=True)
                season_end = date(season + 1, 6, 30)
                if not failed and (season_end < today - timedelta(days=FRESH_DAYS)
                                   or (competition.until and season_end.isoformat() >= competition.until)):
                    done.add(season)
            state["done"][competition.id] = sorted(done)
        else:
            start = min(date.fromisoformat(state["synced_through"]), today) - timedelta(days=RECENT_DAYS)
            first = max(start.isoformat(), fetch_from(competition))
            last = last_day(competition, today)
            if first > last:
                continue
            m, g, failed = fetch_days(code, competition, feed.days_between(first, last), today, budget)
            new_matches += m
            new_goals += g
            failures += failed
            if m:
                print(f"  {competition.id}: {len(m)} finished matches, {len(g)} goals since {first}")
    matches, goals = merge(matches, goals, new_matches, new_goals)
    write_csv("matches.csv", MATCH_FIELDS, matches)
    write_csv("goals.csv", GOAL_FIELDS, goals)
    if not failures:
        state["synced_through"] = today.isoformat()
    print(f"ESPN goals stored: {len(goals):,} in {len(matches):,} matches"
          + (f" | seasons by calendar {report['calendar']}, scanned {report['scanned']}" if args.backfill else ""))
    if failures:
        print(f"WARNING: {failures} days could not be fetched; the next run retries them.")
    return goals


def sync_rosters(state, today, force):
    fetched = state.get("rosters_fetched")
    if not force and fetched and datetime.fromisoformat(fetched) > datetime.now(timezone.utc) - timedelta(hours=ROSTER_HOURS):
        return read_csv("rosters.csv"), read_csv("teams.csv")
    old = read_csv("rosters.csv")
    old_teams = read_csv("teams.csv")
    first_seen = {(r["athlete_id"], r["team_id"]): r["first_seen"] for r in old}
    rows, teams, failed_leagues = [], [], []
    for league in LEAGUES:
        code = resolve_code(league, state)
        league_teams = feed.league_teams(code) if code else None
        league_rows, league_team_rows, failed = [], [], not league_teams
        for team_id, name, logo in league_teams or []:
            athletes = feed.team_roster(code, team_id)
            if athletes is None:
                failed = True
                break
            league_team_rows.append({"competition_id": league.id, "team_id": team_id, "name": name, "logo": logo or ""})
            for athlete in athletes:
                league_rows.append({**athlete, "competition_id": league.id, "team_id": team_id, "team": name,
                                    "first_seen": first_seen.get((athlete["athlete_id"], team_id), today.isoformat()),
                                    "last_seen": today.isoformat()})
        if failed:  # keep yesterday's squads rather than dropping a league
            failed_leagues.append(league.id)
            league_rows = [r for r in old if r["competition_id"] == league.id]
            league_team_rows = [t for t in old_teams if t["competition_id"] == league.id]
        rows += league_rows
        teams += league_team_rows
        print(f"  squads {league.id}: {len(league_team_rows)} teams, {len(league_rows)} players"
              + (" (fetch failed: kept the previous squads)" if failed else ""))
    with_dob = sum(1 for r in rows if r["dob"])
    print(f"Squad players: {len(rows):,} ({with_dob:,} with a date of birth)")
    if not failed_leagues:
        state["rosters_fetched"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return rows, teams


def run_mapping(rosters, teams, goals, today):
    if not tm_base.exists():
        print("Matching skipped: data/base/ is missing (run python scripts/make_tm_snapshot.py once).")
        write_csv("rosters.csv", ROSTER_FIELDS, rosters)
        write_csv("teams.csv", TEAM_FIELDS, teams)
        return
    existing = {r["athlete_id"]: r for r in read_csv("athlete_map.csv")}
    mapped, team_map, new_players, review = espn_map.update(
        rosters, existing, tm_base.players(), tm_base.goals(), goals, tm_base.clubs(),
        tm_base.last_day(), today.isoformat())
    for team in teams:
        team["tm_club_id"] = team_map.get(team["team_id"], "")
    write_csv("rosters.csv", ROSTER_FIELDS, rosters)
    write_csv("teams.csv", TEAM_FIELDS, teams)
    write_csv("athlete_map.csv", MAP_FIELDS, sorted(mapped.values(), key=lambda r: int(r["athlete_id"])))
    write_csv("new_players.csv", NEW_FIELDS, new_players)
    write_csv("review.csv", REVIEW_FIELDS, review)
    squad = {r["athlete_id"] for r in rosters}
    methods = Counter(mapped[a]["method"].split(":")[0] for a in squad if a in mapped)
    print(f"Matched squad players: {sum(methods.values()):,} of {len(squad):,} "
          f"({', '.join(f'{m} {n}' for m, n in methods.most_common())})")
    print(f"  new players (not in Transfermarkt, ESPN-only page): {len(new_players)}")
    print(f"  to review (not shown until matched): {len(review)} -> data/espn/review.csv")
    print(f"  ESPN teams matched to a Transfermarkt club: {len(team_map)} of {len(teams)}")


def report():
    matches, goals = read_csv("matches.csv"), read_csv("goals.csv")
    tm_last = tm_base.last_day() if tm_base.exists() else "0000-00-00"
    tm_counts = Counter()
    if tm_base.exists():
        for g in tm_base.goals():
            if g["date"] <= tm_last:
                tm_counts[(g["competition_id"], season_of(g["date"]))] += 1
    espn_counts = Counter((g["competition_id"], season_of(g["date"])) for g in goals if g["date"] <= tm_last)
    choice = choose_sources(tm_counts, espn_counts)
    per = defaultdict(lambda: {"matches": 0, "scored": 0, "detail": 0, "goals": 0, "score_goals": 0})
    for m in matches:
        key = (m["competition_id"], season_of(m["date"]))
        total = sum(int(m[k]) for k in ("home_score", "away_score") if m[k] not in ("", None))
        per[key]["matches"] += 1
        per[key]["score_goals"] += total
        per[key]["scored"] += total > 0
        per[key]["detail"] += total > 0 and int(m["goal_events"] or 0) > 0
    for g in goals:
        per[(g["competition_id"], season_of(g["date"]))]["goals"] += 1
    print(f"Transfermarkt's last day: {tm_last}. 'detail' = matches with goals that have goal events; "
          "'events/score' = goal events ESPN gave against the scorelines.")
    for competition in COMPETITIONS:
        keys = sorted(k for k in set(per) | {k for k in tm_counts if k[0] == competition.id} if k[0] == competition.id)
        print(f"\n{competition.id} {competition.name} (history: {competition.history})")
        if not keys:
            print("  no data")
        for key in keys:
            p = per[key]
            used = choice.get(key, "espn") if f"{key[1]}-07-01" <= tm_last else "espn (after Transfermarkt)"
            detail = f"{p['detail']}/{p['scored']}" if p["scored"] else "-"
            print(f"  {key[1]}/{str(key[1] + 1)[2:]}: ESPN matches {p['matches']:4}, detail {detail:>9}, "
                  f"ESPN goals {p['goals']:5} (scorelines {p['score_goals']:5}) | Transfermarkt goals "
                  f"{tm_counts.get(key, 0):5} -> uses {used}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backfill", action="store_true", help="fetch every season not yet done (first run)")
    parser.add_argument("--rosters", action="store_true", help="refresh the squads even if fetched today")
    parser.add_argument("--report", action="store_true", help="print coverage per competition and season; no requests")
    parser.add_argument("--today", type=date.fromisoformat, default=None, help="override today (UTC)")
    args = parser.parse_args()
    if args.report:
        report()
        return
    today = args.today or utc_today()
    state = load_state()
    goals = sync_goals(args, state, today)
    rosters, teams = sync_rosters(state, today, force=args.rosters or args.backfill)
    run_mapping(rosters, teams, goals, today)
    save_state(state)
    print(f"Requests: {feed.stats['requests']:,} sent, {feed.stats['cached']:,} from cache, "
          f"{feed.stats['failed']:,} failed")


if __name__ == "__main__":
    main()
