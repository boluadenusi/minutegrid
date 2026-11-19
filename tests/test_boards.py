import unittest

from scripts.boards import build_boards


def player(player_id, missing, goals, date):
    return {
        "id": player_id,
        "name": f"Player {player_id}",
        "goals": goals,
        "active": True,
        "missing": missing,
        "lastGoalDate": date,
        "counts": [0 if minute in missing else 1 for minute in range(1, 91)],
    }


class BoardsTest(unittest.TestCase):
    def test_categories_order_and_shape(self):
        boards = build_boards([
            player(1, [], 100, "2024-01-01"),
            player(2, [], 200, "2025-01-01"),
            player(3, [8, 21], 300, "2024-03-01"),
            player(4, [8], 100, "2025-02-01"),
            player(5, [8], 200, "2025-03-01"),
            player(6, [1, 2, 3, 4], 400, "2025-04-01"),
            player(7, [1, 2, 3, 4, 5], 500, "2025-04-01"),
            player(8, [1, 2, 3, 4, 5, 6], 600, "2025-04-01"),  # six missing: not on a board
        ])
        self.assertEqual([p["id"] for p in boards["complete"]], [2, 1])
        self.assertEqual([p["id"] for p in boards["almost"]], [5, 4, 3, 6, 7])
        self.assertEqual(boards["almost"][2]["counts"][7], 0)
        self.assertEqual(len(boards["almost"][2]["counts"]), 90)
        self.assertEqual(boards["almost"][2]["lastGoalDate"], "2024-03-01")

    def test_board_limit(self):
        boards = build_boards([player(i, [], i, "2025-01-01") for i in range(60)])
        self.assertEqual(len(boards["complete"]), 50)
        self.assertEqual(boards["complete"][0]["id"], 59)
        self.assertEqual(boards["complete"][-1]["id"], 10)

    def test_almost_includes_three_gaps_and_is_limited(self):
        boards = build_boards([player(i, [8, 21, 46], i, "2025-01-01") for i in range(60)])
        self.assertEqual(len(boards["almost"]), 50)
        self.assertEqual(boards["almost"][0]["id"], 59)
        self.assertEqual(boards["almost"][-1]["id"], 10)

    def test_inactive_players_are_excluded(self):
        complete = player(1, [], 400, "2025-01-01")
        almost = player(2, [8], 300, "2025-01-01")
        complete["active"] = False
        almost["active"] = False
        self.assertEqual(build_boards([complete, almost]), {"complete": [], "almost": []})


if __name__ == "__main__":
    unittest.main()
