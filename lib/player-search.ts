import type { PlayerIndex } from "./data";

export function searchPlayerCommands(players: PlayerIndex[], query: string): PlayerIndex[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return [];
  return players.filter((player) => player.name.toLowerCase().includes(normalized)).slice(0, 20);
}
