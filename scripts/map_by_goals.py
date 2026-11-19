#!/usr/bin/env python3
"""Map unmapped PitchAPI scorers to Transfermarkt players by their goals.

Both sources overlap until Transfermarkt's last day (2026-07-06). A PitchAPI
scorer is mapped when their goals coincide with one Transfermarkt player's
goals: same competition, date within one day, same regular/extra-time half,
minute cell within one. Acceptance (never a guess):
  - 2+ goals: at least 2 coincide, the best player covers >= 80% of the
    scorer's goals, and no other player coincides with more than a third of
    the best player's hits;
  - 1 goal: the minute is identical, it is the only candidate, and the names
    share a normalized token.
When the scorer's PitchAPI team is already mapped (data/team_map.csv), only
goals for that Transfermarkt club are candidates (same match). Rerun after a
run that mapped new teams to resolve more players.
Everything else goes to data/unmatched_fingerprint.csv for review.
PitchAPI teams are then mapped to the club most of their mapped scorers'
goals were for. Existing mappings are never changed.
"""

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from urllib.parse import quote

import duckdb

if __package__:
    from .map_pitchapi import DATA, DATABASE, append_csv, read_csv, seasons_in_range
    from .mapping_rules import confirmed_competitions, name_tokens
    from .fingerprint_rules import coincides, fingerprint
    from .pitch_cache import CachedPitchClient, PitchRequestError
    from .pitch_goals import goal_cell
    from .probe_pitchapi import ROOT, create_session, is_goal_event, safe_id
else:
    from map_pitchapi import DATA, DATABASE, append_csv, read_csv, seasons_in_range
    from mapping_rules import confirmed_competitions, name_tokens
    from fingerprint_rules import coincides, fingerprint
    from pitch_cache import CachedPitchClient, PitchRequestError
    from pitch_goals import goal_cell
    from probe_pitchapi import ROOT, create_session, is_goal_event, safe_id


PARQUET = ROOT.parent / "footy-pipeline" / "goals_grid.parquet"
TM_LAST_DAY = date(2026, 7, 6)
REVIEW_FIELDS = [
    "pitch_league_id", "league", "pitch_team_id", "team", "pitch_player_id", "player_name",
    "pitch_goals", "best_tm_player_id", "best_tm_name", "best_hits", "runner_up_tm_player_id",
    "runner_up_hits", "reason",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2025, 7, 1),
                        help="first match day to fingerprint (default 2025-07-01, already cached)")
    args = parser.parse_args()
    end = TM_LAST_DAY
    if args.start > end:
        raise ValueError(f"--start must be on or before {end}")

    with (DATA / "coverage.json").open(encoding="utf-8") as file:
        coverage = json.load(file)
    allowed = {entry["id"] for entries in coverage.values() for entry in entries}
    leagues = confirmed_competitions(
        read_csv(DATA / "competition_map.csv"), read_csv(DATA / "competition_overrides.csv"), allowed
    )
    player_map = {row["pitch_player_id"]: row for row in read_csv(DATA / "player_map.csv")}
    team_clubs = {}
    for row in read_csv(DATA / "team_map.csv"):
        team_clubs[(row["pitch_league_id"], row["pitch_team_id"])] = row["tm_club_id"]
    team_map = set(team_clubs)

    competition_ids = sorted({league["competition_id"] for league in leagues})
    with duckdb.connect(str(DATABASE), read_only=True) as con:
        rows = con.execute(f"""
            SELECT g.player_id, g.club_id, g.date, g.minute, g.is_extra_time, gm.competition_id
            FROM '{str(PARQUET).replace(chr(92), "/")}' g
            JOIN games gm ON g.game_id = gm.game_id
            WHERE gm.competition_id IN ({",".join("?" * len(competition_ids))})
              AND g.date BETWEEN ? AND ?
        """, [*competition_ids, args.start - timedelta(days=1), end + timedelta(days=1)]).fetchall()
        tm_names = {int(pid): name for pid, name in con.execute("SELECT player_id, name FROM players").fetchall()}
        club_names = {}
        for cid, name in con.execute(
            "SELECT home_club_id, home_club_name FROM games UNION SELECT away_club_id, away_club_name FROM games"
        ).fetchall():
            if cid is not None and name:
                club_names[str(cid)] = name
    tm_by_day = defaultdict(list)
    for pid, club_id, day, minute, extra, cid in rows:
        tm_by_day[(cid, day)].append({
            "player_id": int(pid), "club_id": str(club_id), "date": day,
            "cell": minute if minute and minute >= 1 else None, "extra": bool(extra),
        })
    print(f"Transfermarkt goals loaded: {len(rows):,} ({args.start} to {end})", flush=True)

    # PitchAPI goals per (league, team, player), from cached responses where possible.
    pitch = defaultdict(list)
    meta = {}
    skipped = 0
    with create_session() as session:
        client = CachedPitchClient(session, DATA / "cache")
        for league in leagues:
            lid = safe_id(league["pitch_league_id"])
            seen_matches = set()
            for season in seasons_in_range(league["seasons"], args.start, end):
                try:
                    matches = client.get(f"/v1/leagues/{lid}/matches?season={quote(season, safe='')}")["matches"]
                except PitchRequestError as error:
                    print(f"Skipping league season: {error}", file=sys.stderr, flush=True)
                    skipped += 1
                    continue
                for match in matches:
                    day = date.fromisoformat(match["date"])
                    match_id = safe_id(match["id"])
                    if match.get("status") != "finished" or not args.start <= day <= end or match_id in seen_matches:
                        continue
                    seen_matches.add(match_id)
                    try:
                        events = client.get(f"/v1/matches/{match_id}/events")["events"]
                    except PitchRequestError as error:
                        print(f"Skipping match events: {error}", file=sys.stderr, flush=True)
                        skipped += 1
                        continue
                    sides = {team["id"]: team["name"] for team in (match["home_team"], match["away_team"])}
                    for event in events:
                        if not is_goal_event(event):
                            continue
                        cell = goal_cell(event)
                        player = event.get("player") or {}
                        if cell is None or not player.get("id") or event.get("team_id") not in sides:
                            continue
                        team_id, pid = safe_id(event["team_id"]), safe_id(player["id"])
                        key = (lid, team_id, pid)
                        pitch[key].append({
                            "date": day, "cell": cell[0], "extra": cell[1],
                            "competition_id": league["competition_id"],
                            "club": team_clubs.get((lid, team_id)),
                        })
                        meta[key] = {"league": league["pitch_league_name"], "team": sides[event["team_id"]],
                                     "name": player.get("name") or ""}
            print(f"PitchAPI {league['pitch_league_name']} ({league['competition_id']}): "
                  f"{len(seen_matches)} matches", flush=True)

    # A scorer's goals across all leagues/teams form one fingerprint.
    goals_by_player = defaultdict(list)
    keys_by_player = defaultdict(list)
    for key, goals in pitch.items():
        goals_by_player[key[2]].extend(goals)
        keys_by_player[key[2]].append(key)

    tm_to_pitch = defaultdict(set)
    for pid, row in player_map.items():
        tm_to_pitch[int(row["tm_player_id"])].add(pid)
    new_rows, review = [], []
    accepted = {}
    for pid in sorted(goals_by_player):
        if pid in player_map:
            continue
        first = keys_by_player[pid][0]
        name = meta[first]["name"]
        target, reason, best, best_hits, runner, runner_hits = fingerprint(
            goals_by_player[pid], tm_by_day, name, tm_names)
        if target is not None:
            accepted[pid] = (target, reason, best_hits, runner, runner_hits)
            continue
        for key in keys_by_player[pid]:
            review.append(review_row(key, meta[key], len(goals_by_player[pid]), best, tm_names, best_hits,
                                     runner, runner_hits, reason))

    # One Transfermarkt player may legitimately have two PitchAPI ids (ids changed
    # in September), but only when the names agree; otherwise send all to review.
    targets = defaultdict(set)
    for pid, (target, *_rest) in accepted.items():
        targets[target].add(pid)
    for target, pids in targets.items():
        all_pids = pids | tm_to_pitch.get(target, set())
        names = {name_tokens(meta[keys_by_player[p][0]]["name"]) if p in keys_by_player
                 else name_tokens(player_map[p]["player_name"]) for p in all_pids}
        if len(names) > 1:
            for pid in pids:
                _t, _r, best_hits, runner, runner_hits = accepted.pop(pid)
                for key in keys_by_player[pid]:
                    review.append(review_row(key, meta[key], len(goals_by_player[pid]), target, tm_names,
                                             best_hits, runner, runner_hits,
                                             "another PitchAPI player with a different name maps to this player"))
    for pid, (target, _reason, *_rest) in sorted(accepted.items()):
        new_rows.append({"pitch_player_id": pid, "tm_player_id": target,
                         "player_name": meta[keys_by_player[pid][0]]["name"]})

    # Teams: club most mapped scorers' coinciding goals were for.
    mapped = {pid: int(row["tm_player_id"]) for pid, row in player_map.items()}
    mapped.update({pid: target for pid, (target, *_rest) in accepted.items()})
    team_votes = defaultdict(Counter)
    for (lid, team_id, pid), goals in pitch.items():
        tm_id = mapped.get(pid)
        if tm_id is None:
            continue
        for goal in goals:
            club = next((
                tm["club_id"]
                for offset in (-1, 0, 1)
                for tm in tm_by_day.get((goal["competition_id"], goal["date"] + timedelta(days=offset)), ())
                if tm["player_id"] == tm_id and coincides(goal, tm)
            ), None)
            if club is not None:
                team_votes[(lid, team_id)][club] += 1
    league_by_id = {safe_id(league["pitch_league_id"]): league for league in leagues}
    team_names = {(key[0], key[1]): meta[key]["team"] for key in pitch}
    team_rows = []
    for (lid, team_id), votes in sorted(team_votes.items()):
        if (lid, team_id) in team_map:
            continue
        club_id, count = votes.most_common(1)[0]
        if count >= 3 and count >= 0.8 * sum(votes.values()):
            league = league_by_id[lid]
            team_rows.append({
                "pitch_league_id": lid, "league": league["pitch_league_name"],
                "competition_id": league["competition_id"], "pitch_team_id": team_id,
                "pitch_team_name": team_names[(lid, team_id)], "tm_club_id": club_id,
                "tm_club_name": club_names.get(club_id, ""),
            })

    append_csv(DATA / "player_map.csv", ["pitch_player_id", "tm_player_id", "player_name"], new_rows, ["pitch_player_id"])
    append_csv(DATA / "team_map.csv", ["pitch_league_id", "league", "competition_id", "pitch_team_id",
                                       "pitch_team_name", "tm_club_id", "tm_club_name"],
               team_rows, ["pitch_league_id", "pitch_team_id"])
    with (DATA / "unmatched_fingerprint.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(review)

    print("\n--- per-league summary (goals from", args.start, "to", end, ") ---")
    new_ids = set(accepted)
    for league in leagues:
        lid = safe_id(league["pitch_league_id"])
        keys = [key for key in pitch if key[0] == lid]
        goals = sum(len(pitch[key]) for key in keys)
        before = sum(len(pitch[key]) for key in keys if key[2] in player_map)
        after = sum(len(pitch[key]) for key in keys if key[2] in player_map or key[2] in new_ids)
        pct = lambda n: f"{100 * n / goals:.1f}%" if goals else "n/a"
        print(f"{league['pitch_league_name']} ({league['competition_id']}): scorers={len({k[2] for k in keys})}, "
              f"goals={goals}, mapped goals before={before} ({pct(before)}), after={after} ({pct(after)})")
    reasons = Counter(row["reason"] for row in review)
    print(f"\nPlayers newly mapped: {len(new_rows)}")
    print(f"Teams newly mapped: {len(team_rows)}")
    print(f"Players left for review: {len({row['pitch_player_id'] for row in review})} "
          f"(data/unmatched_fingerprint.csv)")
    for reason, count in reasons.most_common():
        print(f"  {reason}: {count}")
    print(f"Players created: 0 (fingerprinting only maps to existing Transfermarkt players)")
    if skipped:
        print(f"WARNING: {skipped} API resources were skipped; rerun to retry them.")


def review_row(key, meta, total, best, tm_names, best_hits, runner, runner_hits, reason):
    return {
        "pitch_league_id": key[0], "league": meta["league"], "pitch_team_id": key[1], "team": meta["team"],
        "pitch_player_id": key[2], "player_name": meta["name"], "pitch_goals": total,
        "best_tm_player_id": best or "", "best_tm_name": tm_names.get(best, "") if best else "",
        "best_hits": best_hits, "runner_up_tm_player_id": runner or "", "runner_up_hits": runner_hits,
        "reason": reason,
    }


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError, KeyError, duckdb.Error) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
