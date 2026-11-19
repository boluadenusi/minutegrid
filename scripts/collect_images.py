#!/usr/bin/env python3
"""Collect PitchAPI player photos and club logos into data/images.json.

Player photos come from /v1/players/{id} profiles (image_url) of mapped
players; league logos from /v1/leagues when it has an image field; club logos from the team image_url in league schedules, attached to
Transfermarkt clubs through data/team_map.csv (teams without a mapping are
kept by league + team name, so prep.py can still use them).

Responses come from data/cache/ first; --cached-only makes no API requests.

The script then checks whether cdn.pitchapi.dev serves an image WITHOUT the
API key. If it does, the site links to the CDN directly. If it does not, or
with --download, images are saved under public/images/ and served by the
site itself (the key is only ever sent to cdn.pitchapi.dev, never printed).

Check PitchAPI's terms before showing or storing their images publicly.
"""

import argparse
import hashlib
import json
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlparse

import requests

if __package__:
    from .map_pitchapi import DATA, read_csv, seasons_in_range
    from .mapping_rules import confirmed_competitions
    from .pitch_cache import CachedPitchClient, PitchRequestError
    from .probe_pitchapi import ROOT, create_session, safe_id
else:
    from map_pitchapi import DATA, read_csv, seasons_in_range
    from mapping_rules import confirmed_competitions
    from pitch_cache import CachedPitchClient, PitchRequestError
    from probe_pitchapi import ROOT, create_session, safe_id


OUT = DATA / "images.json"
PUBLIC = ROOT / "public" / "images"
CDN_HOST = "cdn.pitchapi.dev"


def cdn_url(value):
    """Only https URLs on PitchAPI's CDN are accepted."""
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    return value if parsed.scheme == "https" and parsed.hostname == CDN_HOST else None


def is_image(response):
    return response.status_code == 200 and response.headers.get("Content-Type", "").startswith("image/")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cached-only", action="store_true", help="use data/cache only; no API requests")
    parser.add_argument("--download", action="store_true",
                        help="save images under public/images even if the CDN works without the key")
    args = parser.parse_args()

    with (DATA / "coverage.json").open(encoding="utf-8") as file:
        coverage = json.load(file)
    allowed = {entry["id"] for entries in coverage.values() for entry in entries}
    leagues = confirmed_competitions(
        read_csv(DATA / "competition_map.csv"), read_csv(DATA / "competition_overrides.csv"), allowed
    )
    player_map = read_csv(DATA / "player_map.csv")
    team_map = {(row["pitch_league_id"], row["pitch_team_id"]): row["tm_club_id"] for row in read_csv(DATA / "team_map.csv")}

    players, clubs, teams, league_logos = {}, {}, {}, {}
    skipped = 0
    with create_session() as session:
        client = CachedPitchClient(session, DATA / "cache")

        def get(path, **kwargs):
            if args.cached_only and client.cached_at(path) is None:
                return None
            return client.get(path, **kwargs)

        for index, row in enumerate(player_map, start=1):
            tm_id = row["tm_player_id"]
            if tm_id in players:
                continue
            try:
                profile = get(f"/v1/players/{safe_id(row['pitch_player_id'])}", skip_unavailable_profile=True)
            except PitchRequestError as error:
                print(f"Skipping player profile: {error}", file=sys.stderr, flush=True)
                skipped += 1
                continue
            url = cdn_url((profile or {}).get("image_url"))
            if url:
                players[tm_id] = url
            if index % 1000 == 0:
                print(f"  profiles checked: {index:,}/{len(player_map):,}", flush=True)
        print(f"Player photos: {len(players):,} of {len({r['tm_player_id'] for r in player_map}):,} mapped players")

        for league in leagues:
            lid = safe_id(league["pitch_league_id"])
            for season in seasons_in_range(league["seasons"], date(2025, 7, 1), date.today()):
                try:
                    schedule = get(f"/v1/leagues/{lid}/matches?season={quote(season, safe='')}")
                except PitchRequestError as error:
                    print(f"Skipping league season: {error}", file=sys.stderr, flush=True)
                    skipped += 1
                    continue
                for match in (schedule or {}).get("matches", []):
                    for side in ("home_team", "away_team"):
                        team = match[side]
                        url = cdn_url(team.get("image_url"))
                        if not url:
                            continue
                        club = team_map.get((lid, safe_id(team["id"])))
                        if club:
                            clubs.setdefault(club, url)
                        teams.setdefault(f"{league['competition_id']}|{team['name']}", url)
        print(f"Club logos: {len(clubs):,} mapped clubs, {len(teams):,} league teams by name")

        # League logos, if /v1/leagues has them (one request, then cached).
        try:
            catalog = get("/v1/leagues")
        except PitchRequestError as error:
            print(f"Skipping league list: {error}", file=sys.stderr, flush=True)
            skipped += 1
            catalog = None
        by_pitch_id = {safe_id(league["pitch_league_id"]): league["competition_id"] for league in leagues}
        for item in (catalog or {}).get("leagues", []):
            competition_id = by_pitch_id.get(safe_id(item.get("id", "")))
            url = cdn_url(item.get("image_url") or item.get("logo_url") or item.get("logo"))
            if competition_id and url:
                league_logos.setdefault(competition_id, url)
        if catalog is None:
            print("League logos: league list not cached (rerun without --cached-only)")
        elif not league_logos:
            print("League logos: PitchAPI's league list has no image field; leagues keep their names only")
        else:
            print(f"League logos: {len(league_logos)} of {len(leagues)} mapped leagues")

        # Does the CDN serve images without the key?
        sample = next(iter(players.values()), None) or next(iter(clubs.values()), None)
        key_required = None
        if sample:
            try:
                key_required = not is_image(requests.get(sample, timeout=30))
            except requests.RequestException as error:
                print(f"CDN check without key failed: {type(error).__name__}", file=sys.stderr)
                key_required = True
            if key_required:
                try:
                    with_key = is_image(session.get(sample, timeout=30))
                except requests.RequestException:
                    with_key = False
                print("CDN check: images need the API key" if with_key
                      else "CDN check: images did not load even with the key")
                if not with_key:
                    raise RuntimeError("PitchAPI images could not be loaded; nothing was written")
            else:
                print("CDN check: images load without the API key")

        download = args.download or bool(key_required)
        if download:
            saved = 0
            for kind, mapping in (("players", players), ("clubs", clubs), ("teams", teams), ("leagues", league_logos)):
                folder = PUBLIC / kind
                folder.mkdir(parents=True, exist_ok=True)
                for key, url in list(mapping.items()):
                    # Team keys contain names, so they get a stable short hash as file name.
                    stem = key if kind != "teams" else hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
                    name = stem + Path(urlparse(url).path).suffix
                    target = folder / "".join(ch for ch in name if ch.isalnum() or ch in "._-")
                    if not target.exists():
                        response = (session if key_required else requests).get(url, timeout=30)
                        if not is_image(response):
                            print(f"Could not download {kind} image for {key}: HTTP {response.status_code}",
                                  file=sys.stderr)
                            del mapping[key]
                            continue
                        target.write_bytes(response.content)
                        saved += 1
                        time.sleep(0.2)
                    mapping[key] = f"/images/{kind}/{target.name}"
            print(f"Downloaded {saved:,} images into public/images (existing files kept)")

    OUT.write_text(json.dumps({
        "checked": date.today().isoformat(), "local": download, "keyRequired": key_required,
        "players": players, "clubs": clubs, "teams": teams, "leagues": league_logos,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    if skipped:
        print(f"WARNING: {skipped} API resources were skipped; rerun to fill them in.")
    print("Next: python scripts/prep.py")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
