"""Which source fills each competition-season, and small goal helpers.

Sources are never mixed inside one competition-season, so a goal can never
be counted twice: for every (competition, season) up to Transfermarkt's last
day exactly one of Transfermarkt or ESPN is used. After that day only ESPN.
"""

if __package__:
    from .scope import BY_ID, season_of
else:
    from scope import BY_ID, season_of


def choose_sources(tm_counts, espn_counts):
    """tm_counts / espn_counts: {(competition_id, season): goals up to Transfermarkt's last day}.
    Returns {(competition_id, season): "tm" | "espn"}. Ties go to Transfermarkt."""
    choice = {}
    for key in set(tm_counts) | set(espn_counts):
        history = BY_ID[key[0]].history
        if history == "tm":
            choice[key] = "tm"
        elif history == "espn":
            choice[key] = "espn"
        else:
            choice[key] = "espn" if espn_counts.get(key, 0) > tm_counts.get(key, 0) else "tm"
    return choice


def use_tm_goal(competition_id, day, tm_last_day, choice):
    return day <= tm_last_day and choice.get((competition_id, season_of(day)), "tm") == "tm"


def use_espn_goal(competition_id, day, tm_last_day, choice):
    if day > tm_last_day:
        return True
    return choice.get((competition_id, season_of(day))) == "espn"


def gap_closed_date(goals):
    """Date the cell was first filled, when that first goal is a live update."""
    if not goals:
        return None
    first = min(goals, key=lambda goal: goal["date"])
    return first["date"] if first.get("live") else None
