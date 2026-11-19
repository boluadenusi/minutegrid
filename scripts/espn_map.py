"""Match ESPN squad players to Transfermarkt players, and ESPN teams to clubs.

Only players in the current squads of the top 5 leagues need a match (only
they are shown). Steps, each accepting a unique answer only (never a guess):
  1. date of birth + name (all words of the shorter name in the longer one),
     then date of birth + one shared name word;
  2. club + name: the ESPN team's Transfermarkt club and a unique name match
     there;
  3. goals: the ESPN scorer's goals up to Transfermarkt's last day coincide
     with one Transfermarkt player's goals (fingerprint_rules.py).
ESPN's dates of birth are sometimes plainly wrong (years off), so a differing
date of birth never blocks steps 2 and 3; it only blocks a single-goal match
whose names do not fully agree.
A Transfermarkt player can be matched to one ESPN player only. A match, once
made, is kept (data/espn/athlete_map.csv). A player whose name no
Transfermarkt player has (full name; nor a shared name word at the same date
of birth) and with no coinciding goals is new (not in Transfermarkt's data,
so no goals in it either) and gets an ESPN-only page.
Everything else goes to data/espn/review.csv.
ESPN team -> club: the club most of the team's matched players are at in
Transfermarkt (3+ players, at least half of them), else a unique club-name
match among the clubs of the same country.
"""

from collections import Counter, defaultdict
from datetime import date

if __package__:
    from .fingerprint_rules import fingerprint
    from .live_merge import resolve_team_by_name
    from .mapping_rules import name_tokens, player_names_match
    from .scope import BY_ID, TM_IDS
else:
    from fingerprint_rules import fingerprint
    from live_merge import resolve_team_by_name
    from mapping_rules import name_tokens, player_names_match
    from scope import BY_ID, TM_IDS


def _names(athlete):
    return [n for n in (athlete.get("name"), athlete.get("full_name")) if n]


def identity_match(athlete, by_dob):
    """(tm_player_id or None, reason, shared_word_candidates)."""
    if not athlete.get("dob"):
        return None, "no date of birth", None
    candidates = by_dob.get(athlete["dob"], [])
    full = {p["player_id"] for p in candidates if any(player_names_match(n, p["name"] or "") for n in _names(athlete))}
    if len(full) == 1:
        return next(iter(full)), "date of birth + name", 1
    if len(full) > 1:
        return None, "several players share the date of birth and name", len(full)
    words = {t for n in _names(athlete) for t in name_tokens(n)}
    shared = {p["player_id"] for p in candidates if words & set(name_tokens(p["name"] or ""))}
    if len(shared) == 1:
        return next(iter(shared)), "date of birth + shared name word", 1
    if len(shared) > 1:
        return None, "several players share the date of birth and a name word", len(shared)
    return None, "no Transfermarkt player with that date of birth and name", 0


def club_match(athlete, club_id, by_club):
    if not club_id:
        return None
    found = {p["player_id"] for p in by_club.get(club_id, [])
             if any(player_names_match(n, p["name"] or "") for n in _names(athlete))}
    return next(iter(found)) if len(found) == 1 else None


def name_index(tm_players):
    index = defaultdict(list)
    for p in tm_players:
        for token in set(name_tokens(p["name"] or "")):
            index[token].append(p)
    return index


def name_known(athlete, index):
    """True when some Transfermarkt player has the athlete's full name."""
    for n in _names(athlete):
        tokens = name_tokens(n)
        if not tokens:
            continue
        rarest = min(tokens, key=lambda t: len(index.get(t, ())))
        if any(player_names_match(n, p["name"] or "") for p in index.get(rarest, ())):
            return True
    return False


def map_teams(roster, athlete_to_tm, club_of_player, tm_clubs):
    """{espn team_id: tm club_id}."""
    by_team = defaultdict(list)
    team_info = {}
    for row in roster:
        by_team[row["team_id"]].append(row["athlete_id"])
        team_info[row["team_id"]] = (row["competition_id"], row["team"])
    clubs_by_country = defaultdict(dict)
    for club in tm_clubs:
        competition = BY_ID.get(club["competition_id"])
        if competition and competition.country:
            clubs_by_country[competition.country][str(club["club_id"])] = club["name"]
    result = {}
    for team_id, athletes in by_team.items():
        clubs = [club_of_player.get(athlete_to_tm[a]) for a in athletes if a in athlete_to_tm]
        votes = Counter(c for c in clubs if c)
        if votes:
            club, count = votes.most_common(1)[0]
            if count >= 3 and count >= 0.5 * len(clubs):
                result[team_id] = club
                continue
        competition_id, name = team_info[team_id]
        country = BY_ID[competition_id].country if competition_id in BY_ID else None
        candidates = {c: n for c, n in clubs_by_country.get(country, {}).items() if c not in result.values()}
        club = resolve_team_by_name(name, candidates, name_tokens)
        if club:
            result[team_id] = club
    return result


def _tm_by_day(tm_goals):
    index = defaultdict(list)
    for goal in tm_goals:
        minute = int(goal["minute"])
        index[(goal["competition_id"], date.fromisoformat(goal["date"]))].append({
            "player_id": int(goal["player_id"]), "date": date.fromisoformat(goal["date"]),
            "cell": minute, "extra": bool(goal["is_extra_time"]), "club_id": str(goal["club_id"]),
        })
    return index


def update(roster, existing, tm_players, tm_goals, espn_goals, tm_clubs, tm_last_day, today):
    """Returns (athlete_map rows, team_map, new_players rows, review rows)."""
    by_dob, by_club, dob_of, club_of, name_of = defaultdict(list), defaultdict(list), {}, {}, {}
    for p in tm_players:
        pid = int(p["player_id"])
        p = {**p, "player_id": pid}
        name_of[pid] = p["name"] or ""
        if p["dob"]:
            by_dob[p["dob"]].append(p)
            dob_of[pid] = p["dob"]
        if p["club_id"]:
            by_club[str(p["club_id"])].append(p)
            club_of[pid] = str(p["club_id"])

    mapped = {a: dict(row) for a, row in existing.items()}
    athlete_to_tm = {a: int(row["tm_player_id"]) for a, row in mapped.items()}
    athletes = {}
    for row in roster:
        athletes.setdefault(row["athlete_id"], row)
    pending = {a: row for a, row in athletes.items() if a not in mapped}

    proposals, reasons, word_candidates = {}, {}, {}
    for a, athlete in pending.items():
        pid, reason, shared = identity_match(athlete, by_dob)
        reasons[a], word_candidates[a] = reason, shared
        if pid is not None:
            proposals[a] = (pid, reason)

    # Teams from what is matched so far, then club + name and goals for the rest.
    team_map = map_teams(roster, {**athlete_to_tm, **{a: p for a, (p, _r) in proposals.items()}}, club_of, tm_clubs)
    for a, athlete in pending.items():
        if a in proposals:
            continue
        pid = club_match(athlete, team_map.get(athlete["team_id"]), by_club)
        if pid is not None:
            proposals[a] = (pid, "club + name")

    goals_by_athlete = defaultdict(list)
    for goal in espn_goals:
        if goal["athlete_id"] in pending and goal["date"] <= tm_last_day and goal["competition_id"] in TM_IDS:
            goals_by_athlete[goal["athlete_id"]].append({
                "competition_id": goal["competition_id"], "date": date.fromisoformat(goal["date"]),
                "cell": int(goal["cell"]), "extra": goal["extra"] in (True, "True", "true", "1"),
                "club": team_map.get(goal["team_id"]),
            })
    tm_index = _tm_by_day(tm_goals) if goals_by_athlete else {}
    fingerprint_reason = {}
    for a, goals in goals_by_athlete.items():
        if a in proposals:
            continue
        pid, reason, _best, hits, *_ = fingerprint(goals, tm_index, pending[a]["name"], name_of)
        fingerprint_reason[a] = reason
        if pid is None:
            continue
        dob_differs = pending[a].get("dob") and dob_of.get(pid) and dob_of[pid] != pending[a]["dob"]
        names_agree = any(player_names_match(n, name_of.get(pid, "")) for n in _names(pending[a]))
        if hits >= 2 or names_agree or not dob_differs:
            proposals[a] = (pid, f"goals: {reason}")

    by_name = name_index(tm_players)
    taken = set(athlete_to_tm.values())
    claims = Counter(pid for pid, _r in proposals.values())
    review, new_players = [], []
    for a in sorted(pending):
        athlete = pending[a]
        if a in proposals:
            pid, reason = proposals[a]
            if pid in taken:
                review.append(_review(athlete, f"Transfermarkt player {pid} is already matched to another ESPN player"))
            elif claims[pid] > 1:
                review.append(_review(athlete, f"Transfermarkt player {pid} fits several ESPN players"))
            else:
                mapped[a] = {"athlete_id": a, "tm_player_id": str(pid), "method": reason,
                             "espn_name": athlete["name"], "tm_name": name_of.get(pid, ""), "mapped_on": today}
                taken.add(pid)
            continue
        no_goals = fingerprint_reason.get(a) in (None, "no coinciding Transfermarkt goal")
        if word_candidates.get(a) in (0, None) and no_goals and not name_known(athlete, by_name):
            new_players.append({"athlete_id": a, "name": athlete["name"], "dob": athlete["dob"],
                                "team": athlete["team"], "competition_id": athlete["competition_id"]})
        else:
            reason = fingerprint_reason.get(a) or reasons.get(a) or "no match"
            if no_goals and name_known(athlete, by_name):
                reason = "a Transfermarkt player has this name, but neither club, date of birth nor goals confirm it"
            review.append(_review(athlete, reason))
    athlete_to_tm = {a: int(row["tm_player_id"]) for a, row in mapped.items()}
    team_map = map_teams(roster, athlete_to_tm, club_of, tm_clubs)
    return mapped, team_map, new_players, review


def _review(athlete, reason):
    return {"athlete_id": athlete["athlete_id"], "name": athlete["name"], "dob": athlete.get("dob", ""),
            "team": athlete["team"], "competition_id": athlete["competition_id"], "reason": reason}
