"""Read the Transfermarkt snapshot in data/base/ (written by make_tm_snapshot.py)."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_DIR = ROOT / "data" / "base"
META_PATH = BASE_DIR / "meta.json"


def _rows(name, columns):
    import duckdb

    path = BASE_DIR / name
    if not path.exists():
        sys.exit(f"ERROR: {path.relative_to(ROOT)} is missing. Run python scripts/make_tm_snapshot.py once "
                 "(it needs ../footy-pipeline) and commit data/base/.")
    with duckdb.connect() as con:
        cursor = con.execute(f"SELECT {', '.join(columns)} FROM '{str(path).replace(chr(92), '/')}'")
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def exists():
    return META_PATH.exists()


def last_day():
    if not META_PATH.exists():
        sys.exit("ERROR: data/base/meta.json is missing. Run python scripts/make_tm_snapshot.py once.")
    return json.loads(META_PATH.read_text(encoding="utf-8"))["tm_last_day"]


def goals():
    return _rows("tm_goals.parquet",
                 ["player_id", "date", "minute", "is_extra_time", "club_id", "competition_id", "club", "opponent"])


def players():
    return _rows("tm_players.parquet", ["player_id", "name", "dob", "nationality", "club_id", "club"])


def clubs():
    return _rows("tm_clubs.parquet", ["club_id", "name", "competition_id"])
