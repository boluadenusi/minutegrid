#!/usr/bin/env python3
"""Sync live PitchAPI goals (from 2026-07-07) into data/live_goals.parquet.

Only competitions confirmed in data/competition_overrides.csv are synced.
Played (finished) matches are listed per league season, then processed date
by date: events are fetched, Goal events kept, own goals and shootout kicks
dropped, penalties kept. The file is saved after every date.

Rerunnable: matches already processed (data/live_matches.json) are skipped,
including a match whose PitchAPI id changed but whose date and team names
are the same. Goals by unmapped players are stored with an empty
tm_player_id, so a later mapping picks them up on the next run; prep.py
ignores them. HTTP 429 honours Retry-After (see pitch_cache.py).
"""

import argparse
import csv
import json
import os
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

import duckdb

if __package__:
    from .map_pitchapi import DATA, read_csv, seasons_in_range
    from .mapping_rules import confirmed_competitions
    from .pitch_cache import CachedPitchClient, PitchRequestError
    from .pitch_goals import goal_cell
    from .probe_pitchapi import create_session, is_goal_event, safe_id
else:
    from map_pitchapi import DATA, read_csv, seasons_in_range
    from mapping_rules import confirmed_competitions
    from pitch_cache import CachedPitchClient, PitchRequestError
    from pitch_goals import goal_cell
    from probe_pitchapi import create_session, is_goal_event, safe_id


LIVE_START = date(2026, 7, 7)
OUT = DATA / "live_goals.parquet"
STATE = DATA / "live_matches.json"
UNMATCHED = DATA / "live_unmatched.csv"
# Events cached less than this long after kick-off may predate the final whistle.
SETTLED_AFTER = timedelta(hours=4)
COLUMNS = [
    ("date", "DATE"), ("match_id", "VARCHAR"), ("home", "VARCHAR"), ("away", "VARCHAR"),
    ("home_team_id", "VARCHAR"), ("away_team_id", "VARCHAR"), ("competition_id", "VARCHAR"),
    ("pitch_league_id", "VARCHAR"), ("team_id", "VARCHAR"), ("club_name", "VARCHAR"),
    ("tm_club_id", "VARCHAR"), ("source_player_id", "VARCHAR"), ("tm_player_id", "BIGINT"),
    ("player_name", "VARCHAR"), ("minute", "INTEGER"), ("minute_added", "INTEGER"),
    ("period", "VARCHAR"), ("is_penalty", "BOOLEAN"), ("source", "VARCHAR"),
]


def load_rows():
    if not OUT.exists():
        return []
    with duckdb.connect() as con:
        cursor = con.execute(f"SELECT * FROM '{str(OUT).replace(chr(92), '/')}'")
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]


def save(rows, state):
    """Write the parquet file and state atomically (temp file, then replace)."""
    DATA.mkdir(parents=True, exist_ok=True)
    fd, temp_parquet = tempfile.mkstemp(suffix=".parquet", dir=DATA)
    os.close(fd)
    try:
        with duckdb.connect() as con:
            con.execute(f"CREATE TABLE live ({', '.join(f'{name} {kind}' for name, kind in COLUMNS)})")
            if rows:
                con.executemany(
                    f"INSERT INTO live VALUES ({', '.join('?' * len(COLUMNS))})",
                    [[row[name] for name, _ in COLUMNS] for row in rows],
                )
            con.execute(f"COPY (SELECT * FROM live ORDER BY date, match_id, minute) "
                        f"TO '{temp_parquet.replace(chr(92), '/')}' (FORMAT PARQUET)")
        os.replace(temp_parquet, OUT)
    finally:
        if os.path.exists(temp_parquet):
            os.remove(temp_parquet)
    fd, temp_state = tempfile.mkstemp(suffix=".json", dir=DATA)
    with os.fdopen(fd, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(temp_state, STATE)


def settled(client, path, match):
    """True when a cached events response was written well after kick-off."""
    cached = client.cached_at(path)
    if cached is None:
        return False
    kickoff = match.get("time_utc")
    if kickoff:
        start = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
    else:
        start = datetime.combine(date.fromisoformat(match["date"]), datetime.max.time(), timezone.utc)
    return datetime.fromtimestamp(cached, timezone.utc) >= start + SETTLED_AFTER


def main(client):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", type=date.fromisoformat, default=LIVE_START)
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    if args.start < LIVE_START:
        raise ValueError(f"--start must be on or after {LIVE_START}; earlier goals come from Transfermarkt")
    if args.end < args.start:
        raise ValueError("--end must not precede --start")

    with (DATA / "coverage.json").open(encoding="utf-8") as file:
        coverage = json.load(file)
    allowed = {entry["id"] for entries in coverage.values() for entry in entries}
    leagues = confirmed_competitions(
        read_csv(DATA / "competition_map.csv"), read_csv(DATA / "competition_overrides.csv"), allowed
    )
    player_map = {row["pitch_player_id"]: int(row["tm_player_id"]) for row in read_csv(DATA / "player_map.csv")}
    team_map = {(row["pitch_league_id"], row["pitch_team_id"]): row for row in read_csv(DATA / "team_map.csv")}

    rows = load_rows()
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    seen_fixtures = {(m["date"], m["home"], m["away"]) for m in state.values()}

    def resolve(row):
        row["tm_player_id"] = player_map.get(row["source_player_id"])
        team = team_map.get((row["pitch_league_id"], row["team_id"]))
        row["tm_club_id"] = team["tm_club_id"] if team else None
        return row

    unresolved_before = {id(row) for row in rows if row["tm_player_id"] is None}
    for row in rows:
        resolve(row)
    newly_resolved = sum(1 for row in rows if id(row) in unresolved_before and row["tm_player_id"] is not None)

    # Played matches per date across confirmed leagues (schedules always refreshed).
    by_date = defaultdict(list)
    skipped = Counter()
    for league in leagues:
        lid = safe_id(league["pitch_league_id"])
        found = {}
        for season in seasons_in_range(league["seasons"], args.start, args.end):
            path = f"/v1/leagues/{lid}/matches?season={quote(season, safe='')}"
            try:
                matches = client.get(path, refresh=True)["matches"]
            except PitchRequestError as error:
                print(f"Skipping league season: {error}", file=sys.stderr, flush=True)
                skipped[league["competition_id"]] += 1
                continue
            for match in matches:
                day = date.fromisoformat(match["date"])
                match_id = safe_id(match["id"])
                fixture = (match["date"], match["home_team"]["name"], match["away_team"]["name"])
                if (match.get("status") == "finished" and args.start <= day <= args.end
                        and match_id not in state and fixture not in seen_fixtures):
                    found[match_id] = match
        for match in found.values():
            by_date[match["date"]].append((league, match))
        print(f"{league['pitch_league_name']} ({league['competition_id']}): {len(found)} new played matches", flush=True)

    new_goals = Counter()
    for day in sorted(by_date):
        for league, match in by_date[day]:
            lid = safe_id(league["pitch_league_id"])
            match_id = safe_id(match["id"])
            path = f"/v1/matches/{match_id}/events"
            try:
                events = client.get(path, refresh=not settled(client, path, match))["events"]
            except PitchRequestError as error:
                print(f"Skipping match events (will retry next run): {error}", file=sys.stderr, flush=True)
                skipped[league["competition_id"]] += 1
                continue
            home, away = match["home_team"], match["away_team"]
            sides = {home["id"]: home["name"], away["id"]: away["name"]}
            goals = 0
            for event in events:
                if not is_goal_event(event) or goal_cell(event) is None:
                    continue
                if event.get("team_id") not in sides:
                    print(f"Goal team {event.get('team_id')} not in match {match_id}; skipped", file=sys.stderr)
                    continue
                player = event.get("player") or {}
                rows.append(resolve({
                    "date": date.fromisoformat(day), "match_id": match_id,
                    "home": home["name"], "away": away["name"],
                    "home_team_id": safe_id(home["id"]), "away_team_id": safe_id(away["id"]),
                    "competition_id": league["competition_id"], "pitch_league_id": lid,
                    "team_id": safe_id(event["team_id"]), "club_name": sides[event["team_id"]],
                    "tm_club_id": None, "source_player_id": safe_id(player["id"]) if player.get("id") else None,
                    "tm_player_id": None, "player_name": player.get("name") or "",
                    "minute": event["minute"], "minute_added": event.get("minute_added"),
                    "period": event.get("period"), "is_penalty": bool(event.get("is_penalty")),
                    "source": "pitchapi",
                }))
                goals += 1
            new_goals[league["competition_id"]] += goals
            state[match_id] = {"date": day, "home": home["name"], "away": away["name"],
                               "competition_id": league["competition_id"], "goals": goals}
            seen_fixtures.add((day, home["name"], away["name"]))
        save(rows, state)
        print(f"Saved {day}: {len(by_date[day])} matches", flush=True)
    if not by_date:
        save(rows, state)

    in_range = [row for row in rows if args.start <= row["date"] <= args.end]
    dropped = Counter(row["competition_id"] for row in in_range if row["tm_player_id"] is None)
    totals = Counter(row["competition_id"] for row in in_range)
    names = {league["competition_id"]: league["pitch_league_name"] for league in leagues}
    print(f"\n--- live goals {args.start} to {args.end} ---")
    for cid in sorted(totals, key=lambda c: -totals[c]):
        print(f"{names.get(cid, cid)} ({cid}): goals={totals[cid]}, new this run={new_goals[cid]}, "
              f"dropped for unmatched players={dropped[cid]}, skipped API resources={skipped[cid]}")
    print(f"Total goals stored: {len(in_range)}; usable (mapped player): {len(in_range) - sum(dropped.values())}; "
          f"dropped for unmatched players: {sum(dropped.values())}")
    print(f"Earlier unmatched goals now mapped: {newly_resolved}")
    latest = max((row["date"] for row in rows), default=None)
    print(f"Data up to: {latest}")

    unmatched = Counter((row["competition_id"], row["club_name"], row["source_player_id"], row["player_name"])
                        for row in in_range if row["tm_player_id"] is None)
    with UNMATCHED.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["competition_id", "team", "pitch_player_id", "player_name", "goals"])
        for (cid, team, pid, name), count in unmatched.most_common():
            writer.writerow([cid, team, pid or "", name, count])
    print(f"Unmatched scorers written to {UNMATCHED.relative_to(DATA.parent)} ({len(unmatched)} players)")

    print("\n--- 5 latest mapped goals (check one against a match report) ---")
    mapped = sorted((row for row in in_range if row["tm_player_id"] is not None),
                    key=lambda row: (row["date"], row["match_id"], row["minute"]))[-5:]
    for row in mapped:
        added = f"+{row['minute_added']}" if row["minute_added"] else ""
        print(f"{row['date']} {row['home']} v {row['away']} ({row['competition_id']}): {row['player_name']} "
              f"[tm {row['tm_player_id']}] {row['minute']}{added}'{' pen' if row['is_penalty'] else ''} "
              f"for {row['club_name']}")
    if any(skipped.values()):
        print("WARNING: some API resources were skipped; rerun to fill them in.")


if __name__ == "__main__":
    try:
        with create_session() as session:
            main(CachedPitchClient(session, DATA / "cache"))
    except (RuntimeError, ValueError, OSError, KeyError, duckdb.Error) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
