ALMOST_MAX = 5  # "almost complete": 1 to 5 minutes missing (lib/window.ts uses the same)


def build_boards(players):
    complete = [player for player in players if player.get("active") is True and len(player["missing"]) == 0]
    almost = [player for player in players if player.get("active") is True and 1 <= len(player["missing"]) <= ALMOST_MAX]
    complete.sort(key=lambda player: (-player["goals"], player["id"]))
    almost.sort(key=lambda player: (len(player["missing"]), -player["goals"], player["id"]))
    return {"complete": complete[:50], "almost": almost[:50]}
