"""Conservative name and competition matching for the PitchAPI probe."""

import re
import unicodedata
from collections import Counter


CLUB_WORDS = frozenset({"fc", "cf", "afc", "sc", "ac", "club", "football", "futbol"})
TRANSLITERATION = str.maketrans({"ø": "o", "ł": "l", "đ": "d", "æ": "ae", "ß": "ss"})


def confirmed_competitions(base_rows, overrides, allowed_ids):
    base = {}
    for row in base_rows:
        league_id = row["pitch_league_id"]
        if not league_id or league_id in base:
            raise ValueError(f"Missing or duplicate PitchAPI league ID: {league_id}")
        base[league_id] = row
    result = []
    seen = set()
    for row in overrides:
        league_id = row["pitch_league_id"]
        if league_id in seen:
            raise ValueError(f"Duplicate competition override: {league_id}")
        seen.add(league_id)
        if league_id not in base:
            raise ValueError(f"Competition override has unknown PitchAPI league ID: {league_id}")
        competition_id = row["competition_id"].strip()
        if competition_id and competition_id not in allowed_ids:
            raise ValueError(f"Competition override is outside coverage: {competition_id}")
        if competition_id:
            result.append({**base[league_id], "competition_id": competition_id, "confidence": "confirmed"})
    return result


def name_tokens(name, club=False):
    normalized = unicodedata.normalize("NFKD", name.casefold().translate(TRANSLITERATION))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    tokens = re.findall(r"[^\W_]+", normalized)
    return tuple(token for token in tokens if not club or token not in CLUB_WORDS)


def matching_team_ids(name, clubs):
    tokens = name_tokens(name, club=True)
    if not tokens:
        return set()
    return {club["id"] for club in clubs if name_tokens(club["name"], club=True) == tokens}


def roster_team_match(team_names, scorer_names, clubs, players):
    eligible = {club["id"] for club in clubs}
    names_by_club = {}
    for player in players:
        if player["club_id"] in eligible:
            names_by_club.setdefault(player["club_id"], set()).add(name_tokens(player["name"]))
    scorers = {name_tokens(name) for name in scorer_names if name_tokens(name)}
    scores = {
        club_id: len(scorers & names_by_club.get(club_id, set()))
        for club_id in eligible
    }
    named = set()
    for name in team_names:
        named.update(matching_team_ids(name, clubs))
    ranked = sorted(scores, key=lambda club_id: (-scores[club_id], club_id not in named, club_id))
    if not ranked:
        return None, 0, 0
    top = scores[ranked[0]]
    second = scores[ranked[1]] if len(ranked) > 1 else 0
    if top >= 3 and top >= 2 * second:
        return ranked[0], top, second
    return None, top, second


def goal_coverage(goals, cross_leagues, verified_players, saved_players, conflicts):
    totals = {}
    unmatched = {}
    for goal in goals:
        league = goal["league_id"]
        total, matched = totals.get(league, (0, 0))
        pid = goal["player_id"]
        is_matched = bool(pid) and pid not in conflicts and (
            pid in saved_players or pid in verified_players
            if league in cross_leagues else pid in verified_players
        )
        totals[league] = (total + 1, matched + int(is_matched))
        if not is_matched:
            identity = pid or goal["name"]
            key = (identity, goal["team"], goal["league"])
            name, count = unmatched.get(key, (goal["name"], 0))
            unmatched[key] = (name, count + 1)
    return totals, unmatched


def player_names_match(left, right):
    left_tokens = Counter(name_tokens(left))
    right_tokens = Counter(name_tokens(right))
    if not left_tokens or not right_tokens:
        return False
    return not (left_tokens - right_tokens) or not (right_tokens - left_tokens)


def match_player_without_profile(name, club_id, players):
    tokens = name_tokens(name)
    if not tokens:
        return None, "no nationality; no exact player match"
    matches = {
        player["id"] for player in players
        if player["club_id"] == club_id and name_tokens(player["name"]) == tokens
    }
    if len(matches) == 1:
        return next(iter(matches)), "no nationality; exact club match"
    return None, "no nationality; ambiguous club" if matches else "no nationality; no exact player match"


def match_player(name, club_id, league_club_ids, players, transferred_ids=frozenset()):
    def candidates(club_ids):
        return {
            player["id"]
            for player in players
            if player["club_id"] in club_ids and player_names_match(name, player["name"])
        }

    direct = candidates({club_id})
    if len(direct) == 1:
        return next(iter(direct)), "club"
    if len(direct) > 1:
        return None, "ambiguous club"
    other = candidates(set(league_club_ids) - {club_id}) & transferred_ids
    if len(other) == 1:
        return next(iter(other)), "other club in league"
    return None, "ambiguous league" if other else "no player match"
