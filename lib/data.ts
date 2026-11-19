/**
 * lib/data.ts – single data-access module for Minute Grid.
 *
 * Phase 1: reads from pre-built JSON files in /data/.
 * Phase 2: swap implementations here without touching any other file.
 */

import path from "node:path";
import fs from "node:fs";
import { applyWindow, currentWindow, windowedBoards } from "./window";
export { getChains } from "./chains";
export type { Chain } from "./chains";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface GoalDetail {
  date: string;
  opponent: string;
  competition: string;
  club: string;
  /** "espn" for goals from ESPN ("pitchapi" in older data); absent for Transfermarkt history */
  source?: string;
  /** Scored after Transfermarkt's last day (a live update) */
  live?: boolean;
  addedTime?: boolean;
  penalty?: boolean;
}

export interface MinuteGoalDetail {
  count: number;
  firstDate: string | null;
  goals: GoalDetail[];
  /** Date the cell was first filled, when that goal came from live updates */
  gapClosed?: string;
}

export interface ExtraTimeGoalDetail {
  minute: number;
  count: number;
  firstDate: string;
  goals: GoalDetail[];
}

export interface PlayerIndex {
  id: number;
  name: string;
  goalCount: number;
  club?: Club | null;
  active?: boolean;
  asOf?: string;
  /** false when every goal predates the rolling window */
  inWindow?: boolean;
}

export interface Club {
  name: string;
  id: string | null;
  /** Club logo URL (PitchAPI CDN or /images/clubs/...), when collected */
  logo?: string | null;
}

export interface Competition {
  id: string;
  name: string;
  country: string | null;
}

export type CoverageData = Record<"leagues" | "cups" | "superCups" | "uefa" | "international", Competition[]>;

export interface IndexData {
  dataUpTo: string;
  /** First day of the rolling 10-year goal window (YYYY-MM-DD), recomputed every day */
  windowStart?: string;
  /** Last day of the window: today (UTC) */
  windowEnd?: string;
  /** First day of live ESPN updates (the day after Transfermarkt's data ends) */
  liveFrom?: string;
  /** Competition ids that receive live updates */
  liveCompetitions?: string[];
  players: PlayerIndex[];
}

/** Start of the goal window for display; data built before the window existed started in 2012. */
export function windowStartLabel(windowStart?: string): string {
  return windowStart ?? "2012";
}

export interface BoardEntry {
  id: number;
  name: string;
  goals: number;
  missing: number[];
  lastGoalDate: string;
  image?: string | null;
  counts: number[];
  club?: Club | null;
  active?: boolean;
  asOf?: string;
}

export interface GapClosed {
  id: number;
  name: string;
  minute: number;
  date: string;
}

export interface BoardsData {
  complete: BoardEntry[];
  almost: BoardEntry[];
  gapsClosed?: GapClosed[];
  /** YYYY-MM the gapsClosed list covers */
  gapsClosedMonth?: string;
}

export interface PlayerData {
  id: number;
  name: string;
  /** Player photo URL, when collected */
  image?: string | null;
  club?: Club | null;
  active?: boolean;
  asOf?: string;
  minutes: Record<string, MinuteGoalDetail>; // 1–90 { count, firstDate, goals }
  extraTime: ExtraTimeGoalDetail[];          // minute > 90 list of { minute, count, firstDate, goals }
  minutesScored: number[];                   // 1–90 that he scored in
  extraTimeMinutes: number[];                // > 90
  minuteGoalCounts: Record<string, number>;  // minute string → count
  missingMinutes: number[];                  // 1–90 not scored in
  totalGoals: number;
  regularGoals: number;
  extraGoals: number;
  minutesScoredCount: number;
  /** Filled from index.json when the player file has none (prep.py leaves it out so files only change with goals) */
  dataUpTo: string;
  windowStart?: string;
  /** Last day of the window: today (UTC) */
  windowEnd?: string;
  inWindow?: boolean;
}

export interface LeagueSummary {
  id: string;
  name: string;
  country: string | null;
  /** League logo URL, when collected */
  logo?: string | null;
  clubCount: number;
  playerCount: number;
}

export interface LeaguePlayer {
  id: number;
  name: string;
  /** goals in the rolling window */
  goals: number;
  /** minutes (1–90) scored in */
  minutes: number;
  image?: string | null;
}

export interface LeagueClub {
  id: string | null;
  name: string;
  logo?: string | null;
  players: LeaguePlayer[];
}

export interface LeagueDetail {
  id: string;
  name: string;
  country: string | null;
  clubs: LeagueClub[];
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

const DATA_DIR = path.resolve(process.cwd(), "data");

function readJson<T>(filePath: string): T {
  const raw = fs.readFileSync(filePath, "utf-8");
  return JSON.parse(raw) as T;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/** Returns the full search index (id, name, goalCount for every player). */
export function getIndex(): IndexData {
  const indexPath = path.resolve(DATA_DIR, "index.json");
  const window = currentWindow();
  return { ...readJson<IndexData>(indexPath), windowStart: window.start, windowEnd: window.end };
}

/** Home-page leaderboards, re-checked against today's 10-year window. */
export function getBoards(): BoardsData {
  return windowedBoards(readJson<BoardsData>(path.resolve(DATA_DIR, "boards.json")), getPlayerData);
}

export function getCoverage(): CoverageData {
  const filePath = path.resolve(DATA_DIR, "coverage.json");
  if (!fs.existsSync(filePath)) {
    throw new Error("Missing data/coverage.json. Run python scripts/prep.py first.");
  }
  return readJson<CoverageData>(filePath);
}

/** League summaries for the home-page explorer; empty until prep.py has written them. */
export function getLeagues(): LeagueSummary[] {
  const filePath = path.resolve(DATA_DIR, "leagues.json");
  if (!fs.existsSync(filePath)) return [];
  return readJson<{ leagues: LeagueSummary[] }>(filePath).leagues;
}

/** One league's clubs and players, or null for an unknown league id. */
export function getLeague(id: string): LeagueDetail | null {
  if (!/^[A-Za-z0-9]+$/.test(id)) return null;
  const filePath = path.resolve(DATA_DIR, "leagues", `${id}.json`);
  if (!fs.existsSync(filePath)) return null;
  return readJson<LeagueDetail>(filePath);
}

/** Returns the list of all player IDs (for generateStaticParams). */
export function getAllPlayerIds(): number[] {
  const { players } = getIndex();
  return players.map((p) => p.id);
}

/** Returns full data for one player, or null if not found. */
export function getPlayerData(id: number): PlayerData | null {
  const filePath = path.resolve(DATA_DIR, "players", `${String(id)}.json`);
  if (!fs.existsSync(filePath)) return null;
  // Player files are written by prep.py; the window moves on every day, so
  // goals that have since fallen out of it are dropped here.
  const player = readJson<PlayerData>(filePath);
  if (!player.dataUpTo) player.dataUpTo = readJson<IndexData>(path.resolve(DATA_DIR, "index.json")).dataUpTo;
  return applyWindow(player, currentWindow());
}
