/**
 * lib/data.ts – single data-access module for Minute Grid.
 *
 * Phase 1: reads from pre-built JSON files in /data/.
 * Phase 2: swap implementations here without touching any other file.
 */

import path from "path";
import fs from "fs";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PlayerIndex {
  id: number;
  name: string;
  goalCount: number;
}

export interface IndexData {
  dataUpTo: string;
  players: PlayerIndex[];
}

export interface PlayerData {
  id: number;
  name: string;
  minutesScored: number[];        // 1–90 that he scored in
  extraTimeMinutes: number[];     // > 90
  minuteGoalCounts: Record<string, number>; // minute string → count
  missingMinutes: number[];       // 1–90 not scored in
  totalGoals: number;
  regularGoals: number;
  extraGoals: number;
  minutesScoredCount: number;
  dataUpTo: string;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

const DATA_DIR = path.join(process.cwd(), "data");

function readJson<T>(filePath: string): T {
  const raw = fs.readFileSync(filePath, "utf-8");
  return JSON.parse(raw) as T;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/** Returns the full search index (id, name, goalCount for every player). */
export function getIndex(): IndexData {
  return readJson<IndexData>(path.join(DATA_DIR, "index.json"));
}

/** Returns the list of all player IDs (for generateStaticParams). */
export function getAllPlayerIds(): number[] {
  const { players } = getIndex();
  return players.map((p) => p.id);
}

/** Returns full data for one player, or null if not found. */
export function getPlayerData(id: number): PlayerData | null {
  const filePath = path.join(DATA_DIR, "players", `${id}.json`);
  if (!fs.existsSync(filePath)) return null;
  return readJson<PlayerData>(filePath);
}
