"""Launch scope: the top 5 European leagues, their domestic cups and super
cups, and the UEFA club competitions proper (no qualifying rounds).

history:
  "tm"   - Transfermarkt up to its last day, ESPN after it (complete in Transfermarkt).
  "best" - per season, whichever of Transfermarkt and ESPN has more goals
           (Transfermarkt's cup data is thin in places, e.g. early FA Cup rounds);
           ESPN after Transfermarkt's last day.
  "espn" - ESPN only (Transfermarkt does not have the competition).

Only players whose current club plays in one of LEAGUES are shown.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Competition:
    id: str
    espn: tuple          # ESPN league codes to try, first that works wins
    name: str
    country: str | None
    group: str           # coverage group: leagues, cups, superCups, uefa
    history: str         # tm, best or espn
    until: str | None = None  # last day the competition was played (it was abolished)


COMPETITIONS = (
    Competition("GB1", ("eng.1",), "Premier League", "England", "leagues", "tm"),
    Competition("ES1", ("esp.1",), "LaLiga", "Spain", "leagues", "tm"),
    Competition("IT1", ("ita.1",), "Serie A", "Italy", "leagues", "tm"),
    Competition("L1", ("ger.1",), "Bundesliga", "Germany", "leagues", "tm"),
    Competition("FR1", ("fra.1",), "Ligue 1", "France", "leagues", "tm"),

    Competition("FAC", ("eng.fa",), "FA Cup", "England", "cups", "best"),
    Competition("EFL", ("eng.league_cup",), "EFL Cup (Carabao Cup)", "England", "cups", "espn"),
    Competition("CDR", ("esp.copa_del_rey",), "Copa del Rey", "Spain", "cups", "best"),
    Competition("DFB", ("ger.dfb_pokal",), "DFB-Pokal", "Germany", "cups", "best"),
    Competition("CIT", ("ita.coppa_italia",), "Coppa Italia", "Italy", "cups", "best"),
    Competition("CDF", ("fra.coupe_de_france",), "Coupe de France", "France", "cups", "espn"),
    Competition("CDL", ("fra.coupe_de_la_ligue", "fra.league_cup"), "Coupe de la Ligue", "France", "cups",
                "espn", until="2020-06-30"),

    Competition("GBCS", ("eng.charity",), "Community Shield", "England", "superCups", "best"),
    Competition("SUC", ("esp.super_cup",), "Supercopa de España", "Spain", "superCups", "best"),
    Competition("DFL", ("ger.super_cup",), "DFL-Supercup", "Germany", "superCups", "best"),
    Competition("SCI", ("ita.super_cup",), "Supercoppa Italiana", "Italy", "superCups", "best"),
    Competition("FRCH", ("fra.super_cup",), "Trophée des Champions", "France", "superCups", "best"),

    Competition("CL", ("uefa.champions",), "Champions League", None, "uefa", "tm"),
    Competition("EL", ("uefa.europa",), "Europa League", None, "uefa", "tm"),
    Competition("UCOL", ("uefa.europa.conf",), "Conference League", None, "uefa", "tm"),
    Competition("USC", ("uefa.super_cup",), "UEFA Super Cup", None, "uefa", "best"),
)

BY_ID = {c.id: c for c in COMPETITIONS}
LEAGUES = tuple(c for c in COMPETITIONS if c.group == "leagues")
TM_IDS = tuple(c.id for c in COMPETITIONS if c.history != "espn")

# ESPN history is fetched from here for "best"/"espn" competitions (the
# rolling window never reaches further back than 10 years before today).
HISTORY_FROM = "2016-07-01"
# For "tm" competitions ESPN is only needed after Transfermarkt's last day;
# one overlapping season is fetched as well so scorers can be matched by goals.
OVERLAP_FROM = "2025-07-01"

# Players Transfermarkt does not know (signed after its last day) get an id
# above this, so they can never collide with a Transfermarkt id.
ESPN_ID_OFFSET = 1_000_000_000


def season_of(day):
    """European season of an ISO date: 2016-07-01 .. 2017-06-30 is season 2016."""
    year, month = int(day[:4]), int(day[5:7])
    return year if month >= 7 else year - 1


def fetch_from(competition):
    return OVERLAP_FROM if competition.history == "tm" else HISTORY_FROM
