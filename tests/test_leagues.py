import unittest

from scripts.leagues import build_leagues

INFO = {"GB1": {"name": "Premier League", "country": "England"}, "ES1": {"name": "Laliga", "country": "Spain"}}


def entry(pid, name, club, cid="GB1", active=True, goals=10, minutes=30):
    return {"id": pid, "name": name, "club": club, "competitionId": cid, "active": active,
            "goals": goals, "minutes": minutes}


class BuildLeaguesTest(unittest.TestCase):
    def test_groups_active_players_by_league_and_club(self):
        summary, details = build_leagues([
            entry(1, "Haaland", {"name": "Manchester City", "id": "281"}, goals=277, minutes=85),
            entry(2, "Foden", {"name": "Man City", "id": "281"}, goals=90, minutes=60),
            entry(3, "Saka", {"name": "Arsenal FC", "id": "11"}),
            entry(4, "Retired", {"name": "Arsenal FC", "id": "11"}, active=False),
            entry(5, "Second tier", {"name": "Leeds", "id": "399"}, cid="GB2"),
            entry(6, "No club", None),
        ], INFO)
        self.assertEqual(summary, [{"id": "GB1", "name": "Premier League", "country": "England",
                                    "clubCount": 2, "playerCount": 3}])
        clubs = details["GB1"]["clubs"]
        self.assertEqual([club["name"] for club in clubs], ["Arsenal FC", "Manchester City"])
        self.assertEqual([p["name"] for p in clubs[1]["players"]], ["Haaland", "Foden"])

    def test_photos_and_logos_are_carried(self):
        _, details = build_leagues([
            {**entry(1, "Saka", {"name": "Arsenal FC", "id": "11", "logo": "/images/clubs/11.webp"}),
             "image": "/images/players/1.webp"},
            entry(2, "Rice", {"name": "Arsenal FC", "id": "11"}),
        ], INFO)
        club = details["GB1"]["clubs"][0]
        self.assertEqual(club["logo"], "/images/clubs/11.webp")
        self.assertEqual({p["name"]: p.get("image") for p in club["players"]},
                         {"Saka": "/images/players/1.webp", "Rice": None})

    def test_club_without_id_is_keyed_by_name(self):
        _, details = build_leagues([entry(1, "A", {"name": "Girona", "id": None}, cid="ES1")], INFO)
        self.assertEqual(details["ES1"]["clubs"][0]["id"], None)


if __name__ == "__main__":
    unittest.main()
