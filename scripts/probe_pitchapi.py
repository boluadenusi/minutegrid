#!/usr/bin/env python3
"""Probe PitchAPI goals and propose competition mappings for review."""

import argparse
import csv
import json
import re
import sys
import unicodedata
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

import requests
from dotenv import dotenv_values
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "https://api.pitchapi.dev"
COUNTRIES = {
    "ARG": "Argentina", "AUS": "Australia", "AUT": "Austria", "BEL": "Belgium",
    "BRA": "Brazil", "CRO": "Croatia", "HRV": "Croatia", "CZE": "Czech Republic",
    "DEN": "Denmark", "DNK": "Denmark", "ENG": "England", "FRA": "France",
    "GER": "Germany", "DEU": "Germany", "GRE": "Greece", "GRC": "Greece",
    "ITA": "Italy", "JPN": "Japan", "KOR": "Korea, South", "MEX": "Mexico",
    "NED": "Netherlands", "NLD": "Netherlands", "NOR": "Norway", "POL": "Poland",
    "POR": "Portugal", "PRT": "Portugal", "ROU": "Romania", "RUS": "Russia",
    "KSA": "Saudi Arabia", "SAU": "Saudi Arabia", "SCO": "Scotland",
    "SRB": "Serbia", "ESP": "Spain", "SWE": "Sweden", "SUI": "Switzerland",
    "CHE": "Switzerland", "TUR": "Türkiye", "UKR": "Ukraine", "USA": "United States",
}


def normalize(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def propose_mapping(league, competitions):
    country = COUNTRIES.get(str(league.get("country_code", "")).upper())
    if not country:
        return "", "unmapped"
    league_name = normalize(league["name"])
    if re.search(r"\b(second|segunda|serie b|ligue 2|laliga 2|2 bundesliga|bundesliga 2)\b", league_name):
        return "", "unmapped"
    candidates = [
        item for item in competitions
        if item.get("country") and normalize(item["country"]) == normalize(country)
    ]
    exact = [item for item in candidates if normalize(item["name"]) == league_name]
    if len(exact) == 1:
        return exact[0]["id"], "confident"
    if exact:
        return "", "unmapped"
    scored = sorted(
        ((SequenceMatcher(None, league_name, normalize(item["name"])).ratio(), item["id"])
         for item in candidates
         if set(re.findall(r"\b\d+\b", league_name))
         == set(re.findall(r"\b\d+\b", normalize(item["name"])))),
        reverse=True,
    )
    if scored and scored[0][0] >= 0.8 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        return scored[0][1], "unsure"
    return "", "unmapped"


def write_map(leagues, coverage, output):
    competitions = [item for group in coverage.values() for item in group]
    with output.open("x", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=[
            "pitch_league_id", "country_code", "pitch_league_name", "seasons",
            "competition_id", "confidence",
        ])
        writer.writeheader()
        for league in leagues:
            competition_id, confidence = propose_mapping(league, competitions)
            writer.writerow({
                "pitch_league_id": league["id"],
                "country_code": league["country_code"],
                "pitch_league_name": league["name"],
                "seasons": json.dumps(league["seasons"], ensure_ascii=False),
                "competition_id": competition_id,
                "confidence": confidence,
            })


def get_data(session, path):
    try:
        response = session.get(BASE_URL + path, timeout=30, allow_redirects=False)
    except requests.RequestException as error:
        raise RuntimeError(f"PitchAPI request failed for {path}: {type(error).__name__}") from None
    if response.status_code != 200:
        raise RuntimeError(f"PitchAPI returned HTTP {response.status_code} for {path}")
    try:
        payload = response.json()
    except requests.exceptions.JSONDecodeError:
        raise RuntimeError(f"PitchAPI returned invalid JSON for {path}") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise RuntimeError(f"PitchAPI returned an unexpected response for {path}")
    return payload["data"]


def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("PitchAPI returned an invalid identifier")
    return value


def goal_record(event, match, day):
    teams = [match["home_team"], match["away_team"]]
    team = next((team for team in teams if team["id"] == event["team_id"]), None)
    if team is None:
        raise RuntimeError(f"Goal team {event['team_id']} is not in match {match['id']}")
    player = event.get("player") or {}
    return {
        "league": match["league"]["name"],
        "date": day,
        "match_id": match["id"],
        "team_id": event["team_id"],
        "team_name": team["name"],
        "player_id": player.get("id"),
        "player_name": player.get("name"),
        "minute": event["minute"],
        "minute_added": event.get("minute_added"),
        "period": event.get("period"),
        "is_own_goal": event["is_own_goal"],
        "is_penalty": event["is_penalty"],
    }


def is_goal_event(event):
    return event["event_type"].casefold() == "goal"


def collect_goal_samples(samples, goal):
    if goal["minute_added"] is not None and goal["minute_added"] > 0 and len(samples["added_time"]) < 10:
        samples["added_time"].append(goal)
    if goal["is_penalty"] and len(samples["penalties"]) < 3:
        samples["penalties"].append(goal)
    if goal["is_own_goal"] and len(samples["own_goals"]) < 3:
        samples["own_goals"].append(goal)


def create_session():
    key = dotenv_values(ROOT / ".env").get("PITCH_KEY")
    if not key:
        raise RuntimeError("PITCH_KEY is missing from .env")
    session = requests.Session()
    session.headers["X-API-KEY"] = key
    retries = Retry(
        total=4,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods={"GET"},
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dates", nargs="+", type=date.fromisoformat, help="Match dates, YYYY-MM-DD")
    args = parser.parse_args()
    output = ROOT / "data" / "competition_map.csv"
    if output.exists():
        raise RuntimeError("data/competition_map.csv already exists; preserve or rename it before probing again")
    with (ROOT / "data" / "coverage.json").open(encoding="utf-8") as file:
        coverage = json.load(file)
    with create_session() as session:
        leagues = get_data(session, "/v1/leagues")["leagues"]
        print("--- leagues ---")
        for league in leagues:
            print(json.dumps({field: league[field] for field in ("country_code", "name", "seasons")}, ensure_ascii=False))
        scorers = {}
        samples = {"added_time": [], "penalties": [], "own_goals": []}
        print("--- goal events ---")
        for day in args.dates:
            day_string = day.isoformat()
            matches = get_data(session, f"/v1/date/{day_string}")["matches"]
            for match in matches:
                match_id = safe_id(match["id"])
                events = get_data(session, f"/v1/matches/{match_id}/events")["events"]
                for event in events:
                    if not is_goal_event(event):
                        continue
                    goal = goal_record(event, match, day_string)
                    print(json.dumps(goal, ensure_ascii=False))
                    collect_goal_samples(samples, goal)
                    if goal["player_id"] and not goal["is_own_goal"] and len(scorers) < 5:
                        scorers[safe_id(goal["player_id"])] = goal["player_name"]

        for label, goals in samples.items():
            print(f"--- {label} samples ({len(goals)}) ---")
            for goal in goals:
                print(json.dumps(goal, ensure_ascii=False))

        print("--- player responses ---")
        for player_id in scorers:
            player = get_data(session, f"/v1/players/{player_id}")
            print(json.dumps(player, ensure_ascii=False))
        write_map(leagues, coverage, output)
        print(f"Competition mapping written to {output}")
        print(f"Printed {len(scorers)} distinct scoring players.")
        if len(scorers) < 5:
            print("Fewer than five scorers were found; rerun with additional dates after preserving the map.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
