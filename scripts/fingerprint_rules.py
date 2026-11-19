"""Match a scorer from another source to a Transfermarkt player by goals:
same competition, date within one day, same regular/extra-time half and a
minute cell within one. Used by map_by_goals.py (PitchAPI) and espn_map.py.
"""

from collections import Counter
from datetime import timedelta

if __package__:
    from .mapping_rules import name_tokens
else:
    from mapping_rules import name_tokens


def coincides(pitch_goal, tm_goal):
    # Same-match constraint: when the PitchAPI team is mapped to a club, only
    # goals for that club count, so goals from other matches that day cannot compete.
    club = pitch_goal.get("club")
    return (
        (club is None or tm_goal["club_id"] == club)
        and pitch_goal["extra"] == tm_goal["extra"]
        and tm_goal["cell"] is not None
        and abs((pitch_goal["date"] - tm_goal["date"]).days) <= 1
        and abs(pitch_goal["cell"] - tm_goal["cell"]) <= 1
    )


def fingerprint(pitch_goals, tm_by_day, pitch_name, tm_names):
    """Return (tm_player_id or None, reason, best, best_hits, runner_up, runner_hits)."""
    hits = Counter()
    exact = Counter()
    for goal in pitch_goals:
        seen = set()
        for offset in (-1, 0, 1):
            for tm in tm_by_day.get((goal["competition_id"], goal["date"] + timedelta(days=offset)), ()):
                if tm["player_id"] in seen or not coincides(goal, tm):
                    continue
                seen.add(tm["player_id"])
                hits[tm["player_id"]] += 1
                if tm["cell"] == goal["cell"] and tm["date"] == goal["date"]:
                    exact[tm["player_id"]] += 1
    ranked = hits.most_common(2)
    if not ranked:
        return None, "no coinciding Transfermarkt goal", None, 0, None, 0
    best, best_hits = ranked[0]
    runner, runner_hits = ranked[1] if len(ranked) > 1 else (None, 0)
    total = len(pitch_goals)
    if total == 1:
        if runner is not None:
            return None, "single goal with several candidates", best, best_hits, runner, runner_hits
        if not exact[best]:
            return None, "single goal, minute not identical", best, best_hits, runner, runner_hits
        if not set(name_tokens(pitch_name)) & set(name_tokens(tm_names.get(best, ""))):
            return None, "single goal, names share no token", best, best_hits, runner, runner_hits
        return best, "single goal, exact minute and name token", best, best_hits, runner, runner_hits
    if best_hits < 2:
        return None, "fewer than 2 coinciding goals", best, best_hits, runner, runner_hits
    if best_hits < 0.8 * total:
        return None, f"best covers {best_hits}/{total} goals (< 80%)", best, best_hits, runner, runner_hits
    if runner_hits * 3 > best_hits:
        return None, "runner-up too close", best, best_hits, runner, runner_hits
    return best, f"{best_hits}/{total} goals coincide", best, best_hits, runner, runner_hits
