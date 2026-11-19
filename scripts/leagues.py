"""League -> club -> player line-up for the home page explorer.

Only active players (current club in a first-tier league) are listed, under
the league their club plays in. A club is keyed by its Transfermarkt id when
known (else its name) and shown under its most common name.
"""

from collections import Counter


def build_leagues(entries, league_info):
    """entries: dicts with id, name, club {name, id}, competitionId, active, goals, minutes.
    league_info: {competition_id: {"name": ..., "country": ...}} for first-tier leagues.

    Returns (summary, details): summary is a list for data/leagues.json and
    details maps competition id -> data for data/leagues/{id}.json.
    """
    leagues = {}
    for entry in entries:
        cid, club = entry.get("competitionId"), entry.get("club")
        if not entry.get("active") or not club or not club.get("name") or cid not in league_info:
            continue
        key = str(club.get("id") or club["name"])
        group = leagues.setdefault(cid, {}).setdefault(
            key, {"id": club.get("id"), "names": Counter(), "logo": None, "players": []})
        group["names"][club["name"]] += 1
        group["logo"] = group["logo"] or club.get("logo")
        player = {"id": entry["id"], "name": entry["name"], "goals": entry["goals"], "minutes": entry["minutes"]}
        if entry.get("image"):
            player["image"] = entry["image"]
        group["players"].append(player)

    summary, details = [], {}
    for cid, clubs_by_key in leagues.items():
        clubs = []
        for group in clubs_by_key.values():
            players = sorted(group["players"], key=lambda p: (-p["minutes"], -p["goals"], p["name"].casefold()))
            club = {"id": group["id"], "name": group["names"].most_common(1)[0][0], "players": players}
            if group["logo"]:
                club["logo"] = group["logo"]
            clubs.append(club)
        clubs.sort(key=lambda club: club["name"].casefold())
        info = league_info[cid]
        details[cid] = {"id": cid, "name": info["name"], "country": info.get("country"), "clubs": clubs}
        summary.append({
            "id": cid, "name": info["name"], "country": info.get("country"),
            "clubCount": len(clubs), "playerCount": sum(len(club["players"]) for club in clubs),
        })
    summary.sort(key=lambda league: ((league["country"] or "").casefold(), league["name"].casefold()))
    return summary, details
