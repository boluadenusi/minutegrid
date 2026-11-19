import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from scripts import espn_feed, espn_map, espn_sync  # noqa: E402
from scripts.grid_rules import choose_sources, gap_closed_date, use_espn_goal, use_tm_goal  # noqa: E402
from scripts.scope import BY_ID, COMPETITIONS, LEAGUES, season_of  # noqa: E402

TM_LAST = "2026-07-06"


class ScopeTest(unittest.TestCase):
    def test_scope_is_top5_cups_and_uefa_proper(self):
        ids = {c.id for c in COMPETITIONS}
        self.assertEqual({c.id for c in LEAGUES}, {"GB1", "ES1", "IT1", "L1", "FR1"})
        for cup in ("FAC", "EFL", "CDR", "DFB", "CIT", "CDF", "CDL", "GBCS", "SUC", "DFL", "SCI", "FRCH"):
            self.assertIn(cup, ids)
        self.assertTrue({"CL", "EL", "UCOL", "USC"} <= ids)
        self.assertFalse(ids & {"CLQ", "ELQ", "ECLQ", "FIWC"})
        self.assertEqual({c.id for c in COMPETITIONS if c.history == "espn"}, {"EFL", "CDF", "CDL"})

    def test_season_of(self):
        self.assertEqual(season_of("2016-07-01"), 2016)
        self.assertEqual(season_of("2017-06-30"), 2016)
        self.assertEqual(season_of("2026-11-18"), 2026)


class SourceChoiceTest(unittest.TestCase):
    def test_one_source_per_competition_season(self):
        tm = {("FAC", 2016): 61, ("FAC", 2017): 90, ("GB1", 2016): 1000, ("CDR", 2018): 50}
        espn = {("FAC", 2016): 78, ("FAC", 2017): 80, ("GB1", 2016): 1200, ("EFL", 2016): 150, ("CDR", 2018): 50}
        choice = choose_sources(tm, espn)
        self.assertEqual(choice[("FAC", 2016)], "espn")   # ESPN has more
        self.assertEqual(choice[("FAC", 2017)], "tm")
        self.assertEqual(choice[("GB1", 2016)], "tm")     # leagues: Transfermarkt history
        self.assertEqual(choice[("EFL", 2016)], "espn")   # only ESPN has it
        self.assertEqual(choice[("CDR", 2018)], "tm")     # tie

    def test_goals_never_counted_twice(self):
        choice = {("FAC", 2016): "espn", ("FAC", 2017): "tm", ("GB1", 2025): "tm"}
        for cid, day in (("FAC", "2017-01-07"), ("FAC", "2018-01-06"), ("GB1", "2026-05-24"),
                         ("GB1", "2026-08-20"), ("EFL", "2026-08-20")):
            self.assertNotEqual(use_tm_goal(cid, day, TM_LAST, choice), use_espn_goal(cid, day, TM_LAST, choice),
                                (cid, day))
        self.assertTrue(use_espn_goal("GB1", "2026-07-07", TM_LAST, choice))
        self.assertFalse(use_tm_goal("GB1", "2026-07-07", TM_LAST, choice))

    def test_gap_closed_only_by_live_goal(self):
        self.assertEqual(gap_closed_date([{"date": "2026-09-01", "live": True}]), "2026-09-01")
        self.assertIsNone(gap_closed_date([{"date": "2020-01-01", "source": "espn"},
                                           {"date": "2026-09-01", "live": True}]))
        self.assertIsNone(gap_closed_date([]))


def event(details, home_score="2", away_score="1", completed=True):
    return {"id": "99", "date": "2026-08-22T14:00Z", "name": "B at A",
            "status": {"type": {"completed": completed}},
            "competitions": [{"competitors": [
                {"homeAway": "home", "score": home_score, "team": {"id": "1", "displayName": "Arsenal"}},
                {"homeAway": "away", "score": away_score, "team": {"id": "2", "displayName": "Chelsea"}}],
                "details": details}]}


def detail(clock, athlete="10", team="1", **flags):
    return {"scoringPlay": True, "type": {"text": "Goal"}, "clock": {"displayValue": clock},
            "team": {"id": team}, "athletesInvolved": [{"id": athlete, "displayName": "A Player"}], **flags}


class FeedTest(unittest.TestCase):
    def test_parse_goals_rules(self):
        ev = event([detail("90'+3'", penaltyKick=True), detail("12'", athlete="11", team="2", ownGoal=True),
                    detail("45'+1'", athlete="12"), detail("105'", athlete="13", team="2"),
                    detail("120'", athlete="14", shootout=True)])
        match = espn_feed.parse_match("GB1", ev)
        self.assertEqual((match["home"], match["away"], match["date"]), ("Arsenal", "Chelsea", "2026-08-22"))
        goals, events = espn_feed.parse_goals("eng.1", match, ev, ev["competitions"][0]["details"])
        self.assertEqual(events, 4)  # own goal included, shoot-out kick not
        by_athlete = {g["athlete_id"]: g for g in goals}
        self.assertNotIn("11", by_athlete)  # own goal
        self.assertNotIn("14", by_athlete)  # shoot-out
        self.assertEqual((by_athlete["10"]["cell"], by_athlete["10"]["added_time"], by_athlete["10"]["penalty"]),
                         (90, True, True))
        self.assertEqual(by_athlete["10"]["opponent"], "Chelsea")
        self.assertEqual((by_athlete["12"]["cell"], by_athlete["12"]["added_time"]), (45, True))
        self.assertEqual((by_athlete["13"]["cell"], by_athlete["13"]["extra"], by_athlete["13"]["team"]),
                         (105, True, "Chelsea"))

    def test_calendar_days(self):
        self.assertEqual(espn_feed.calendar_days({"leagues": [{"calendar": ["2017-01-07T08:00Z", "2017-01-08T08:00Z"]}]}),
                         ["20170107", "20170108"])
        self.assertEqual(espn_feed.calendar_days({"leagues": [{"calendar": [{"entries": [{"startDate": "2017-02-01T08:00Z"}]}]}]}),
                         ["20170201"])
        self.assertEqual(espn_feed.calendar_days({}), [])

    def test_cup_rounds_are_read_day_by_day(self):
        # Cup/UEFA calendars give rounds as ranges; the detail names the match days.
        cup = {"leagues": [{"calendar": [{"startDate": "2019-06-01T04:00Z", "endDate": "2020-06-01T03:59Z", "entries": [
            {"detail": "Aug 27-Sep 2", "startDate": "2019-08-19T07:00Z", "endDate": "2019-09-11T06:59Z"},
            {"detail": "Dec 30-Jan 1", "startDate": "2019-12-17T08:00Z", "endDate": "2020-01-07T07:59Z"},
            {"detail": "Mar 1", "startDate": "2020-02-28T08:00Z", "endDate": "2020-06-01T06:59Z"},
            {"detail": "TBD", "startDate": "2020-06-10T07:00Z", "endDate": "2020-06-12T06:59Z"}]}]}]}
        days = espn_feed.calendar_days(cup)
        self.assertEqual(days[:9], ["20190826", "20190827", "20190828", "20190829", "20190830", "20190831",
                                    "20190901", "20190902", "20190903"])  # one day of margin either side
        self.assertIn("20191229", days)
        self.assertIn("20200102", days)  # round across new year
        self.assertIn("20200301", days)
        self.assertNotIn("20200401", days)  # the final's range is long, its day is not
        self.assertEqual(days[-3:], ["20200610", "20200611", "20200612"])  # no readable detail: whole range

    def test_duplicated_goal_events_are_dropped(self):
        # Two feeds merged: every goal twice, the copy up to a minute apart.
        ev = event([detail("26'"), detail("26'"), detail("49'", athlete="12"), detail("50'", athlete="12"),
                    detail("90'+3'", athlete="13"), detail("90'+4'", athlete="13")], home_score="3", away_score="0")
        match = espn_feed.parse_match("FAC", ev)
        goals, events = espn_feed.parse_goals("eng.fa", match, ev, ev["competitions"][0]["details"])
        self.assertEqual((events, sorted(g["athlete_id"] for g in goals)), (3, ["10", "12", "13"]))
        # A real brace a minute apart stays when the scoreline has room for it.
        ev = event([detail("49'", athlete="12"), detail("50'", athlete="12")], home_score="2", away_score="0")
        goals, _e = espn_feed.parse_goals("eng.fa", espn_feed.parse_match("FAC", ev), ev, ev["competitions"][0]["details"])
        self.assertEqual(len(goals), 2)

    def test_roster_athletes(self):
        flat = {"athletes": [{"id": 5, "displayName": "Bukayo Saka", "fullName": "Bukayo Saka",
                              "dateOfBirth": "2001-09-05T07:00Z", "citizenship": "England"}]}
        grouped = {"athletes": [{"position": "Forwards", "items": [
            {"id": "6", "displayName": "X", "citizenshipCountry": {"abbreviation": "FRA"}}]}]}
        self.assertEqual(espn_feed.roster_athletes(flat)[0],
                         {"athlete_id": "5", "name": "Bukayo Saka", "full_name": "Bukayo Saka",
                          "dob": "2001-09-05", "nationality": "England"})
        self.assertEqual(espn_feed.roster_athletes(grouped)[0]["nationality"], "FRA")

    def test_uncached_requests_are_not_stored(self):
        class Ok:
            status_code = 200

            def json(self):
                return {"events": []}

        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(espn_feed, "CACHE", Path(folder)), \
                mock.patch.object(espn_feed.time, "sleep", lambda _s: None), \
                mock.patch.object(espn_feed.requests, "get", lambda *_a, **_k: Ok()):
            self.assertEqual(espn_feed.get_json("https://example.test/a", cache=False), (200, {"events": []}))
            self.assertEqual(list(Path(folder).iterdir()), [])
            espn_feed.get_json("https://example.test/a", cache=True)
            self.assertEqual(len(list(Path(folder).iterdir())), 1)


def squad(athlete_id, name, dob, team_id="t1", team="Arsenal", competition="GB1"):
    return {"athlete_id": athlete_id, "name": name, "full_name": name, "dob": dob, "team_id": team_id,
            "team": team, "competition_id": competition, "first_seen": "2026-11-18"}


class MappingTest(unittest.TestCase):
    tm_players = [
        {"player_id": 1, "name": "Bukayo Saka", "dob": "2001-09-05", "nationality": "England", "club_id": "11", "club": "Arsenal"},
        {"player_id": 2, "name": "Declan Rice", "dob": "1999-01-14", "nationality": "England", "club_id": "11", "club": "Arsenal"},
        {"player_id": 3, "name": "Martin Ødegaard", "dob": "1998-12-17", "nationality": "Norway", "club_id": "11", "club": "Arsenal"},
        {"player_id": 4, "name": "Someone Else", "dob": "2005-05-05", "nationality": "Spain", "club_id": "99", "club": "Other"},
        {"player_id": 5, "name": "Gabriel Jesus", "dob": "1997-04-03", "nationality": "Brazil", "club_id": "11", "club": "Arsenal"},
    ]
    tm_clubs = [{"club_id": "11", "name": "Arsenal FC", "competition_id": "GB1"}]

    def run_update(self, roster, existing=None, espn_goals=(), tm_goals=()):
        return espn_map.update(roster, existing or {}, self.tm_players, list(tm_goals), list(espn_goals),
                               self.tm_clubs, TM_LAST, "2026-11-18")

    def test_date_of_birth_and_name(self):
        mapped, team_map, new, review = self.run_update([
            squad("a1", "Bukayo Saka", "2001-09-05"), squad("a2", "Declan Rice", "1999-01-14"),
            squad("a3", "Martin Odegaard", "1998-12-17"), squad("a4", "Brand New", "2008-02-02"),
            squad("a5", "Unknown Dob", "")])
        self.assertEqual({a: r["tm_player_id"] for a, r in mapped.items()}, {"a1": "1", "a2": "2", "a3": "3"})
        self.assertEqual(team_map, {"t1": "11"})                 # 3 matched players at club 11
        self.assertEqual([r["athlete_id"] for r in new], ["a4", "a5"])  # nobody in Transfermarkt has these names
        self.assertEqual(review, [])

    def test_club_and_name_when_birthday_differs_in_one_source(self):
        roster = [squad("a1", "Bukayo Saka", "2001-09-05"), squad("a2", "Declan Rice", "1999-01-14"),
                  squad("a3", "Martin Odegaard", "1998-12-17"), squad("a5", "Gabriel Jesus", "")]
        mapped, *_ = self.run_update(roster)
        self.assertEqual(mapped["a5"]["tm_player_id"], "5")
        self.assertEqual(mapped["a5"]["method"], "club + name")

    def test_wrong_espn_birthday_does_not_block_club_match(self):
        # ESPN's date of birth can be years off (seen: Jack Clarke, Thierno Barry).
        roster = [squad("a1", "Bukayo Saka", "2001-09-05"), squad("a2", "Declan Rice", "1999-01-14"),
                  squad("a3", "Martin Odegaard", "1998-12-17"), squad("a5", "Gabriel Jesus", "1993-01-01")]
        mapped, _t, new, _r = self.run_update(roster)
        self.assertEqual(mapped["a5"]["tm_player_id"], "5")
        self.assertEqual(new, [])

    def test_known_name_elsewhere_is_reviewed_not_new(self):
        # Wrong ESPN birthday and a club Transfermarkt cannot confirm: never a duplicate ESPN-only page.
        mapped, _t, new, review = self.run_update([squad("a7", "Someone Else", "1990-01-01", team_id="t9", team="Nowhere")])
        self.assertEqual((mapped, new), ({}, []))
        self.assertIn("has this name", review[0]["reason"])

    def test_existing_matches_are_kept_and_never_doubled(self):
        existing = {"old": {"athlete_id": "old", "tm_player_id": "1", "method": "x", "espn_name": "B. Saka",
                            "tm_name": "Bukayo Saka", "mapped_on": "2026-11-01"}}
        mapped, _t, new, review = self.run_update([squad("a1", "Bukayo Saka", "2001-09-05")], existing)
        self.assertEqual(set(mapped), {"old"})
        self.assertIn("already matched", review[0]["reason"])
        self.assertEqual(new, [])

    def test_two_espn_players_for_one_transfermarkt_player(self):
        mapped, _t, _n, review = self.run_update([squad("a1", "Bukayo Saka", "2001-09-05"),
                                                   squad("a9", "Saka", "2001-09-05", team_id="t2", team="Other")])
        self.assertEqual(mapped, {})
        self.assertEqual(len(review), 2)


class MergeTest(unittest.TestCase):
    def test_refetched_match_replaces_old_rows(self):
        old_m = [{"competition_id": "GB1", "match_id": "1", "date": "2026-08-01"},
                 {"competition_id": "GB1", "match_id": "2", "date": "2026-08-02"}]
        old_g = [{"competition_id": "GB1", "match_id": "1", "date": "2026-08-01", "minute": "10", "athlete_id": "a"},
                 {"competition_id": "GB1", "match_id": "2", "date": "2026-08-02", "minute": "5", "athlete_id": "b"}]
        new_m = [{"competition_id": "GB1", "match_id": "1", "date": "2026-08-01"}]
        new_g = [{"competition_id": "GB1", "match_id": "1", "date": "2026-08-01", "minute": 11, "athlete_id": "a"}]
        matches, goals = espn_sync.merge(old_m, old_g, new_m, new_g)
        self.assertEqual(len(matches), 2)
        self.assertEqual([(g["match_id"], int(g["minute"])) for g in goals], [("1", 11), ("2", 5)])


class CodesTest(unittest.TestCase):
    def test_every_competition_has_an_espn_code(self):
        for competition in COMPETITIONS:
            self.assertTrue(competition.espn, competition.id)
            self.assertIs(BY_ID[competition.id], competition)


if __name__ == "__main__":
    unittest.main()
