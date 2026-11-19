"""Player photos and club logos from data/images.json (written by collect_images.py)."""

import json


def load_images(path):
    if not path.exists():
        return {"players": {}, "clubs": {}, "teams": {}, "leagues": {}}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {key: data.get(key) or {} for key in ("players", "clubs", "teams", "leagues")}


def player_image(images, pid):
    return images["players"].get(str(pid))


def club_with_logo(images, club, competition_id=None):
    """Copy of club {name, id} with "logo": by Transfermarkt club id, else by
    league + PitchAPI team name (clubs known only by name)."""
    if not club:
        return club
    logo = images["clubs"].get(str(club.get("id"))) if club.get("id") is not None else None
    if not logo and competition_id:
        logo = images["teams"].get(f"{competition_id}|{club.get('name')}")
    return {**club, "logo": logo} if logo else dict(club)
