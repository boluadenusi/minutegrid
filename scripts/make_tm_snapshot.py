#!/usr/bin/env python3
"""One-time export of the Transfermarkt data Minute Grid needs into data/base/,
so the scheduled update job never needs ../footy-pipeline.

Transfermarkt's data stops at its last day (2026-07-06); everything after it
comes from ESPN, so this only has to be rerun if the Transfermarkt export is
ever refreshed.

Writes:
  data/base/tm_goals.parquet    goals in the launch competitions from 2016-07-01
  data/base/tm_players.parquet  every player: name, date of birth, nationality, club
  data/base/tm_clubs.parquet    club names per competition (launch competitions)
  data/base/meta.json           Transfermarkt's last day

Usage: python scripts/make_tm_snapshot.py
"""

import json
import sys

import duckdb

if __package__:
    from .scope import HISTORY_FROM, TM_IDS
    from .tm_base import BASE_DIR, META_PATH, ROOT
else:
    from scope import HISTORY_FROM, TM_IDS
    from tm_base import BASE_DIR, META_PATH, ROOT

PIPELINE = ROOT.parent / "footy-pipeline"
DUCKDB_PATH = PIPELINE / "transfermarkt-datasets.duckdb"
PARQUET_PATH = PIPELINE / "goals_grid.parquet"


def sql_path(path):
    return str(path).replace("\\", "/")


def main():
    for path in (DUCKDB_PATH, PARQUET_PATH):
        if not path.exists():
            sys.exit(f"ERROR: {path} not found")
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    columns = {row[0] for row in con.execute("DESCRIBE players").fetchall()}
    needed = {"player_id", "name", "date_of_birth", "country_of_citizenship", "current_club_id", "current_club_name"}
    if needed - columns:
        sys.exit(f"ERROR: players table lacks {sorted(needed - columns)}; it has {sorted(columns)}")
    ids = ",".join(f"'{cid}'" for cid in TM_IDS)
    goals = sql_path(PARQUET_PATH)

    con.execute(f"""
        COPY (
            SELECT g.player_id, g.game_id, strftime(CAST(g.date AS DATE), '%Y-%m-%d') AS date,
                   g.minute, g.is_extra_time, CAST(g.club_id AS VARCHAR) AS club_id, gm.competition_id,
                   CASE WHEN g.club_id = gm.home_club_id THEN gm.home_club_name
                        WHEN g.club_id = gm.away_club_id THEN gm.away_club_name END AS club,
                   CASE WHEN g.club_id = gm.home_club_id THEN gm.away_club_name
                        WHEN g.club_id = gm.away_club_id THEN gm.home_club_name END AS opponent
            FROM '{goals}' g JOIN games gm ON g.game_id = gm.game_id
            WHERE gm.competition_id IN ({ids}) AND CAST(g.date AS DATE) >= DATE '{HISTORY_FROM}'
            ORDER BY g.player_id, date
        ) TO '{sql_path(BASE_DIR / "tm_goals.parquet")}' (FORMAT parquet)
    """)
    con.execute(f"""
        COPY (
            SELECT player_id, name, strftime(CAST(date_of_birth AS DATE), '%Y-%m-%d') AS dob,
                   country_of_citizenship AS nationality, CAST(current_club_id AS VARCHAR) AS club_id,
                   current_club_name AS club
            FROM players ORDER BY player_id
        ) TO '{sql_path(BASE_DIR / "tm_players.parquet")}' (FORMAT parquet)
    """)
    con.execute(f"""
        COPY (
            SELECT DISTINCT CAST(club_id AS VARCHAR) AS club_id, name, competition_id FROM (
                SELECT home_club_id AS club_id, home_club_name AS name, competition_id FROM games
                UNION ALL
                SELECT away_club_id, away_club_name, competition_id FROM games
            ) WHERE competition_id IN ({ids}) AND club_id IS NOT NULL AND name IS NOT NULL
            ORDER BY club_id
        ) TO '{sql_path(BASE_DIR / "tm_clubs.parquet")}' (FORMAT parquet)
    """)
    last_day = con.execute(f"SELECT strftime(max(CAST(date AS DATE)), '%Y-%m-%d') FROM '{goals}'").fetchone()[0]
    counts = {name: con.execute(f"SELECT count(*) FROM '{sql_path(BASE_DIR / name)}'").fetchone()[0]
              for name in ("tm_goals.parquet", "tm_players.parquet", "tm_clubs.parquet")}
    con.close()
    META_PATH.write_text(json.dumps({"tm_last_day": last_day, "competitions": list(TM_IDS),
                                     "history_from": HISTORY_FROM}, indent=1), encoding="utf-8")
    for name, count in counts.items():
        print(f"  {name}: {count:,} rows")
    print(f"Transfermarkt's last day: {last_day}")
    print(f"Wrote {BASE_DIR.relative_to(ROOT)} (commit it: the scheduled job reads it)")


if __name__ == "__main__":
    main()
