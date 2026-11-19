/**
 * Players this browser picked from search, newest first (at most MAX_RECENT).
 * Kept in localStorage only: a per-visitor convenience that may be empty or
 * unavailable (private windows, blocked storage), so every access is guarded.
 */
const KEY = "minutegrid:recent-players";
export const MAX_RECENT = 3;

export function readRecentPlayers(): number[] {
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter((id): id is number => Number.isInteger(id)).slice(0, MAX_RECENT) : [];
  } catch {
    return [];
  }
}

export function rememberRecentPlayer(id: number): number[] {
  const next = [id, ...readRecentPlayers().filter((other) => other !== id)].slice(0, MAX_RECENT);
  try {
    window.localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // Storage blocked: search still works, it just won't remember.
  }
  return next;
}

/**
 * A few well-known scorers to try, rotating daily among the top scorers so
 * the list isn't always the same four names.
 */
export function suggestedPlayers<T extends { id: number; goalCount: number; inWindow?: boolean }>(
  players: T[], exclude: number[], day: number, count = 4, pool = 24,
): T[] {
  const top = [...players]
    .filter((player) => player.inWindow !== false && !exclude.includes(player.id))
    .sort((a, b) => b.goalCount - a.goalCount || a.id - b.id)
    .slice(0, pool);
  if (top.length <= count) return top;
  const step = Math.max(1, Math.floor(top.length / count));
  return Array.from({ length: count }, (_, i) => top[(day + i * step) % top.length]);
}
