import type { GoalDetail, PlayerData } from "./data";

export interface LastGoal extends GoalDetail {
  minute: number;
  extraTime: boolean;
}

/**
 * The player's most recent goal in the data: latest date, and the latest
 * minute when several goals share that date. Null when the player has no
 * goals (e.g. all of them fall before the rolling window).
 */
export function getLastGoal(player: Pick<PlayerData, "minutes" | "extraTime">): LastGoal | null {
  let last: LastGoal | null = null;
  const consider = (goal: GoalDetail, minute: number, extraTime: boolean) => {
    if (!goal.date) return;
    if (!last || goal.date > last.date || (goal.date === last.date && minute > last.minute)) {
      last = { ...goal, minute, extraTime };
    }
  };
  for (const [minute, detail] of Object.entries(player.minutes)) {
    for (const goal of detail.goals) consider(goal, Number(minute), false);
  }
  for (const detail of player.extraTime) {
    for (const goal of detail.goals) consider(goal, detail.minute, true);
  }
  return last;
}

/** "81'", "90+'" for added time, "105' (ET)" for extra time. */
export function formatGoalMinute(goal: Pick<LastGoal, "minute" | "extraTime" | "addedTime">): string {
  if (goal.extraTime) return `${goal.minute}' (ET)`;
  return goal.addedTime ? `${goal.minute}+'` : `${goal.minute}'`;
}
