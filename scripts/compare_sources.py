#!/usr/bin/env python3
"""Compare PitchAPI and Transfermarkt goals for the 2025/2026 big-five top flights.

Reports counts only; it does not decide pass or fail.
"""

import argparse
import csv
import sys
from collections import defaultdict
from datetime import date
from urllib.parse import quote

import duckdb

if __package__:
    from .pitch_cache import CachedPitchClient, PitchRequestError
    from .pitch_goals import goal_cell
    from .probe_pitchapi import ROOT, create_session, is_goal_event, safe_id
else:
    from pitch_cache import CachedPitchClient, PitchRequestError
    from pitch_goals import goal_cell
    from probe_pitchapi import ROOT, create_session, is_goal_event, safe_id


DATA = ROOT / "data"
PIPELINE = ROOT.parent / "footy-pipeline"
DATABASE = PIPELINE / "transfermarkt-datasets.duckdb"
PARQUET = PIPELINE / "goals_grid.parquet"
COMPETITIONS = ("GB1", "ES1", "L1", "IT1", "FR1")
SEASON = "2025/2026"
SEASON_START, SEASON_END = date(2025, 7, 1), date(2026, 6, 30)
DIFF_FIELDS = [
    "kind", "tm_player_id", "player_name", "competition_id", "tm_date", "pitch_date",
    "tm_minute", "tm_extra", "pitch_minute", "pitch_minute_added", "pitch_cell", "pitch_extra",
    "minute_diff", "tm_game_id", "pitch_match_id", "pitch_player_id",
]


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def pair_goals(tm_goals, pitch_goals):
    """Pair one player's goals by date (within one day), closest minute first.

    Returns (pairs, tm_only, pitch_only). Each goal is a dict with
    "date" (date), "cell" (int or None) and "extra" (bool).
    """
    candidates = []
    for i, tm in enumerate(tm_goals):
        for j, pa in enumerate(pitch_goals):
            days = abs((tm["date"] - pa["date"]).days)
            if days > 1:
                continue
            if tm["cell"] is None:
                minute_gap = 10_000
            else:
                minute_gap = abs(tm["cell"] - pa["cell"]) + (0 if tm["extra"] == pa["extra"] else 1000)
            candidates.append((minute_gap, days, i, j))
    candidates.sort()
    used_tm, used_pa, pairs = set(), set(), []
    for _gap, _days, i, j in candidates:
        if i in used_tm or j in used_pa:
            continue
        used_tm.add(i)
        used_pa.add(j)
        pairs.append((tm_goals[i], pitch_goals[j]))
    tm_only = [goal for i, goal in enumerate(tm_goals) if i not in used_tm]
    pitch_only = [goal for j, goal in enumerate(pitch_goals) if j not in used_pa]
    return pairs, tm_only, pitch_only


def classify(tm, pa):
    if tm["cell"] is None:
        return "tm_minute_unknown", None
    if tm["extra"] != pa["extra"]:
        return "off_by_more", abs(tm["cell"] - pa["cell"])
    diff = abs(tm["cell"] - pa["cell"])
    return ("exact" if diff == 0 else "off_by_1" if diff == 1 else "off_by_more"), diff


def load_pitch_goals(client, leagues, player_map):
    goals_by_player = defaultdict(list)
    totals = defaultdict(int)
    unmapped = defaultdict(int)
    skipped = defaultdict(int)
    for league in leagues:
        lid = safe_id(league["pitch_league_id"])
        cid = league["competition_id"]
        try:
            matches = client.get(f"/v1/leagues/{lid}/matches?season={quote(SEASON, safe='')}")["matches"]
        except PitchRequestError as error:
            print(f"Skipping {cid} schedule: {error}", file=sys.stderr, flush=True)
            skipped[cid] += 1
            continue
        played = [m for m in matches if m.get("status") == "finished"]
        for match in played:
            match_id = safe_id(match["id"])
            try:
                events = client.get(f"/v1/matches/{match_id}/events")["events"]
            except PitchRequestError as error:
                print(f"Skipping match events: {error}", file=sys.stderr, flush=True)
                skipped[cid] += 1
                continue
            for event in events:
                if not is_goal_event(event):
                    continue
                cell = goal_cell(event)
                if cell is None:
                    continue
                totals[cid] += 1
                pid = (event.get("player") or {}).get("id")
                tm_id = player_map.get(safe_id(pid)) if pid else None
                if tm_id is None:
                    unmapped[cid] += 1
                    continue
                goals_by_player[tm_id].append({
                    "date": date.fromisoformat(match["date"]), "cell": cell[0], "extra": cell[1],
                    "minute": event["minute"], "minute_added": event.get("minute_added"),
                    "match_id": match_id, "pitch_player_id": pid, "competition_id": cid,
                })
        print(f"PitchAPI {cid}: {len(played)} finished matches, {totals[cid]} goals "
              f"({unmapped[cid]} by unmapped players)", flush=True)
    return goals_by_player, totals, unmapped, skipped


def load_tm_goals():
    with duckdb.connect(str(DATABASE), read_only=True) as con:
        rows = con.execute(f"""
            SELECT g.player_id, g.date, g.minute, g.is_extra_time, g.game_id, gm.competition_id
            FROM '{str(PARQUET).replace(chr(92), "/")}' g
            JOIN games gm ON g.game_id = gm.game_id
            WHERE gm.competition_id IN ({",".join("?" * len(COMPETITIONS))})
              AND g.date BETWEEN ? AND ?
        """, [*COMPETITIONS, SEASON_START, SEASON_END]).fetchall()
        names = dict(con.execute("SELECT player_id, name FROM players").fetchall())
    goals = defaultdict(list)
    totals = defaultdict(int)
    for pid, day, minute, extra, game_id, cid in rows:
        totals[cid] += 1
        goals[int(pid)].append({
            "date": day, "cell": minute if minute and minute >= 1 else None,
            "extra": bool(extra), "game_id": game_id, "competition_id": cid,
        })
    return goals, totals, {int(k): v for k, v in names.items()}


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    overrides = {row["competition_id"].strip(): row for row in read_csv(DATA / "competition_overrides.csv")}
    missing = [cid for cid in COMPETITIONS if cid not in overrides]
    if missing:
        raise RuntimeError(f"No confirmed PitchAPI league for: {', '.join(missing)}")
    leagues = [{"pitch_league_id": overrides[cid]["pitch_league_id"], "competition_id": cid} for cid in COMPETITIONS]
    player_map = {row["pitch_player_id"]: int(row["tm_player_id"]) for row in read_csv(DATA / "player_map.csv")}
    mapped_tm = set(player_map.values())

    tm_goals, tm_totals, names = load_tm_goals()
    with create_session() as session:
        client = CachedPitchClient(session, DATA / "cache")
        pa_goals, pa_totals, pa_unmapped, skipped = load_pitch_goals(client, leagues, player_map)

    counts = defaultdict(int)
    diffs = []
    tm_unmapped_goals = 0
    for pid in sorted(set(tm_goals) | set(pa_goals)):
        if pid not in mapped_tm:
            tm_unmapped_goals += len(tm_goals.get(pid, []))
            continue
        pairs, tm_only, pa_only = pair_goals(tm_goals.get(pid, []), pa_goals.get(pid, []))
        name = names.get(pid, f"Player {pid}")
        for tm, pa in pairs:
            kind, diff = classify(tm, pa)
            counts[kind] += 1
            if kind != "exact":
                diffs.append(row(kind, pid, name, tm, pa, diff))
        for tm in tm_only:
            counts["tm_only"] += 1
            diffs.append(row("tm_only", pid, name, tm, None, None))
        for pa in pa_only:
            counts["pitch_only"] += 1
            diffs.append(row("pitch_only", pid, name, None, pa, None))

    with (DATA / "overlap_diffs.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=DIFF_FIELDS)
        writer.writeheader()
        writer.writerows(diffs)

    print(f"\n--- overlap {SEASON}: {', '.join(COMPETITIONS)} (45+/90+ merged) ---")
    for cid in COMPETITIONS:
        print(f"{cid}: Transfermarkt goals={tm_totals[cid]}, PitchAPI goals={pa_totals[cid]}, "
              f"PitchAPI goals by unmapped players={pa_unmapped[cid]}, skipped API resources={skipped[cid]}")
    print(f"Goals in Transfermarkt: {sum(tm_totals.values())}")
    print(f"Goals in PitchAPI: {sum(pa_totals.values())}")
    print(f"  excluded from comparison: Transfermarkt goals by players with no PitchAPI mapping={tm_unmapped_goals}, "
          f"PitchAPI goals by unmapped players={sum(pa_unmapped.values())}")
    print(f"Exact matches: {counts['exact']}")
    print(f"Minutes off by 1: {counts['off_by_1']}")
    print(f"Minutes off by more (incl. regular vs extra time): {counts['off_by_more']}")
    print(f"Paired but Transfermarkt minute unknown: {counts['tm_minute_unknown']}")
    print(f"Transfermarkt-only: {counts['tm_only']}")
    print(f"PitchAPI-only: {counts['pitch_only']}")
    print(f"Wrote {len(diffs)} disagreements to data/overlap_diffs.csv")

    print("\n--- 20 largest minute disagreements ---")
    paired = sorted((d for d in diffs if d["minute_diff"] != ""), key=lambda d: -int(d["minute_diff"]))
    for d in paired[:20]:
        print(f"{d['player_name']} ({d['tm_player_id']}) {d['competition_id']} | TM {d['tm_date']} "
              f"min {d['tm_minute']}{' ET' if d['tm_extra'] == 'True' else ''} | PitchAPI {d['pitch_date']} "
              f"min {d['pitch_minute']}+{d['pitch_minute_added'] or 0} -> cell {d['pitch_cell']}"
              f"{' ET' if d['pitch_extra'] == 'True' else ''} | diff {d['minute_diff']}")
    print("\n--- 20 players with the most one-sided goals ---")
    one_sided = defaultdict(lambda: [0, 0, ""])
    for d in diffs:
        if d["kind"] in ("tm_only", "pitch_only"):
            entry = one_sided[d["tm_player_id"]]
            entry[0 if d["kind"] == "tm_only" else 1] += 1
            entry[2] = d["player_name"]
    for pid, (tm_n, pa_n, name) in sorted(one_sided.items(), key=lambda item: -(item[1][0] + item[1][1]))[:20]:
        print(f"{name} ({pid}): Transfermarkt-only={tm_n}, PitchAPI-only={pa_n}")
    if any(skipped.values()):
        print("WARNING: some API resources were skipped; PitchAPI counts are partial.")


def row(kind, pid, name, tm, pa, diff):
    return {
        "kind": kind, "tm_player_id": pid, "player_name": name,
        "competition_id": (tm or pa)["competition_id"],
        "tm_date": tm["date"].isoformat() if tm else "", "pitch_date": pa["date"].isoformat() if pa else "",
        "tm_minute": "" if not tm or tm["cell"] is None else tm["cell"], "tm_extra": tm["extra"] if tm else "",
        "pitch_minute": pa["minute"] if pa else "", "pitch_minute_added": (pa["minute_added"] or "") if pa else "",
        "pitch_cell": pa["cell"] if pa else "", "pitch_extra": pa["extra"] if pa else "",
        "minute_diff": "" if diff is None else diff,
        "tm_game_id": tm["game_id"] if tm else "", "pitch_match_id": pa["match_id"] if pa else "",
        "pitch_player_id": pa["pitch_player_id"] if pa else "",
    }


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError, KeyError, duckdb.Error) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
