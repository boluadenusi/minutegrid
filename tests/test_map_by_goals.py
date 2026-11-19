import unittest
from collections import defaultdict
from datetime import date

from scripts.map_by_goals import fingerprint
from scripts.window_rules import in_window, window_start


def pg(day, cell, extra=False):
    return {"date": date(2025, 9, day), "cell": cell, "extra": extra, "competition_id": "IT1"}


def tm_index(*goals):
    index = defaultdict(list)
    for pid, day, cell in goals:
        index[("IT1", date(2025, 9, day))].append(
            {"player_id": pid, "club_id": "1", "date": date(2025, 9, day), "cell": cell, "extra": False})
    return index


NAMES = {1: "Romelu Lukaku", 2: "Scott McTominay"}


class FingerprintTest(unittest.TestCase):
    def test_maps_when_goals_coincide(self):
        index = tm_index((1, 1, 10), (1, 8, 55), (1, 15, 89), (2, 8, 70))
        result = fingerprint([pg(1, 10), pg(9, 56), pg(15, 90)], index, "R. Lukaku", NAMES)
        self.assertEqual(result[0], 1)

    def test_rejects_below_80_percent(self):
        index = tm_index((1, 1, 10), (1, 8, 55))
        result = fingerprint([pg(1, 10), pg(8, 55), pg(20, 30)], index, "Lukaku", NAMES)
        self.assertIsNone(result[0])

    def test_rejects_close_runner_up(self):
        index = tm_index((1, 1, 10), (1, 8, 55), (2, 1, 11), (2, 8, 54))
        self.assertIsNone(fingerprint([pg(1, 10), pg(8, 55)], index, "Lukaku", NAMES)[0])

    def test_single_goal_needs_exact_minute_and_name(self):
        index = tm_index((1, 1, 10))
        self.assertEqual(fingerprint([pg(1, 10)], index, "Lukaku", NAMES)[0], 1)
        self.assertIsNone(fingerprint([pg(1, 11)], index, "Lukaku", NAMES)[0])
        self.assertIsNone(fingerprint([pg(1, 10)], index, "Someone Else", NAMES)[0])

    def test_same_match_constraint_removes_other_clubs(self):
        index = tm_index((1, 1, 10), (1, 8, 55), (2, 1, 11), (2, 8, 54))
        for goals in index.values():
            for goal in goals:
                goal["club_id"] = "A" if goal["player_id"] == 1 else "B"
        goals = [{**pg(1, 10), "club": "A"}, {**pg(8, 55), "club": "A"}]
        self.assertEqual(fingerprint(goals, index, "Lukaku", NAMES)[0], 1)

    def test_extra_time_never_matches_regular(self):
        index = tm_index((1, 1, 90), (1, 8, 90))
        self.assertIsNone(fingerprint([pg(1, 91, True), pg(8, 91, True)], index, "Lukaku", NAMES)[0])


class WindowTest(unittest.TestCase):
    def test_window_start(self):
        self.assertEqual(window_start(date(2026, 11, 18)), date(2016, 11, 18))
        self.assertEqual(window_start(date(2028, 2, 29)), date(2018, 2, 28))

    def test_start_day_included(self):
        self.assertTrue(in_window("2016-11-18", "2016-11-18"))
        self.assertFalse(in_window("2016-11-17", "2016-11-18"))


if __name__ == "__main__":
    unittest.main()
