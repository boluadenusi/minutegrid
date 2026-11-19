import unittest

from scripts.probe_espn import describe, minute_cell, parse_clock


class ClockTest(unittest.TestCase):
    def test_parse_clock(self):
        self.assertEqual(parse_clock("45'+2'"), (45, 2))
        self.assertEqual(parse_clock("90' + 5'"), (90, 5))
        self.assertEqual(parse_clock("37'"), (37, 0))
        self.assertEqual(parse_clock("105'"), (105, 0))
        self.assertEqual(parse_clock("120'+1'"), (120, 1))
        for bad in (None, "", "HT", "FT", "45:00"):
            self.assertIsNone(parse_clock(bad))

    def test_minute_cell_rules(self):
        self.assertEqual(minute_cell(45, 2), (45, False, True))
        self.assertEqual(minute_cell(90, 4), (90, False, True))
        self.assertEqual(minute_cell(37, 0), (37, False, False))
        self.assertEqual(minute_cell(105, 0), (105, True, False))
        self.assertEqual(minute_cell(120, 1), (120, True, True))
        self.assertIsNone(minute_cell(0, 0))


class DaysTest(unittest.TestCase):
    def test_days_in(self):
        from scripts.probe_espn import days_in
        self.assertEqual(days_in("20261101"), ["20261101"])
        self.assertEqual(days_in("20261130-20261202"), ["20261130", "20261201", "20261202"])
        self.assertEqual(len(days_in("20260707-20260826")), 51)
        with self.assertRaises(ValueError):
            days_in("20261103-20261101")


class DiscoveryTest(unittest.TestCase):
    def test_slug_from_ref(self):
        from scripts.probe_espn import slug_from_ref
        self.assertEqual(slug_from_ref("http://sports.core.api.espn.com/v2/sports/soccer/leagues/eng.fa?lang=en&region=us"), "eng.fa")
        self.assertEqual(slug_from_ref("https://sports.core.api.espn.com/v2/sports/soccer/leagues/uefa.europa_qual"), "uefa.europa_qual")
        self.assertIsNone(slug_from_ref(None))

    def test_suggestions(self):
        from scripts.probe_espn import suggest
        leagues = {"ned.1": "Dutch Eredivisie", "ned.cup": "Dutch KNVB Beker", "ned.supercup": "Johan Cruijff Schaal",
                   "uefa.europa_qual": "UEFA Europa League Qualifying", "uefa.europa": "UEFA Europa League",
                   "uefa.europa.conf_qual": "UEFA Conference League Qualifying", "ukr.1": "Ukrainian Premier League"}
        self.assertEqual([s for s, _ in suggest("NLP", leagues)], ["ned.cup"])
        self.assertEqual([s for s, _ in suggest("NLSC", leagues)], ["ned.supercup"])
        self.assertEqual([s for s, _ in suggest("ELQ", leagues)], ["uefa.europa_qual"])
        self.assertEqual([s for s, _ in suggest("ECLQ", leagues)], ["uefa.europa.conf_qual"])
        self.assertEqual([s for s, _ in suggest("UKR1", leagues)], ["ukr.1"])
        self.assertEqual(suggest("AFAC", leagues), [])


class RequestTest(unittest.TestCase):
    def test_match_goals(self):
        from scripts.probe_espn import match_goals
        event = lambda a, b: {"competitions": [{"competitors": [{"score": a}, {"score": b}]}]}
        self.assertEqual(match_goals(event("0", "0")), 0)
        self.assertEqual(match_goals(event("2", "1")), 3)
        self.assertEqual(match_goals(event(None, None)), 0)
        self.assertEqual(match_goals(event("x", "1")), 1)

    def test_connection_errors_are_retried_and_not_cached(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        import requests
        from scripts import probe_espn

        calls = []

        class Ok:
            status_code = 200
            def json(self):
                return {"events": []}

        def flaky(*_args, **_kwargs):
            calls.append(1)
            if len(calls) < 3:
                raise requests.ConnectionError("dropped")
            return Ok()

        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(probe_espn, "CACHE", Path(folder)), \
                mock.patch.object(probe_espn.time, "sleep", lambda _s: None), \
                mock.patch.object(probe_espn.requests, "get", flaky):
            self.assertEqual(probe_espn.get_json("https://example.test/a"), (200, {"events": []}))
            self.assertEqual(len(calls), 3)

        def always_down(*_args, **_kwargs):
            raise requests.ConnectionError("down")

        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(probe_espn, "CACHE", Path(folder)), \
                mock.patch.object(probe_espn.time, "sleep", lambda _s: None), \
                mock.patch.object(probe_espn.requests, "get", always_down):
            status, body = probe_espn.get_json("https://example.test/b")
            self.assertIsNone(status)
            self.assertIn("after 4 attempts", body["error"])
            self.assertEqual(list(Path(folder).iterdir()), [])  # failures are not cached


class DescribeTest(unittest.TestCase):
    def test_reads_a_scoreboard_goal(self):
        event = {"id": "1", "name": "A at B", "competitions": [{"competitors": [
            {"team": {"id": "359", "displayName": "Arsenal"}}, {"team": {"id": "363", "displayName": "Chelsea"}}]}]}
        detail = {"type": {"text": "Penalty - Scored"}, "clock": {"displayValue": "90'+3'"}, "team": {"id": "359"},
                  "scoringPlay": True, "penaltyKick": True, "ownGoal": False,
                  "athletesInvolved": [{"id": "123", "displayName": "Bukayo Saka"}]}
        goal = describe("eng.1", "GB1", "2026-05-24", event, detail)
        self.assertEqual((goal["team"], goal["athlete_id"], goal["cell"], goal["minute_added"]), ("Arsenal", "123", 90, 3))
        self.assertTrue(goal["penalty"])
        self.assertFalse(goal["own_goal"])


if __name__ == "__main__":
    unittest.main()
