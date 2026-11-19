#!/usr/bin/env python3
"""Map PitchAPI teams and goalscorers conservatively for review."""

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import date
from urllib.parse import quote

import duckdb

if __package__:
    from .mapping_rules import confirmed_competitions, goal_coverage, match_player, match_player_without_profile, roster_team_match
    from .probe_pitchapi import ROOT, create_session, is_goal_event, safe_id
    from .pitch_cache import CachedPitchClient, PitchRequestError
else:
    from mapping_rules import confirmed_competitions, goal_coverage, match_player, match_player_without_profile, roster_team_match
    from probe_pitchapi import ROOT, create_session, is_goal_event, safe_id
    from pitch_cache import CachedPitchClient, PitchRequestError


DATABASE = ROOT.parent / "footy-pipeline" / "transfermarkt-datasets.duckdb"
DATA = ROOT / "data"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def append_csv(path, fields, rows, key_fields):
    existing = read_csv(path) if path.exists() else []
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as file:
            current_fields = csv.DictReader(file).fieldnames
        if current_fields != fields:
            raise ValueError(f"Unexpected columns in existing file: {path}")
    keys = {tuple(str(row[field]) for field in key_fields) for row in existing}
    pending = []
    for row in rows:
        key = tuple(str(row[field]) for field in key_fields)
        if key not in keys:
            pending.append(row)
            keys.add(key)
    with path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        if not existing and file.tell() == 0:
            writer.writeheader()
        writer.writerows(pending)


def seasons_in_range(raw, start, end):
    seasons = json.loads(raw)
    if not isinstance(seasons, list):
        raise ValueError("Invalid seasons in competition map")
    result = []
    for season in seasons:
        years = [int(year) for year in re.findall(r"(?:19|20)\d{2}", season)]
        if not years:
            raise ValueError(f"Unrecognized season: {season}")
        if min(years) <= end.year and max(years) + 1 >= start.year:
            result.append(season)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2025, 7, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    if args.end < args.start:
        raise ValueError("End date must not precede start date")
    paths = [DATA / name for name in (
        "team_map.csv", "unmatched_teams.csv", "player_map.csv", "unmatched.csv", "unavailable_profiles.csv"
    )]
    old_teams = read_csv(paths[0]) if paths[0].exists() else []
    old_unmatched_teams = read_csv(paths[1]) if paths[1].exists() else []
    old_players = read_csv(paths[2]) if paths[2].exists() else []
    old_unmatched = read_csv(paths[3]) if paths[3].exists() else []
    old_unavailable = read_csv(paths[4]) if paths[4].exists() else []
    saved_teams = {}
    for row in old_teams:
        key = (row["pitch_league_id"], row["pitch_team_id"])
        if key in saved_teams and saved_teams[key]["tm_club_id"] != row["tm_club_id"]:
            raise ValueError(f"Conflicting existing team mappings: {key}")
        saved_teams[key] = row
    saved_players = {}
    for row in old_players:
        pid = row["pitch_player_id"]
        if pid in saved_players and saved_players[pid]["tm_player_id"] != row["tm_player_id"]:
            raise ValueError(f"Conflicting existing player mappings: {pid}")
        saved_players[pid] = row

    with (DATA / "coverage.json").open(encoding="utf-8") as file:
        coverage = json.load(file)
    allowed = {entry["id"] for entries in coverage.values() for entry in entries}
    cross_competitions = {entry["id"] for group in ("uefa", "international") for entry in coverage[group]}
    leagues = confirmed_competitions(
        read_csv(DATA / "competition_map.csv"), read_csv(DATA / "competition_overrides.csv"), allowed
    )
    if not leagues:
        raise RuntimeError("No confirmed competitions to map")

    with duckdb.connect(str(DATABASE), read_only=True) as con:
        players = [
            {"id": pid, "name": name, "club_id": str(club_id)}
            for pid, name, club_id in con.execute(
                "SELECT player_id, name, current_club_id FROM players WHERE name IS NOT NULL AND current_club_id IS NOT NULL"
            ).fetchall()
        ]
        league_clubs = {}
        for league in leagues:
            competition_id = league["competition_id"]
            rows = con.execute("""
                SELECT DISTINCT home_club_id, home_club_name FROM games WHERE competition_id = ?
                UNION
                SELECT DISTINCT away_club_id, away_club_name FROM games WHERE competition_id = ?
            """, [competition_id, competition_id]).fetchall()
            clubs = [{"id": str(cid), "name": name} for cid, name in rows if cid is not None and name]
            league_clubs[league["pitch_league_id"]] = clubs

    # An observation is scoped to a league and team; conflicting identities
    # across observations are rejected before the global player map is written.
    matches_by_league = {}
    team_rows, unmatched_teams, team_ids = [], [], {}
    unavailable = []
    unavailable_by_league = defaultdict(set)
    for row in old_unavailable:
        unavailable_by_league[row["pitch_league_id"]].add(row["pitch_player_id"])
    skipped_resources = defaultdict(int)
    profiles, failed_profiles = {}, {}
    events_by_match = {}
    report_goals = []
    with create_session() as session:
        client = CachedPitchClient(session, DATA / "cache")
        for league in leagues:
            lid = safe_id(league["pitch_league_id"])
            matches = {}
            for season in seasons_in_range(league["seasons"], args.start, args.end):
                path = f"/v1/leagues/{lid}/matches?season={quote(season, safe='')}"
                try:
                    season_data = client.get(path)
                except PitchRequestError as error:
                    print(f"Skipping league season: {error}", file=sys.stderr, flush=True)
                    skipped_resources[lid] += 1
                    continue
                for match in season_data["matches"]:
                    match_day = date.fromisoformat(match["date"])
                    if args.start <= match_day <= args.end:
                        matches[(safe_id(match["id"]), match_day)] = match
            matches_by_league[lid] = list(matches.values())
            teams = defaultdict(set)
            for match in matches.values():
                for side in ("home_team", "away_team"):
                    team = match[side]
                    teams[safe_id(team["id"])].add(team["name"])
            clubs = league_clubs[lid]
            team_scorers = defaultdict(set)
            for match in matches.values():
                match_id = safe_id(match["id"])
                try:
                    events = client.get(f"/v1/matches/{match_id}/events")["events"]
                except PitchRequestError as error:
                    print(f"Skipping match events: {error}", file=sys.stderr, flush=True)
                    skipped_resources[lid] += 1
                    continue
                events_by_match[(lid, match_id, match["date"])] = events
                sides = {team["id"]: team["name"] for team in (match["home_team"], match["away_team"])}
                for event in events:
                    if not is_goal_event(event) or event["is_own_goal"]:
                        continue
                    team_id = event.get("team_id")
                    player = event.get("player") or {}
                    pid = player.get("id")
                    name = player.get("name") or ""
                    if date.fromisoformat(match["date"]) >= date(2026, 7, 7):
                        report_goals.append({"league_id": lid, "league": league["pitch_league_name"],
                                             "team_id": team_id, "team": sides.get(team_id, "Unknown team"),
                                             "player_id": pid, "name": name or "Unknown scorer"})
                    if league["competition_id"] in cross_competitions or not pid or team_id not in sides:
                        continue
                    pid = safe_id(pid)
                    if pid not in profiles and pid not in failed_profiles:
                        try:
                            profiles[pid] = client.get(f"/v1/players/{pid}", skip_unavailable_profile=True)
                        except PitchRequestError as error:
                            print(f"Skipping player profile: {error}", file=sys.stderr, flush=True)
                            failed_profiles[pid] = str(error)
                    profile = profiles.get(pid)
                    if pid not in failed_profiles:
                        team_scorers[team_id].add(profile["name"] if profile is not None else name)
                    if profile is None and pid not in failed_profiles:
                        unavailable_by_league[lid].add(pid)
                        unavailable.append({"pitch_league_id": lid, "league": league["pitch_league_name"],
                                            "pitch_team_id": team_id, "team": sides[team_id],
                                            "pitch_player_id": pid, "player_name": name,
                                            "nationality_status": "no nationality"})
            if league["competition_id"] in cross_competitions:
                print(f"Competition: {league['pitch_league_name']} — player-map resolution only", flush=True)
                continue
            for team_id, names in sorted(teams.items()):
                key = (lid, team_id)
                club_id, top, second = roster_team_match(names, team_scorers[team_id], clubs, players)
                row = {
                    "pitch_league_id": lid, "league": league["pitch_league_name"],
                    "competition_id": league["competition_id"], "pitch_team_id": team_id,
                    "pitch_team_name": " | ".join(sorted(names)),
                }
                if key in saved_teams and club_id and (
                    saved_teams[key]["tm_club_id"] != club_id
                    or saved_teams[key]["competition_id"] != league["competition_id"]
                ):
                    print(f"Team mapping conflict for {lid}/{team_id}; existing mapping retained for review", file=sys.stderr)
                    club_id = None
                if club_id:
                    team_ids[(lid, team_id)] = club_id
                    club_name = sorted(club["name"] for club in clubs if club["id"] == club_id)[0]
                    team_rows.append({**row, "tm_club_id": club_id, "tm_club_name": club_name})
                else:
                    unmatched_teams.append({**row, "reason": f"roster overlap {top}, runner-up {second}"})
            print(f"Teams: {league['pitch_league_name']} — {len(teams)} observed, {len(matches)} matches", flush=True)

        observations = {}
        for league in leagues:
            lid = league["pitch_league_id"]
            if league["competition_id"] in cross_competitions:
                continue
            clubs = {club["id"] for club in league_clubs[lid]}
            clubs.update(club_id for (league_id, _), club_id in team_ids.items() if league_id == lid)
            league_players = [player for player in players if player["club_id"] in clubs]
            for match in matches_by_league[lid]:
                match_id = safe_id(match["id"])
                events = events_by_match.get((lid, match_id, match["date"]))
                if events is None:
                    continue
                sides = {team["id"]: team["name"] for team in (match["home_team"], match["away_team"])}
                for event in events:
                    if not is_goal_event(event) or event["is_own_goal"]:
                        continue
                    team_id = event.get("team_id")
                    if team_id not in sides:
                        print(f"Goal team {team_id} is not in match {match_id}; left unmatched", file=sys.stderr)
                        continue
                    team_id = safe_id(team_id)
                    player = event.get("player") or {}
                    if not player.get("id"):
                        print(f"Goal in match {match_id} has no player ID; left unmatched", file=sys.stderr)
                        continue
                    pid = safe_id(player["id"])
                    key = (lid, team_id, pid)
                    if key in observations:
                        continue
                    if pid not in profiles and pid not in failed_profiles:
                        try:
                            profiles[pid] = client.get(f"/v1/players/{pid}", skip_unavailable_profile=True)
                        except PitchRequestError as error:
                            print(f"Skipping player profile: {error}", file=sys.stderr, flush=True)
                            failed_profiles[pid] = str(error)
                    profile = profiles.get(pid)
                    name = profile["name"] if profile is not None else (player.get("name") or "")
                    club_id = team_ids.get((lid, team_id))
                    if pid in failed_profiles:
                        target, reason = None, f"profile request failed: {failed_profiles[pid]}"
                    elif profile is None:
                        unavailable_by_league[lid].add(pid)
                        unavailable.append({
                            "pitch_league_id": lid, "league": league["pitch_league_name"],
                            "pitch_team_id": team_id, "team": sides[team_id], "pitch_player_id": pid,
                            "player_name": name, "nationality_status": "no nationality",
                        })
                        target, reason = match_player_without_profile(name, club_id, league_players) if club_id else (None, "no nationality; unmatched team")
                    else:
                        target, reason = match_player(name, club_id, {club_id}, league_players) if club_id else (None, "unmatched team")
                    observations[key] = {
                        "pitch_league_id": lid, "league": league["pitch_league_name"],
                        "pitch_team_id": team_id, "team": sides[team_id], "pitch_player_id": pid,
                        "player_name": name, "tm_player_id": target, "reason": reason,
                    }
            print(f"Players: {league['pitch_league_name']} — processed {len(matches_by_league[lid])} matches", flush=True)

    by_player = defaultdict(list)
    for observation in observations.values():
        by_player[observation["pitch_player_id"]].append(observation)
    player_rows, unmatched = [], []
    verified_players, conflicts = {}, set()
    for pid, entries in sorted(by_player.items()):
        targets = {entry["tm_player_id"] for entry in entries}
        if pid in saved_players and any(
            target is not None and str(target) != saved_players[pid]["tm_player_id"] for target in targets
        ):
            conflicts.add(pid)
            print(f"Player mapping conflict for {pid}; existing mapping retained for review", file=sys.stderr)
            unmatched.extend({**entry, "reason": "conflicting player mapping"} for entry in entries)
            continue
        if len(targets) == 1 and None not in targets:
            verified_players[pid] = next(iter(targets))
            if pid not in saved_players:
                player_rows.append({"pitch_player_id": pid, "tm_player_id": verified_players[pid], "player_name": entries[0]["player_name"]})
        else:
            for entry in entries:
                unmatched.append({**entry, "reason": entry["reason"] if entry["tm_player_id"] is None else "conflicting player contexts"})
    team_fields = ["pitch_league_id", "league", "competition_id", "pitch_team_id", "pitch_team_name"]
    player_fields = ["pitch_league_id", "league", "pitch_team_id", "team", "pitch_player_id", "player_name", "tm_player_id", "reason"]
    append_csv(paths[0], team_fields + ["tm_club_id", "tm_club_name"], team_rows, ["pitch_league_id", "pitch_team_id"])
    append_csv(paths[1], team_fields + ["reason"], unmatched_teams, ["pitch_league_id", "pitch_team_id"])
    append_csv(paths[2], ["pitch_player_id", "tm_player_id", "player_name"], player_rows, ["pitch_player_id"])
    append_csv(paths[3], player_fields, unmatched, ["pitch_league_id", "pitch_team_id", "pitch_player_id"])
    append_csv(paths[4], ["pitch_league_id", "league", "pitch_team_id", "team", "pitch_player_id", "player_name", "nationality_status"],
               unavailable, ["pitch_league_id", "pitch_team_id", "pitch_player_id"])
    mapped_ids = set(verified_players)
    cross_leagues = {league["pitch_league_id"] for league in leagues if league["competition_id"] in cross_competitions}
    for goal in report_goals:
        profile = profiles.get(goal["player_id"])
        if profile and profile.get("name"):
            goal["name"] = profile["name"]
    totals, unmatched_goals = goal_coverage(report_goals, cross_leagues, mapped_ids, set(saved_players), conflicts)
    print("\nCoverage uses cached league schedules; current-season schedules may be stale.")
    print("\n--- per-league summary ---")
    for league in leagues:
        lid = league["pitch_league_id"]
        obs = [row for row in observations.values() if row["pitch_league_id"] == lid]
        total_goals, matched_goals = totals.get(lid, (0, 0))
        percent = f"{100 * matched_goals / total_goals:.1f}%" if total_goals else "n/a"
        print(f"{league['pitch_league_name']}: teams matched={sum(key[0] == lid for key in team_ids)}, "
              f"teams unmatched={sum(row['pitch_league_id'] == lid for row in unmatched_teams)}, "
              f"players matched={len({row['pitch_player_id'] for row in obs if row['pitch_player_id'] in mapped_ids})}, "
              f"players unmatched={len({row['pitch_player_id'] for row in obs if row['pitch_player_id'] not in mapped_ids})}, "
              f"unavailable profiles={len(unavailable_by_league[lid])}, skipped API resources={skipped_resources[lid]}, "
              f"goals since 2026-07-07={total_goals}, matched goals={matched_goals}, coverage={percent}")
    matched_observed = len(set(by_player) & mapped_ids)
    print(f"Total: teams matched={len(team_ids)}, players matched={matched_observed}, "
          f"players created=0, unmatched players={len(by_player) - matched_observed}")
    print("\n--- top 25 unmatched scorers by goals ---")
    for (_identity, team, league), (name, count) in sorted(
        unmatched_goals.items(), key=lambda item: (-item[1][1], item[0][2], item[0][1], item[1][0])
    )[:25]:
        print(f"{name} | {team} | {league} | {count} goals")
    if args.start > date(2026, 7, 7) or args.end < date.today() or any(skipped_resources.values()):
        print("WARNING: Goal coverage is partial because the date range is limited or API resources were skipped.")
    print(f"Reep not used; mapping covers observed goalscorers from {args.start} through {args.end}.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError, KeyError, duckdb.Error) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
