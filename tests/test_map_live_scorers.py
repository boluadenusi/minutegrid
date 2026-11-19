import sys
import unittest
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from scripts.map_live_scorers import learn_nationalities, name_nationality_match, roster_match, season_year  # noqa: E402
from scripts.mapping_rules import name_tokens  # noqa: E402


def player(pid, name, club="1", country="Japan"):
    return {"id": pid, "name": name, "club_id": club, "country": country, "last_season": 2025}


class SeasonYearTest(unittest.TestCase):
    def test_parses_varchar_seasons(self):
        self.assertEqual(season_year("2025"), 2025)
        self.assertEqual(season_year("2025/2026"), 2025)
        self.assertIsNone(season_year(None))
        self.assertIsNone(season_year(""))


class NationalityTableTest(unittest.TestCase):
    def test_needs_enough_consistent_votes(self):
        pairs = [("JPN", "Japan")] * 9 + [("JPN", "Korea, South")] + [("SWE", "Sweden")] * 4
        self.assertEqual(learn_nationalities(pairs), {"JPN": "Japan"})


class RosterMatchTest(unittest.TestCase):
    def test_unique_roster_name(self):
        roster = {"1": [player(1, "Yuito Suzuki"), player(2, "Akito Kato")]}
        self.assertEqual(roster_match({"Yuito Suzuki"}, {"1"}, roster)[0], 1)

    def test_shared_surname_is_ambiguous(self):
        roster = {"1": [player(1, "Yuito Suzuki"), player(2, "Akito Suzuki")]}
        target, reason, found = roster_match({"Suzuki"}, {"1"}, roster)
        self.assertIsNone(target)
        self.assertEqual(found, {1, 2})


class NameNationalityTest(unittest.TestCase):
    def index(self, *players):
        by_name = defaultdict(list)
        for p in players:
            by_name[name_tokens(p["name"])].append(p)
        return by_name

    def test_unique_full_name_and_nationality(self):
        by_name = self.index(player(1, "Akito Suzuki"), player(2, "Akito Suzuki", country="Brazil"))
        self.assertEqual(name_nationality_match({"Akito Suzuki"}, "Japan", by_name)[0], 1)

    def test_single_word_names_never_match(self):
        by_name = self.index(player(1, "Pedro", country="Brazil"))
        self.assertIsNone(name_nationality_match({"Pedro"}, "Brazil", by_name)[0])

    def test_unknown_nationality_goes_to_review(self):
        by_name = self.index(player(1, "Akito Suzuki"))
        self.assertEqual(name_nationality_match({"Akito Suzuki"}, None, by_name)[1], "nationality unknown")


if __name__ == "__main__":
    unittest.main()
