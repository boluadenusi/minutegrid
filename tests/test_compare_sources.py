import unittest
from datetime import date

from scripts.compare_sources import classify, pair_goals
from scripts.pitch_goals import goal_cell


def ev(minute, added=None, period="SecondHalf", own=False, pen=False):
    return {"minute": minute, "minute_added": added, "period": period, "is_own_goal": own, "is_penalty": pen}


class GoalCellTest(unittest.TestCase):
    def test_added_time_merges_into_45_and_90(self):
        self.assertEqual(goal_cell(ev(45, 2, "FirstHalf")), (45, False, True))
        self.assertEqual(goal_cell(ev(90, 4)), (90, False, True))
        self.assertEqual(goal_cell(ev(47, None, "FirstHalf")), (45, False, True))

    def test_own_goals_dropped_penalties_kept(self):
        self.assertIsNone(goal_cell(ev(30, own=True)))
        self.assertEqual(goal_cell(ev(30, pen=True)), (30, False, False))

    def test_extra_time_and_shootout(self):
        self.assertEqual(goal_cell(ev(105, 1, "ExtraTimeFirstHalf")), (105, True, True))
        self.assertEqual(goal_cell(ev(98, None, "")), (98, True, False))
        self.assertIsNone(goal_cell(ev(120, None, "PenaltyShootout")))


class PairGoalsTest(unittest.TestCase):
    def g(self, day, cell, extra=False):
        return {"date": date(2025, 9, day), "cell": cell, "extra": extra}

    def test_pairs_within_one_day_closest_minute(self):
        tm = [self.g(1, 10), self.g(1, 80)]
        pa = [self.g(2, 79), self.g(1, 10), self.g(5, 30)]
        pairs, tm_only, pa_only = pair_goals(tm, pa)
        self.assertEqual([classify(a, b)[0] for a, b in pairs], ["exact", "off_by_1"])
        self.assertEqual(tm_only, [])
        self.assertEqual(pa_only, [self.g(5, 30)])

    def test_unknown_tm_minute(self):
        pairs, _, _ = pair_goals([self.g(1, None)], [self.g(1, 50)])
        self.assertEqual(classify(*pairs[0])[0], "tm_minute_unknown")


if __name__ == "__main__":
    unittest.main()
