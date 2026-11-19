#!/usr/bin/env python3
"""
prep.py - builds Minute Grid's site data.

Sources:
  data/base/      Transfermarkt snapshot (make_tm_snapshot.py): history up to its last day
  data/espn/      ESPN goals, squads and player matches (espn_sync.py): the cups
                  Transfermarkt lacks or has fewer goals for, and everything after
                  Transfermarkt's last day
Scope (scope.py): the top 5 leagues, their domestic cups and super cups, and
the UEFA club competitions proper. Only players in a current squad of a top-5
league club are written; a player who leaves drops out, and comes back
automatically when he is in a top-5 squad again.

Outputs:
  data/players/{id}.json  per-player grid (files of players no longer in scope are removed)
  data/index.json         search index
  data/boards.json        complete / almost complete boards and gaps closed this month
  data/leagues.json, data/leagues/{id}.json   league -> club -> player explorer
  data/coverage.json      the competitions counted

Only goals inside the rolling window (10 years up to the build day, or
--today YYYY-MM-DD) are written; the site re-applies the window every day.
"""

import argparse
import csv
import json
import pathlib
import sys
import time
from collections import defaultdict
from datetime import date, timedelta

import tm_base
from boards import ALMOST_MAX, build_boards
from grid_rules import choose_sources, gap_closed_date, use_espn_goal, use_tm_goal
from images import club_with_logo, load_images, player_image
from leagues import build_leagues
from scope import BY_ID, COMPETITIONS, ESPN_ID_OFFSET, LEAGUES, season_of
from window_rules import WINDOW_YEARS, in_window, window_start

LOCK_WAITS = (0.5, 1, 2, 3, 4, 5, 5)  # about 20 s in total
locked_files: list[str] = []


def write_json_retrying(path, value, *, required=True):
    """Windows can lock a file for a while (antivirus, the search indexer, a
    running `next dev` watching data/). Wait and retry for about 20 seconds; a
    player file that stays locked (required=False) is skipped and reported."""
    for attempt, wait in enumerate((*LOCK_WAITS, None), start=1):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(value, f, separators=(",", ":"), ensure_ascii=False)
            return True
        except OSError as error:
            if error.errno not in (13, 22):
                raise
            if wait is None:
                if required:
                    raise
                print(f"  {path.name} is still locked; skipped (rerun prep.py to write it)")
                locked_files.append(path.name)
                return False
            print(f"  {path.name} is locked ({error.strerror}); retry {attempt}/{len(LOCK_WAITS)} in {wait:g}s")
            time.sleep(wait)


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT_DIR / "data"
ESPN_DIR = DATA / "espn"
OUT_PLAYERS_DIR = DATA / "players"
OUT_LEAGUES_DIR = DATA / "leagues"
IMAGES_PATH = DATA / "images.json"
RECENT_SCORER_DAYS = 30  # a league goal this recent also places a player at that club

parser = argparse.ArgumentParser(description="Minute Grid data preparation")
parser.add_argument("--boards-only", action="store_true",
                    help="regenerate boards and coverage without writing player files or the index")
parser.add_argument("--today", type=date.fromisoformat, default=date.today(),
                    help="build day for the rolling window (default: today)")
args = parser.parse_args()
WINDOW_START = window_start(args.today).isoformat()
print(f"Rolling window: goals from {WINDOW_START} ({WINDOW_YEARS} years before {args.today})")


def read_csv(name):
    path = ESPN_DIR / name
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def truthy(value):
    return value in (True, "True", "true", "1")


# ---------------------------------------------------------------------------
# 1. Inputs
# ---------------------------------------------------------------------------
tm_last = tm_base.last_day()
tm_goals = tm_base.goals()
tm_names = {int(p["player_id"]): p["name"] for p in tm_base.players()}
espn_goals = read_csv("goals.csv")
rosters = read_csv("rosters.csv")
teams = {t["team_id"]: t for t in read_csv("teams.csv")}
state_path = ESPN_DIR / "state.json"
state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
if not rosters:
    sys.exit("ERROR: data/espn/rosters.csv is empty. Run python scripts/espn_sync.py --backfill first.")
print(f"Transfermarkt up to {tm_last}: {len(tm_goals):,} goals | ESPN: {len(espn_goals):,} goals, "
      f"{len(rosters):,} squad players")

pid_of = {r["athlete_id"]: int(r["tm_player_id"]) for r in read_csv("athlete_map.csv")}
new_names = {}
for row in read_csv("new_players.csv"):
    pid_of[row["athlete_id"]] = ESPN_ID_OFFSET + int(row["athlete_id"])
    new_names[ESPN_ID_OFFSET + int(row["athlete_id"])] = row["name"]

# ---------------------------------------------------------------------------
# 2. Who is in scope: players in a current top-5 squad
# ---------------------------------------------------------------------------
images = load_images(IMAGES_PATH)


def club_for(team_id, team_name, competition_id):
    team = teams.get(team_id, {})
    club = {"name": team.get("name") or team_name, "id": team.get("tm_club_id") or f"espn-{team_id}"}
    out = club_with_logo(images, club if team.get("tm_club_id") else {**club, "id": None}, competition_id)
    out["id"] = club["id"]
    if not out.get("logo") and team.get("logo"):
        out["logo"] = team["logo"]
    return out


current = {}  # pid -> {club, competitionId, asOf}
for row in rosters:
    pid = pid_of.get(row["athlete_id"])
    if pid is None:
        continue
    if pid in current and current[pid]["asOf"] >= row["first_seen"]:
        continue
    current[pid] = {"club": club_for(row["team_id"], row["team"], row["competition_id"]),
                    "competitionId": row["competition_id"], "asOf": row["first_seen"],
                    "espnName": row["name"]}
league_ids = {league.id for league in LEAGUES}
recent_from = (args.today - timedelta(days=RECENT_SCORER_DAYS)).isoformat()
added_by_goal = 0
for goal in espn_goals:
    pid = pid_of.get(goal["athlete_id"])
    if pid is None or pid in current or goal["competition_id"] not in league_ids or goal["date"] < recent_from:
        continue
    current[pid] = {"club": club_for(goal["team_id"], goal["team"], goal["competition_id"]),
                    "competitionId": goal["competition_id"], "asOf": goal["date"], "espnName": goal["athlete"]}
    added_by_goal += 1
unmatched_squad = len({r["athlete_id"] for r in rosters if r["athlete_id"] not in pid_of})
print(f"  players in top-5 squads: {len(current):,} (+{added_by_goal} from league goals in the last "
      f"{RECENT_SCORER_DAYS} days; {unmatched_squad} squad players not matched yet, see data/espn/review.csv)")

# ---------------------------------------------------------------------------
# 3. Goals: one source per competition-season
# ---------------------------------------------------------------------------
tm_counts, espn_counts = defaultdict(int), defaultdict(int)
for g in tm_goals:
    if g["date"] <= tm_last:
        tm_counts[(g["competition_id"], season_of(g["date"]))] += 1
for g in espn_goals:
    if g["date"] <= tm_last:
        espn_counts[(g["competition_id"], season_of(g["date"]))] += 1
choice = choose_sources(tm_counts, espn_counts)
espn_seasons = sorted(f"{cid} {season}/{str(season + 1)[2:]}" for (cid, season), src in choice.items()
                      if src == "espn" and BY_ID[cid].history == "best")
if espn_seasons:
    print(f"  seasons where ESPN has more goals than Transfermarkt (ESPN used): {', '.join(espn_seasons)}")

regular = defaultdict(lambda: defaultdict(list))  # pid -> minute -> [goal]
extra = defaultdict(lambda: defaultdict(list))
last_goal = {}
data_up_to = "1900-01-01"
counted = {"tm": 0, "espn": 0, "live": 0}

for g in tm_goals:
    pid, day = int(g["player_id"]), g["date"]
    if pid not in current or not use_tm_goal(g["competition_id"], day, tm_last, choice):
        continue
    minute, is_extra = int(g["minute"]), bool(g["is_extra_time"])
    if (not is_extra and not 1 <= minute <= 90) or not in_window(day, WINDOW_START):
        continue
    entry = {"date": day, "opponent": g["opponent"] or "Unknown",
             "competition": BY_ID[g["competition_id"]].name, "club": g["club"] or "Unknown"}
    (extra if is_extra else regular)[pid][minute].append(entry)
    last_goal[pid] = max(last_goal.get(pid, day), day)
    data_up_to = max(data_up_to, day)
    counted["tm"] += 1

for g in espn_goals:
    pid, day = pid_of.get(g["athlete_id"]), g["date"]
    if pid not in current or not use_espn_goal(g["competition_id"], day, tm_last, choice):
        continue
    data_up_to = max(data_up_to, day)
    if not in_window(day, WINDOW_START):
        continue
    cell, is_extra = int(g["cell"]), truthy(g["extra"])
    entry = {"date": day, "opponent": g["opponent"] or "Unknown",
             "competition": BY_ID[g["competition_id"]].name, "club": g["team"] or "Unknown", "source": "espn"}
    if truthy(g["added_time"]):
        entry["addedTime"] = True
    if truthy(g["penalty"]):
        entry["penalty"] = True
    if day > tm_last:
        entry["live"] = True
        counted["live"] += 1
    (extra if is_extra else regular)[pid][cell].append(entry)
    last_goal[pid] = max(last_goal.get(pid, day), day)
    counted["espn"] += 1

for minutes in (*regular.values(), *extra.values()):
    for goals in minutes.values():
        goals.sort(key=lambda e: (e["date"], e["competition"], e["opponent"]))
data_up_to = max(data_up_to, state.get("synced_through") or "")
print(f"  goals in the window: Transfermarkt {counted['tm']:,}, ESPN {counted['espn']:,} "
      f"(of which after {tm_last}: {counted['live']:,}); data up to {data_up_to}")

# ---------------------------------------------------------------------------
# 4. Player files, index, boards, leagues
# ---------------------------------------------------------------------------
OUT_PLAYERS_DIR.mkdir(parents=True, exist_ok=True)
player_ids = sorted(pid for pid in current if pid in regular or pid in extra)
index_entries, board_entries, league_entries, gaps_closed = [], [], [], []
print(f"Writing {len(player_ids):,} players (squad players with a goal in the window) ...")

for pid in player_ids:
    info = current[pid]
    name = tm_names.get(pid) or new_names.get(pid) or info["espnName"] or f"Player {pid}"
    reg, ext = regular.get(pid, {}), extra.get(pid, {})
    image = player_image(images, pid)
    minutes_data, minutes_scored, counts = {}, [], {}
    for m in range(1, 91):
        goals = reg.get(m, [])
        minutes_data[str(m)] = {"count": len(goals), "firstDate": goals[0]["date"] if goals else None, "goals": goals}
        if goals:
            closed = gap_closed_date(goals)
            if closed:
                minutes_data[str(m)]["gapClosed"] = closed
                gaps_closed.append({"id": pid, "name": name, "minute": m, "date": closed})
            minutes_scored.append(m)
            counts[str(m)] = len(goals)
    extra_list = []
    for m in sorted(ext):
        goals = ext[m]
        extra_list.append({"minute": m, "count": len(goals), "firstDate": goals[0]["date"], "goals": goals})
        counts[str(m)] = len(goals)
    regular_goals = sum(len(g) for g in reg.values())
    extra_goals = sum(len(g) for g in ext.values())
    total = regular_goals + extra_goals
    missing = [m for m in range(1, 91) if m not in reg]
    player_json = {
        "id": pid, "name": name, "club": info["club"], "image": image, "active": True, "asOf": info["asOf"],
        "minutes": minutes_data, "extraTime": extra_list, "minutesScored": minutes_scored,
        "extraTimeMinutes": sorted(ext), "minuteGoalCounts": counts, "missingMinutes": missing,
        "totalGoals": total, "regularGoals": regular_goals, "extraGoals": extra_goals,
        "minutesScoredCount": len(minutes_scored), "inWindow": total > 0,
    }
    if not args.boards_only:
        write_json_retrying(OUT_PLAYERS_DIR / f"{pid}.json", player_json, required=False)
    league_entries.append({"id": pid, "name": name, "club": info["club"], "active": True, "image": image,
                           "competitionId": info["competitionId"], "goals": total, "minutes": len(minutes_scored)})
    index_entries.append({"id": pid, "name": name, "goalCount": total,
                          "club": {"name": info["club"]["name"], "id": info["club"]["id"]},
                          "active": True, "asOf": info["asOf"], "inWindow": True})
    if len(missing) <= ALMOST_MAX:
        board_entries.append({"id": pid, "name": name, "club": info["club"], "image": image, "active": True,
                              "asOf": info["asOf"], "goals": total, "missing": missing,
                              "lastGoalDate": last_goal[pid], "counts": [len(reg.get(m, [])) for m in range(1, 91)]})

removed = 0
if not args.boards_only:
    keep = {f"{pid}.json" for pid in player_ids}
    for stale in OUT_PLAYERS_DIR.glob("*.json"):
        if stale.name not in keep:
            stale.unlink()
            removed += 1

coverage = {group: [] for group in ("leagues", "cups", "superCups", "uefa", "international")}
for competition in COMPETITIONS:
    coverage[competition.group].append({"id": competition.id, "name": competition.name, "country": competition.country})

if not args.boards_only:
    write_json_retrying(DATA / "index.json", {
        "dataUpTo": data_up_to,
        "windowStart": WINDOW_START,
        "liveFrom": (date.fromisoformat(tm_last) + timedelta(days=1)).isoformat(),
        # A competition that has ended (Coupe de la Ligue, 2020) gets no live updates.
        "liveCompetitions": [c.id for c in COMPETITIONS if not c.until or c.until > tm_last],
        "players": sorted(index_entries, key=lambda p: (-p["goalCount"], p["id"])),
    })

month = args.today.isoformat()[:7]
boards = build_boards(board_entries)
gaps_this_month = [gap for gap in gaps_closed if gap["date"].startswith(month)]
boards["gapsClosed"] = sorted(gaps_this_month, key=lambda g: (g["date"], g["name"], g["minute"]), reverse=True)[:30]
boards["gapsClosedMonth"] = month
write_json_retrying(DATA / "boards.json", boards)

league_summary, league_details = build_leagues(
    league_entries, {league.id: {"name": league.name, "country": league.country} for league in LEAGUES})
for league in league_summary:
    logo = images["leagues"].get(league["id"])
    if logo:
        league["logo"] = league_details[league["id"]]["logo"] = logo
OUT_LEAGUES_DIR.mkdir(parents=True, exist_ok=True)
for stale in OUT_LEAGUES_DIR.glob("*.json"):
    if stale.stem not in league_details:
        stale.unlink()
for cid, detail in league_details.items():
    write_json_retrying(OUT_LEAGUES_DIR / f"{cid}.json", detail)
write_json_retrying(DATA / "leagues.json", {"leagues": league_summary})
write_json_retrying(DATA / "coverage.json", coverage)

print(f"Done: {len(player_ids):,} players, {len(league_summary)} leagues, "
      f"{sum(l['clubCount'] for l in league_summary):,} clubs"
      + ("" if args.boards_only else f"; removed {removed:,} player files no longer in scope"))
print(f"  boards: {len(boards['complete'])} complete, {len(boards['almost'])} almost complete")
print(f"  gaps closed by live goals: {len(gaps_closed):,} (this month: {len(gaps_this_month):,})")

if locked_files:
    print(f"\nWARNING: {len(locked_files)} player file(s) stayed locked and were not updated: "
          f"{', '.join(locked_files[:20])}{' …' if len(locked_files) > 20 else ''}")
    print("Stop `next dev` (it watches data/) and rerun python scripts/prep.py.")
    sys.exit(1)
