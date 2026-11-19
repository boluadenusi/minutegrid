#!/usr/bin/env python3
"""Map live-only PitchAPI scorers (unmatched rows in data/live_goals.parquet).

Goal fingerprinting cannot reach players who only started scoring after
Transfermarkt's last day (summer signings, debutants), so this uses names:

1. Club roster: the scorer's PitchAPI team is mapped (data/team_map.csv) and
   exactly one player in that Transfermarkt club's roster has a matching
   name (same tokens, or one name's tokens contain the other's).
2. Exact name + nationality: otherwise (e.g. a transfer after 2026-07-06),
   exactly one Transfermarkt player with last_season >= 2025 has the same
   full normalized name (at least two words) and the same nationality as the
   PitchAPI profile. The nationality-code table is learned from players that
   are already mapped; nothing is hardcoded.

One Transfermarkt player never takes two PitchAPI players with different
names. Everything else goes to data/live_review.csv; nothing is guessed.
After this, rerun sync_goals.py (it re-resolves stored goals) and prep.py.
"""

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict

import duckdb

if __package__:
    from .map_pitchapi import DATA, DATABASE, append_csv, read_csv
    from .mapping_rules import name_tokens, player_names_match
    from .pitch_cache import CachedPitchClient, PitchRequestError
    from .probe_pitchapi import create_session
    from .sync_goals import OUT as LIVE_PATH
else:
    from map_pitchapi import DATA, DATABASE, append_csv, read_csv
    from mapping_rules import name_tokens, player_names_match
    from pitch_cache import CachedPitchClient, PitchRequestError
    from probe_pitchapi import create_session
    from sync_goals import OUT as LIVE_PATH


MIN_LAST_SEASON = 2025
REVIEW_FIELDS = ["pitch_player_id", "player_name", "profile_name", "nationality", "teams", "competitions",
                 "goals", "candidates", "reason"]


def season_year(value):
    """players.last_season is VARCHAR ('2025'); returns the first year as an int, or None."""
    digits = str(value or "").strip()[:4]
    return int(digits) if digits.isdigit() else None


def learn_nationalities(pairs, min_count=5, min_share=0.9):
    """pairs: (pitch country_code, Transfermarkt country_of_citizenship) for mapped players."""
    votes = defaultdict(Counter)
    for code, country in pairs:
        if code and country:
            votes[code][country] += 1
    table = {}
    for code, counter in votes.items():
        country, count = counter.most_common(1)[0]
        total = sum(counter.values())
        if total >= min_count and count >= min_share * total:
            table[code] = country
    return table


def roster_match(names, clubs, roster):
    """Unique roster player in one of `clubs` whose name matches any of `names`."""
    found = {
        player["id"] for club in clubs for player in roster.get(club, ())
        if any(player_names_match(name, player["name"]) for name in names if name)
    }
    if len(found) == 1:
        return next(iter(found)), "club roster", found
    return None, ("ambiguous club roster" if found else "not in mapped club roster"), found


def name_nationality_match(names, country, by_name):
    """Unique recent player with the same full name (2+ words) and nationality."""
    if not country:
        return None, "nationality unknown", set()
    found = set()
    for name in names:
        tokens = name_tokens(name or "")
        if len(tokens) < 2:
            continue
        found |= {player["id"] for player in by_name.get(tokens, ()) if player["country"] == country}
    if len(found) == 1:
        return next(iter(found)), "exact name + nationality", found
    return None, ("several players with this name and nationality" if found
                  else "no exact name + nationality match"), found


def main():
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    if not LIVE_PATH.exists():
        raise RuntimeError("data/live_goals.parquet is missing; run sync_goals.py first")
    player_map = {row["pitch_player_id"]: row for row in read_csv(DATA / "player_map.csv")}
    team_map = {(row["pitch_league_id"], row["pitch_team_id"]): row["tm_club_id"] for row in read_csv(DATA / "team_map.csv")}

    with duckdb.connect() as con:
        live = con.execute(f"""
            SELECT pitch_league_id, team_id, club_name, competition_id, source_player_id, player_name,
                   tm_player_id
            FROM '{str(LIVE_PATH).replace(chr(92), "/")}'
            WHERE source_player_id IS NOT NULL
        """).fetchall()
    scorers = {}
    goals_by_comp = Counter()
    mapped_by_comp = Counter()
    live_teams = defaultdict(set)  # every live scorer's PitchAPI teams, mapped or not
    for lid, team_id, club_name, cid, pid, name, tm_id in live:
        live_teams[pid].add(club_name)
        goals_by_comp[cid] += 1
        # Trust the current player map, not tm_player_id stored by an earlier
        # sync: a mapping removed since then must come back for review.
        if pid in player_map:
            mapped_by_comp[cid] += 1
            continue
        entry = scorers.setdefault(pid, {"names": set(), "teams": set(), "clubs": set(), "comps": Counter(), "goals": 0})
        entry["names"].add(name)
        entry["teams"].add(club_name)
        entry["comps"][cid] += 1
        entry["goals"] += 1
        club = team_map.get((lid, team_id))
        if club:
            entry["clubs"].add(club)
    print(f"Live scorers without a mapping: {len(scorers):,} ({sum(s['goals'] for s in scorers.values()):,} goals)")

    with duckdb.connect(str(DATABASE), read_only=True) as con:
        rows = con.execute("""
            SELECT player_id, name, current_club_id, country_of_citizenship, last_season FROM players
            WHERE name IS NOT NULL
        """).fetchall()
    players = {int(pid): {"id": int(pid), "name": name, "club_id": str(club) if club is not None else None,
                          "country": country, "last_season": season_year(season)}
               for pid, name, club, country, season in rows}
    roster = defaultdict(list)
    by_name = defaultdict(list)
    for player in players.values():
        if player["club_id"]:
            roster[player["club_id"]].append(player)
        if player["last_season"] is not None and player["last_season"] >= MIN_LAST_SEASON:
            by_name[name_tokens(player["name"])].append(player)

    with create_session() as session:
        client = CachedPitchClient(session, DATA / "cache")
        # Nationality table from cached profiles of already-mapped players (no requests).
        pairs = []
        for pid, row in player_map.items():
            if client.cached_at(f"/v1/players/{pid}") is None:
                continue
            try:
                profile = client.get(f"/v1/players/{pid}", skip_unavailable_profile=True)
            except PitchRequestError:
                continue
            tm = players.get(int(row["tm_player_id"]))
            if profile and tm:
                pairs.append((profile.get("country_code"), tm["country"]))
        nationality = learn_nationalities(pairs)
        print(f"Nationality codes learned: {len(nationality)} (from {len(pairs):,} mapped players with cached profiles)")

        tm_to_names = defaultdict(set)
        for row in player_map.values():
            tm_to_names[int(row["tm_player_id"])].add(name_tokens(row["player_name"]))
        accepted, review = {}, []
        for pid, entry in sorted(scorers.items()):
            names = set(entry["names"])
            target, reason, found = roster_match(names, entry["clubs"], roster)
            profile = None
            if target is None:
                try:
                    profile = client.get(f"/v1/players/{pid}", skip_unavailable_profile=True)
                except PitchRequestError as error:
                    print(f"Skipping player profile: {error}", file=sys.stderr, flush=True)
                if profile and profile.get("name"):
                    names.add(profile["name"])
                code = profile.get("country_code") if profile else None
                if found:  # ambiguous roster: keep that reason unless nationality settles it uniquely
                    narrowed = {p for p in found if players[p]["country"] == nationality.get(code)}
                    if len(narrowed) == 1:
                        target, reason = next(iter(narrowed)), "club roster + nationality"
                else:
                    target, reason, found = name_nationality_match(names, nationality.get(code), by_name)
            if target is not None:
                own = {name_tokens(name) for name in names if name}
                if tm_to_names.get(target) and not tm_to_names[target] & own:
                    target, reason = None, "Transfermarkt player already mapped to a differently named PitchAPI player"
            if target is not None:
                accepted[pid] = (target, reason, entry)
                tm_to_names[target] |= {name_tokens(name) for name in names if name}
            else:
                review.append({
                    "pitch_player_id": pid, "player_name": " | ".join(sorted(n for n in entry["names"] if n)),
                    "profile_name": (profile or {}).get("name", ""),
                    "nationality": (profile or {}).get("country_code", ""),
                    "teams": " | ".join(sorted(entry["teams"])),
                    "competitions": " | ".join(sorted(entry["comps"])), "goals": entry["goals"],
                    "candidates": " | ".join(f"{p} {players[p]['name']} ({players[p]['country']})" for p in sorted(found)[:5]),
                    "reason": reason,
                })

    # PitchAPI can give one player separate ids (e.g. league vs UEFA), always at
    # the same club. Scorers at clubs that never overlap are different people
    # (two "Gustavo Silva"s), so every new mapping in such a group goes to review.
    holders = defaultdict(set)
    for pid, row in player_map.items():
        holders[int(row["tm_player_id"])].add(pid)
    for pid, (target, *_rest) in accepted.items():
        holders[target].add(pid)
    for target, pids in holders.items():
        team_sets = [live_teams[pid] for pid in pids if live_teams.get(pid)]
        if len(team_sets) < 2 or all(a & b for i, a in enumerate(team_sets) for b in team_sets[i + 1:]):
            continue
        for pid in sorted(pids & set(accepted)):
            _target, _reason, entry = accepted.pop(pid)
            review.append({
                "pitch_player_id": pid, "player_name": " | ".join(sorted(n for n in entry["names"] if n)),
                "profile_name": "", "nationality": "", "teams": " | ".join(sorted(entry["teams"])),
                "competitions": " | ".join(sorted(entry["comps"])), "goals": entry["goals"],
                "candidates": f"{target} {players[target]['name']} ({players[target]['country']})",
                "reason": "same Transfermarkt player matched to scorers at different clubs",
            })

    append_csv(DATA / "player_map.csv", ["pitch_player_id", "tm_player_id", "player_name"],
               [{"pitch_player_id": pid, "tm_player_id": target, "player_name": sorted(n for n in entry["names"] if n)[0]}
                for pid, (target, _reason, entry) in sorted(accepted.items())], ["pitch_player_id"])
    review.sort(key=lambda row: -row["goals"])
    with (DATA / "live_review.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(review)

    print("\n--- live goals by mapped players, per competition ---")
    newly = Counter()
    for _target, _reason, entry in accepted.values():
        newly.update(entry["comps"])
    for cid in sorted(goals_by_comp, key=lambda c: -goals_by_comp[c]):
        before, after, total = mapped_by_comp[cid], mapped_by_comp[cid] + newly[cid], goals_by_comp[cid]
        print(f"{cid}: goals={total}, mapped before={before} ({100 * before / total:.1f}%), "
              f"after={after} ({100 * after / total:.1f}%)")
    reasons = Counter(reason for _t, reason, _e in accepted.values())
    print(f"\nPlayers newly mapped: {len(accepted)} ({', '.join(f'{r}: {n}' for r, n in reasons.most_common())})")
    print(f"Goals newly usable: {sum(newly.values())}")
    print(f"Players left for review: {len(review)} (data/live_review.csv)")
    for reason, count in Counter(row["reason"] for row in review).most_common():
        print(f"  {reason}: {count}")
    print("\n--- 10 largest unresolved scorers ---")
    for row in review[:10]:
        print(f"{row['player_name']} | {row['teams']} | {row['goals']} goals | {row['reason']}")
    print("\nNext: python scripts/sync_goals.py (re-resolves stored goals), then python scripts/prep.py")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError, KeyError, duckdb.Error) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
