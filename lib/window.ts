import type { BoardEntry, BoardsData, ExtraTimeGoalDetail, GoalDetail, MinuteGoalDetail, PlayerData } from "./data";

/** Minute Grid only counts goals from the last WINDOW_YEARS years, ending today. */
export const WINDOW_YEARS = 10;

/** Today as YYYY-MM-DD in UTC, so every server and visitor agrees on the day. */
export function todayIso(now: Date = new Date()): string {
  return now.toISOString().slice(0, 10);
}

/** Same calendar day WINDOW_YEARS years before `today`; 29 February falls back to 28 February. */
export function windowStartFor(today: string): string {
  const [year, month, day] = today.split("-").map(Number);
  const start = new Date(Date.UTC(year - WINDOW_YEARS, month - 1, day));
  if (start.getUTCMonth() !== month - 1) start.setUTCDate(0); // 29 Feb -> 28 Feb
  return start.toISOString().slice(0, 10);
}

export interface GoalWindow {
  start: string;
  end: string;
}

export function currentWindow(now: Date = new Date()): GoalWindow {
  const end = todayIso(now);
  return { start: windowStartFor(end), end };
}

const inWindow = (goal: GoalDetail, window: GoalWindow) => goal.date >= window.start && goal.date <= window.end;

function firstLiveDate(goals: GoalDetail[]): string | undefined {
  const first = goals.reduce<GoalDetail | null>((best, goal) => (!best || goal.date < best.date ? goal : best), null);
  return first?.live || first?.source === "pitchapi" ? first.date : undefined;
}

/**
 * Re-applies the rolling window to a player file built on an earlier day:
 * goals that have since fallen out of the window are removed and every
 * count, list and flag is recomputed from what is left.
 */
export function applyWindow(player: PlayerData, window: GoalWindow): PlayerData {
  const minutes: Record<string, MinuteGoalDetail> = {};
  const minuteGoalCounts: Record<string, number> = {};
  const minutesScored: number[] = [];
  const missingMinutes: number[] = [];
  let regularGoals = 0;
  for (let minute = 1; minute <= 90; minute++) {
    const key = String(minute);
    const goals = (player.minutes[key]?.goals ?? []).filter((goal) => inWindow(goal, window));
    const detail: MinuteGoalDetail = { count: goals.length, firstDate: goals[0]?.date ?? null, goals };
    const closed = firstLiveDate(goals);
    if (closed) detail.gapClosed = closed;
    minutes[key] = detail;
    if (goals.length) {
      minutesScored.push(minute);
      minuteGoalCounts[key] = goals.length;
      regularGoals += goals.length;
    } else {
      missingMinutes.push(minute);
    }
  }
  const extraTime: ExtraTimeGoalDetail[] = [];
  let extraGoals = 0;
  for (const detail of player.extraTime) {
    const goals = detail.goals.filter((goal) => inWindow(goal, window));
    if (!goals.length) continue;
    extraTime.push({ ...detail, count: goals.length, firstDate: goals[0].date, goals });
    minuteGoalCounts[String(detail.minute)] = goals.length;
    extraGoals += goals.length;
  }
  const totalGoals = regularGoals + extraGoals;
  return {
    ...player,
    minutes,
    extraTime,
    minutesScored,
    extraTimeMinutes: extraTime.map((detail) => detail.minute),
    minuteGoalCounts,
    missingMinutes,
    totalGoals,
    regularGoals,
    extraGoals,
    minutesScoredCount: minutesScored.length,
    windowStart: window.start,
    windowEnd: window.end,
    inWindow: totalGoals > 0,
  };
}

/** A board entry recomputed from the player's windowed data. */
export function boardEntryFor(entry: BoardEntry, player: PlayerData): BoardEntry {
  const dates = [
    ...Object.values(player.minutes).flatMap((detail) => detail.goals),
    ...player.extraTime.flatMap((detail) => detail.goals),
  ].map((goal) => goal.date);
  return {
    ...entry,
    goals: player.totalGoals,
    missing: player.missingMinutes,
    lastGoalDate: dates.reduce((last, date) => (date > last ? date : last), ""),
    counts: Array.from({ length: 90 }, (_, index) => player.minutes[String(index + 1)]?.count ?? 0),
  };
}

/**
 * Rebuilds the boards for today's window. Only players already on a board
 * can still qualify (the window only ever drops old goals; new goals arrive
 * with the next prep.py run), so loading those few player files is enough.
 */
/** "Almost complete": 1 to this many minutes missing (scripts/boards.py uses the same). */
export const ALMOST_MAX = 5;

export function windowedBoards(boards: BoardsData, load: (id: number) => PlayerData | null): BoardsData {
  const entries = [...boards.complete, ...boards.almost].flatMap((entry) => {
    const player = load(entry.id);
    return player ? [boardEntryFor(entry, player)] : [];
  });
  const byGoals = (a: BoardEntry, b: BoardEntry) => b.goals - a.goals || a.id - b.id;
  return {
    ...boards,
    complete: entries.filter((entry) => entry.missing.length === 0).sort(byGoals),
    almost: entries
      .filter((entry) => entry.missing.length >= 1 && entry.missing.length <= ALMOST_MAX)
      .sort((a, b) => a.missing.length - b.missing.length || byGoals(a, b)),
  };
}
