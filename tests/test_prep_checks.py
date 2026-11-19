import unittest

from scripts.prep_checks import total_changes


class PrepChecksTest(unittest.TestCase):
    def test_identical_totals(self):
        self.assertEqual(total_changes({1: 10, 2: 536}, {1: 10, 2: 536}), [])

    def test_checks_only_players_with_previous_goals(self):
        self.assertEqual(
            total_changes({1: 5, 2: 7, 4: 0}, {1: 6, 3: 1, 4: 0}),
            [(1, 5, 6), (2, 7, 0)],
        )


if __name__ == "__main__":
    unittest.main()
