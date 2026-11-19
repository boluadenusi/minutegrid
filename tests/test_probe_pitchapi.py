import unittest

from scripts.probe_pitchapi import collect_goal_samples, goal_record, is_goal_event, propose_mapping


class ProbeTest(unittest.TestCase):
    def test_exact_name_and_country_is_confident(self):
        league = {"name": "Premier League", "country_code": "ENG"}
        competitions = [
            {"id": "GB1", "name": "Premier League", "country": "England"},
            {"id": "RU1", "name": "Premier League", "country": "Russia"},
        ]
        self.assertEqual(propose_mapping(league, competitions), ("GB1", "confident"))

    def test_second_division_and_unknown_country_are_unmapped(self):
        competitions = [{"id": "IT1", "name": "Serie A", "country": "Italy"}]
        self.assertEqual(propose_mapping({"name": "Serie B", "country_code": "ITA"}, competitions), ("", "unmapped"))
        self.assertEqual(propose_mapping({"name": "Serie A", "country_code": "XXX"}, competitions), ("", "unmapped"))

    def test_goal_includes_team_and_minute_fields(self):
        match = {
            "id": "m_1", "league": {"name": "Premier League"},
            "home_team": {"id": "t_1", "name": "Home"},
            "away_team": {"id": "t_2", "name": "Away"},
        }
        event = {
            "team_id": "t_2", "player": {"id": "p_1", "name": "Scorer"},
            "minute": 90, "minute_added": 4, "period": "SecondHalf",
            "is_own_goal": False, "is_penalty": True,
        }
        goal = goal_record(event, match, "2026-07-07")
        self.assertEqual(goal["team_name"], "Away")
        self.assertEqual((goal["minute"], goal["minute_added"]), (90, 4))
        self.assertTrue(goal["is_penalty"])
        self.assertEqual(goal["player_id"], "p_1")

    def test_goal_type_is_case_insensitive(self):
        for event_type in ("goal", "Goal", "GOAL"):
            self.assertTrue(is_goal_event({"event_type": event_type}))
        for event_type in ("substitution", "yellowcard"):
            self.assertFalse(is_goal_event({"event_type": event_type}))

    def test_samples_are_limited_and_may_overlap(self):
        samples = {"added_time": [], "penalties": [], "own_goals": []}
        goal = {"minute_added": 2, "is_penalty": True, "is_own_goal": True}
        for _ in range(12):
            collect_goal_samples(samples, goal)
        self.assertEqual(len(samples["added_time"]), 10)
        self.assertEqual(len(samples["penalties"]), 3)
        self.assertEqual(len(samples["own_goals"]), 3)

    def test_goal_requires_matching_team(self):
        match = {
            "id": "m_1", "league": {"name": "League"},
            "home_team": {"id": "t_1", "name": "Home"},
            "away_team": {"id": "t_2", "name": "Away"},
        }
        with self.assertRaisesRegex(RuntimeError, "not in match"):
            goal_record({"team_id": "t_unknown"}, match, "2026-07-07")


if __name__ == "__main__":
    unittest.main()
