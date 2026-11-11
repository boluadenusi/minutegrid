#!/usr/bin/env python3
"""
prep.py - Minute Grid data preparation script.

Reads goals_grid.parquet + transfermarkt-datasets.duckdb (players table)
Outputs:
  data/players/{player_id}.json  - per-player detail
  data/index.json                - search index (id, name, goalCount)
"""

import sys
import json
import pathlib
import duckdb
import pyarrow.parquet as pq
import pandas as pd

# ---------------------------------------------------------------------------
# Paths (relative to repo root, i.e. one level up from scripts/)
# ---------------------------------------------------------------------------
SCRIPT_DIR = pathlib.Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
PARQUET_PATH = ROOT_DIR.parent / "footy-pipeline" / "goals_grid.parquet"
DUCKDB_PATH = ROOT_DIR.parent / "footy-pipeline" / "transfermarkt-datasets.duckdb"
OUT_PLAYERS_DIR = ROOT_DIR / "data" / "players"
OUT_INDEX_PATH = ROOT_DIR / "data" / "index.json"

# ---------------------------------------------------------------------------
# 1. Load goals
# ---------------------------------------------------------------------------
print(f"Reading {PARQUET_PATH} …")
goals_df = pq.read_table(PARQUET_PATH).to_pandas()
print(f"  {len(goals_df):,} rows, columns: {list(goals_df.columns)}")

REQUIRED_COLS = {
    "game_event_id", "game_id", "date", "minute",
    "club_id", "player_id", "stoppage_ambiguous", "is_extra_time",
}
missing = REQUIRED_COLS - set(goals_df.columns)
if missing:
    print(f"ERROR: parquet is missing columns: {missing}")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 2. Load players from DuckDB
# ---------------------------------------------------------------------------
print(f"Reading players from {DUCKDB_PATH} …")
con = duckdb.connect(str(DUCKDB_PATH), read_only=True)

# Confirm the columns we need exist
try:
    players_df = con.execute("SELECT player_id, name FROM players").df()
except duckdb.CatalogException as e:
    print(f"ERROR: could not query players table – {e}")
    print("DESCRIBE players:")
    print(con.execute("DESCRIBE players").fetchall())
    sys.exit(1)

con.close()
print(f"  {len(players_df):,} players loaded")

# Build lookup
players_map: dict[int, str] = dict(
    zip(players_df["player_id"].astype(int), players_df["name"].astype(str))
)

# ---------------------------------------------------------------------------
# 3. Compute dataUpTo
# ---------------------------------------------------------------------------
goals_df["date"] = pd.to_datetime(goals_df["date"])
data_up_to: str = goals_df["date"].max().strftime("%Y-%m-%d")
print(f"  dataUpTo = {data_up_to}")

# ---------------------------------------------------------------------------
# 4. Aggregate per player
# ---------------------------------------------------------------------------
# Clamp regular-time minutes to [1, 90].
# Extra-time goals (is_extra_time == True) are kept separately.
# Cells 45 and 90 include stoppage-time goals (stoppage_ambiguous).

OUT_PLAYERS_DIR.mkdir(parents=True, exist_ok=True)

index_entries: list[dict] = []

player_ids = sorted(goals_df["player_id"].unique())
print(f"Processing {len(player_ids):,} players …")

for pid in player_ids:
    pid = int(pid)
    pdata = goals_df[goals_df["player_id"] == pid]

    name = players_map.get(pid, f"Player {pid}")

    # Regular-time rows (minute in 1–90, or stoppage_ambiguous bucketed to 45/90)
    regular = pdata[~pdata["is_extra_time"]]
    # Extra-time rows
    extra = pdata[pdata["is_extra_time"]]

    # Minutes scored in (1–90)
    # stoppage_ambiguous rows already have minute == 45 or 90 in the parquet
    minutes_scored: list[int] = sorted(
        int(m) for m in regular["minute"].unique() if 1 <= int(m) <= 90
    )

    # Extra-time minutes scored (> 90)
    extra_minutes: list[int] = sorted(int(m) for m in extra["minute"].unique())

    total_goals = int(len(pdata))
    regular_goals = int(len(regular))
    extra_goals = int(len(extra))

    # Goals per minute (for tooltip / detail)
    minute_goal_counts: dict[str, int] = {}
    for _, row in regular.iterrows():
        m = str(int(row["minute"]))
        minute_goal_counts[m] = minute_goal_counts.get(m, 0) + 1
    for _, row in extra.iterrows():
        m = str(int(row["minute"]))
        minute_goal_counts[m] = minute_goal_counts.get(m, 0) + 1

    # Missing minutes (1–90 not scored in)
    missing_minutes: list[int] = [m for m in range(1, 91) if m not in minutes_scored]

    player_json = {
        "id": pid,
        "name": name,
        "minutesScored": minutes_scored,
        "extraTimeMinutes": extra_minutes,
        "minuteGoalCounts": minute_goal_counts,
        "missingMinutes": missing_minutes,
        "totalGoals": total_goals,
        "regularGoals": regular_goals,
        "extraGoals": extra_goals,
        "minutesScoredCount": len(minutes_scored),
        "dataUpTo": data_up_to,
    }

    out_path = OUT_PLAYERS_DIR / f"{pid}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(player_json, f, separators=(",", ":"))

    index_entries.append({
        "id": pid,
        "name": name,
        "goalCount": total_goals,
    })

# ---------------------------------------------------------------------------
# 5. Write index
# ---------------------------------------------------------------------------
index_json = {
    "dataUpTo": data_up_to,
    "players": sorted(index_entries, key=lambda x: -x["goalCount"]),
}
with open(OUT_INDEX_PATH, "w", encoding="utf-8") as f:
    json.dump(index_json, f, separators=(",", ":"))

print(f"Done! Written {len(player_ids):,} player files + index.json")
print(f"  Players dir: {OUT_PLAYERS_DIR}")
print(f"  Index:       {OUT_INDEX_PATH}")

# ---------------------------------------------------------------------------
# 6. Quick sanity check for Haaland (player_id 418560)
# ---------------------------------------------------------------------------
HAALAND_ID = 418560
haaland_path = OUT_PLAYERS_DIR / f"{HAALAND_ID}.json"
if haaland_path.exists():
    with open(haaland_path) as f:
        h = json.load(f)
    print(f"\nHaaland ({HAALAND_ID}) sanity check:")
    print(f"  name          = {h['name']}")
    print(f"  totalGoals    = {h['totalGoals']}")
    print(f"  minutesScored = {h['minutesScored']}")
    print(f"  missingMinutes (1–90) first 10: {h['missingMinutes'][:10]}")
else:
    print(f"\nWARNING: Haaland file not found at {haaland_path}")
