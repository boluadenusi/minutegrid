import unittest

from scripts.coverage_rules import competition_group, readable_competition_name


class CoverageRulesTest(unittest.TestCase):
    def test_allowed_competitions(self):
        examples = [
            ({"type": "domestic_league", "sub_type": "first_tier"}, "leagues"),
            ({"type": "domestic_cup", "sub_type": "domestic_cup"}, "cups"),
            ({"type": "other", "sub_type": "domestic_super_cup"}, "superCups"),
            ({"type": "other", "sub_type": "uefa_europa_league_qualifying"}, "uefa"),
            ({"type": "national_team_competition", "sub_type": "world_cup"}, "international"),
            ({"type": "national_team_competition", "sub_type": "uefa_euro"}, "international"),
        ]
        for competition, group in examples:
            with self.subTest(competition=competition):
                self.assertEqual(competition_group(competition), group)

    def test_excludes_second_divisions_and_playoffs(self):
        for subtype in ("second_tier", "play_off", None):
            with self.subTest(subtype=subtype):
                self.assertIsNone(competition_group({"type": "domestic_league", "sub_type": subtype}))

    def test_readable_name(self):
        self.assertEqual(readable_competition_name("serie-a"), "Serie A")


if __name__ == "__main__":
    unittest.main()
