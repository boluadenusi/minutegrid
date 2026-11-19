"""Transfermarkt competition categories included in Minute Grid."""


def competition_group(competition):
    subtype = (competition.get("sub_type") or "").lower()
    kind = (competition.get("type") or "").lower()
    if subtype == "first_tier":
        return "leagues"
    if subtype == "domestic_cup" or kind == "domestic_cup":
        return "cups"
    if subtype == "domestic_super_cup":
        return "superCups"
    if kind == "national_team_competition":
        return "international"
    if subtype.startswith("uefa_"):
        return "uefa"
    return None


def readable_competition_name(name):
    return " ".join(name.replace("-", " ").replace("_", " ").split()).title()
