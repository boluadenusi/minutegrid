import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from scripts.probe_espn_history import TARGETS, WINDOW_START, season_years, verdict  # noqa: E402


def window(matches=4, with_goals=3, with_details=3, goals=None, errors=0):
    goals = goals if goals is not None else [{"athlete_id": "1", "minute": 10}] * 5
    return {"window": "x", "matches": matches, "with_goals": with_goals, "with_details": with_details,
            "goals": goals, "errors": errors}


class HistoryTest(unittest.TestCase):
    def test_season_years(self):
        refs = ["http://sports.core.api.espn.com/v2/sports/soccer/leagues/eng.1/seasons/2016?lang=en",
                "http://sports.core.api.espn.com/v2/sports/soccer/leagues/eng.1/seasons/2003", None]
        self.assertEqual(season_years(refs), [2003, 2016])

    def test_verdicts(self):
        self.assertEqual(verdict([window()]), "full goal detail at the window start")
        self.assertTrue(verdict([window(with_details=1)]).startswith("partial"))
        self.assertEqual(verdict([window(with_details=0, goals=[])]), "scores only, no goal detail")
        self.assertEqual(verdict([window(matches=0, with_goals=0, with_details=0, goals=[])]),
                         "no matches found in the sample")
        self.assertTrue(verdict([window(matches=0, with_goals=0, with_details=0, goals=[], errors=3)]).startswith("unknown"))
        self.assertEqual(verdict([window(goals=[{"athlete_id": None, "minute": 10}])]),
                         "goal detail, but 1 goals without scorer id and 0 without a minute")

    def test_first_windows_are_inside_the_ten_year_window(self):
        for code, (_cid, _name, windows) in TARGETS.items():
            self.assertGreaterEqual(windows[0][0], WINDOW_START, code)
            self.assertLessEqual(windows[0][0], windows[0][1], code)


if __name__ == "__main__":
    unittest.main()
