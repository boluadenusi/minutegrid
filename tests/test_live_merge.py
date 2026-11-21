import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from scripts.live_merge import gap_closed_date, live_goals  # noqa: E402

INFO = {"GB1": {"name": "premier-league", "sub_type": "first_tier"}, "CL": {"name": "uefa-champions-league", "sub_type": None}}


def row(day, match, minute, *, added=None, period="SecondHalf", club="Arsenal", tm_club="11", pid=1, comp="GB1", pen=False):
    return (day, match, "Arsenal", "Chelsea", comp, club, tm_club, pid, minute, added, period, pen)


class LiveGoalsTest(unittest.TestCase):
    def test_added_time_penalty_and_club_update(self):
        goals, skipped = live_goals([row("2026-08-20", "m1", 90, added=3, pen=True)], "2026-07-06", set(), INFO, {"11": "Arsenal FC"})
        self.assertEqual(skipped, set())
        goal = goals[0]
        self.assertEqual((goal["cell"], goal["extra"]), (90, False))
        self.assertTrue(goal["entry"]["addedTime"] and goal["entry"]["penalty"])
        self.assertEqual(goal["entry"]["opponent"], "Chelsea")
        self.assertEqual(goal["club"], {"name": "Arsenal FC", "id": "11"})

    def test_cup_goal_does_not_update_club(self):
        goals, _ = live_goals([row("2026-09-20", "m1", 10, comp="CL")], "2026-07-06", set(), INFO, {})
        self.assertIsNone(goals[0]["club"])

    def test_match_already_in_transfermarkt_is_skipped_whole(self):
        rows = [row("2026-07-05", "m1", 10), row("2026-07-05", "m1", 20, club="Chelsea", tm_club="631", pid=2)]
        goals, skipped = live_goals(rows, "2026-07-06", {("2026-07-05", "631")}, INFO, {})
        self.assertEqual((goals, skipped), ([], {"m1"}))

    def test_gap_closed_only_when_first_goal_is_live(self):
        self.assertEqual(gap_closed_date([{"date": "2026-08-01", "source": "pitchapi"}]), "2026-08-01")
        self.assertIsNone(gap_closed_date([{"date": "2019-01-01"}, {"date": "2026-08-01", "source": "pitchapi"}]))


class ResolveTeamByNameTest(unittest.TestCase):
    def test_unique_fit_within_league(self):
        from scripts.live_merge import resolve_team_by_name
        from scripts.mapping_rules import name_tokens
        clubs = {"209": "Club Atlético River Plate", "1444": "Racing Club Asociación Civil de Avellaneda",
                 "1775": "Club Atlético Tigre", "12": "Club Atlético Independiente"}
        self.assertEqual(resolve_team_by_name("River Plate", clubs, name_tokens), "209")
        self.assertEqual(resolve_team_by_name("Racing Club", clubs, name_tokens), "1444")
        self.assertIsNone(resolve_team_by_name("Atlético", clubs, name_tokens))  # fits several
        self.assertIsNone(resolve_team_by_name("Boca Juniors", clubs, name_tokens))  # fits none


if __name__ == "__main__":
    unittest.main()
