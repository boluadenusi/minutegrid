"""Turn rows of data/live_goals.parquet into Minute Grid goal entries.

Never mix sources inside one match: a live match is dropped when it falls on
or before Transfermarkt's last day and Transfermarkt may already hold it
(a known scoring club has a Transfermarkt game that day, or no club is known).
"""

from collections import defaultdict

from pitch_goals import goal_cell


def live_goals(rows, tm_last_day, tm_club_days, competition_info, club_names):
    """rows: (date, match_id, home, away, competition_id, club_name, tm_club_id,
    tm_player_id, minute, minute_added, period, is_penalty).

    Returns (goals, skipped_match_ids). Each goal is a dict with pid, date,
    cell, extra, entry (the goal detail for the page) and club (or None when
    the goal does not update the player's club: only first-tier leagues do).
    """
    by_match = defaultdict(list)
    for row in rows:
        by_match[row[1]].append(row)
    skipped = set()
    for match_id, match_rows in by_match.items():
        day = match_rows[0][0]
        if day > tm_last_day:
            continue
        clubs = {str(row[6]) for row in match_rows if row[6]}
        if not clubs or any((day, club) in tm_club_days for club in clubs):
            skipped.add(match_id)

    goals = []
    for (day, match_id, home, away, competition_id, club_name, tm_club_id, tm_player_id,
         minute, minute_added, period, is_penalty) in rows:
        if match_id in skipped or tm_player_id is None:
            continue
        cell = goal_cell({"minute": minute, "minute_added": minute_added, "period": period, "is_own_goal": False})
        if cell is None:
            continue
        info = competition_info.get(competition_id, {})
        club = club_names.get(str(tm_club_id), club_name) if tm_club_id else club_name
        entry = {
            "date": day,
            "opponent": away if club_name == home else home,
            "competition": info.get("name") or competition_id,
            "club": club,
            "source": "pitchapi",
        }
        if cell[2]:
            entry["addedTime"] = True
        if is_penalty:
            entry["penalty"] = True
        goals.append({
            "pid": int(tm_player_id), "date": day, "competition_id": competition_id, "cell": cell[0], "extra": cell[1], "entry": entry,
            "club": {"name": club, "id": str(tm_club_id) if tm_club_id else None}
            if info.get("sub_type") == "first_tier" else None,
        })
    return goals, skipped


def resolve_team_by_name(name, candidates, name_tokens):
    """Unique Transfermarkt club for an unmapped PitchAPI team name.

    candidates: {club_id: club_name}, limited to clubs that have played in
    the same league. All of the PitchAPI name's words (ignoring words like
    FC/Club) must appear in the club's name, e.g. "River Plate" ->
    "Club Atlético River Plate". Several fits, or none, give None.
    """
    tokens = set(name_tokens(name or "", club=True))
    if not tokens:
        return None
    fits = [club for club, club_name in candidates.items()
            if tokens <= set(name_tokens(club_name or "", club=True))]
    return fits[0] if len(fits) == 1 else None


def gap_closed_date(goals):
    """Date the cell was first filled, when that first goal came from the live file."""
    if not goals:
        return None
    first = min(goals, key=lambda goal: goal["date"])
    return first["date"] if first.get("source") == "pitchapi" else None
