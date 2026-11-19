import unittest

from scripts.mapping_rules import confirmed_competitions, goal_coverage, match_player, match_player_without_profile, matching_team_ids, name_tokens, player_names_match, roster_team_match


class MappingRulesTest(unittest.TestCase):
    def test_only_confirmed_nonempty_overrides_are_used(self):
        base = [
            {"pitch_league_id": "a", "competition_id": "old"},
            {"pitch_league_id": "b", "competition_id": "old"},
            {"pitch_league_id": "c", "competition_id": "old"},
        ]
        overrides = [
            {"pitch_league_id": "a", "competition_id": "GB1"},
            {"pitch_league_id": "b", "competition_id": ""},
        ]
        self.assertEqual(confirmed_competitions(base, overrides, {"GB1"}), [
            {"pitch_league_id": "a", "competition_id": "GB1", "confidence": "confirmed"},
        ])

    def test_unknown_or_duplicate_overrides_fail(self):
        base = [{"pitch_league_id": "a"}]
        with self.assertRaises(ValueError):
            confirmed_competitions(base, [{"pitch_league_id": "b", "competition_id": "GB1"}], {"GB1"})
        with self.assertRaises(ValueError):
            confirmed_competitions(base, [{"pitch_league_id": "a", "competition_id": "BAD"}], {"GB1"})

    def test_team_matching_ignores_accents_and_club_terms(self):
        clubs = [{"id": "1", "name": "Málaga CF"}, {"id": "2", "name": "Málaga City FC"}]
        self.assertEqual(matching_team_ids("FC Malaga", clubs), {"1"})
        self.assertEqual(name_tokens("Łódź AFC", club=True), ("lodz",))

    def test_team_ambiguity_is_not_resolved_by_guessing(self):
        clubs = [{"id": "1", "name": "Example FC"}, {"id": "2", "name": "Example CF"}]
        self.assertEqual(matching_team_ids("Example", clubs), {"1", "2"})

    def test_roster_requires_three_unique_scorers_and_double_the_runner_up(self):
        clubs = [{"id": "1", "name": "First FC"}, {"id": "2", "name": "Second FC"}]
        players = [{"id": n, "name": f"Player {n}", "club_id": "1"} for n in range(3)]
        players += [{"id": 10, "name": "Player 0", "club_id": "2"}]
        scorers = ["Player 0", "Player 1", "Player 2", "Player 2"]
        self.assertEqual(roster_team_match(["Second"], scorers, clubs, players), ("1", 3, 1))
        players.append({"id": 11, "name": "Player 1", "club_id": "2"})
        self.assertEqual(roster_team_match(["First"], scorers, clubs, players), (None, 3, 2))
        self.assertEqual(roster_team_match(["First"], scorers[:2], clubs, players), (None, 2, 2))

    def test_goal_coverage_uses_saved_player_map_only_for_cross_competitions(self):
        goals = [
            {"league_id": league, "league": league, "player_id": pid, "name": pid, "team": "Team"}
            for league, pid in [("domestic", "old"), ("domestic", "new"), ("uefa", "old"), ("uefa", "missing")]
        ]
        totals, unmatched = goal_coverage(goals, {"uefa"}, {"new"}, {"old"}, set())
        self.assertEqual(totals, {"domestic": (2, 1), "uefa": (2, 1)})
        self.assertEqual(sum(count for _, count in unmatched.values()), 2)

    def test_goal_coverage_groups_name_variations_by_player_team_and_league(self):
        goals = [
            {"league_id": "l", "league": "League", "player_id": "p", "name": name, "team": "Team"}
            for name in ("J. Smith", "John Smith")
        ]
        _, unmatched = goal_coverage(goals, set(), set(), set(), set())
        self.assertEqual(list(unmatched.values()), [("J. Smith", 2)])

    def test_player_subset_and_ambiguity(self):
        self.assertTrue(player_names_match("Jude Bellingham", "Jude Victor Bellingham"))
        self.assertFalse(player_names_match("J. Bellingham", "Jude Bellingham"))
        players = [
            {"id": 1, "name": "Alex Smith", "club_id": "10"},
            {"id": 2, "name": "Alex James Smith", "club_id": "10"},
        ]
        self.assertEqual(match_player("Alex Smith", "10", {"10"}, players), (None, "ambiguous club"))

    def test_fallback_is_unique_within_league_only(self):
        players = [
            {"id": 1, "name": "Alex Smith", "club_id": "11"},
            {"id": 2, "name": "Alex Smith", "club_id": "99"},
        ]
        self.assertEqual(match_player("Alex Smith", "10", {"10", "11"}, players, {1}), (1, "other club in league"))
        self.assertEqual(match_player("Alex Smith", "10", {"10", "11"}, players), (None, "no player match"))
        players.append({"id": 3, "name": "Alex Smith", "club_id": "12"})
        self.assertEqual(match_player("Alex Smith", "10", {"10", "11", "12"}, players, {1, 3}), (None, "ambiguous league"))

    def test_no_empty_name_matches(self):
        self.assertFalse(player_names_match("", "Some Player"))

    def test_unavailable_profile_requires_unique_exact_name_in_team(self):
        players = [
            {"id": 1, "name": "José García", "club_id": "10"},
            {"id": 2, "name": "Jose Luis Garcia", "club_id": "10"},
            {"id": 3, "name": "Jose Garcia", "club_id": "20"},
        ]
        self.assertEqual(match_player_without_profile("Jose Garcia", "10", players), (1, "no nationality; exact club match"))
        self.assertEqual(match_player_without_profile("Jose", "10", players)[0], None)
        players.append({"id": 4, "name": "Jose Garcia", "club_id": "10"})
        self.assertEqual(match_player_without_profile("Jose Garcia", "10", players)[0], None)


if __name__ == "__main__":
    unittest.main()
