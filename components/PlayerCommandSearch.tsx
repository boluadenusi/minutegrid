"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { CommandPalette, type CommandItem } from "@/components/motion/command-palette";
import type { IndexData, PlayerIndex } from "@/lib/data";
import { searchPlayerCommands } from "@/lib/player-search";
import Link from "next/link";
import ClubStatus from "@/components/ClubStatus";
import { readRecentPlayers, rememberRecentPlayer, suggestedPlayers } from "@/lib/recent-players";

interface PlayerCommandSearchProps {
  onSelectPlayer: (id: number) => void;
  label: string;
  className: string;
  /** Cmd/Ctrl + this key opens search; "" for none (when several searches share a page). */
  shortcut?: string;
  /** Optional icon shown before the label. */
  icon?: ReactNode;
}

export default function PlayerCommandSearch({ onSelectPlayer, label, className, shortcut = "k", icon }: PlayerCommandSearchProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState<IndexData | null>(null);
  const [error, setError] = useState(false);
  const [recent, setRecent] = useState<number[]>([]);

  useEffect(() => {
    if (!open || index) return;
    const controller = new AbortController();
    fetch("/api/index", { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`Search index request failed: ${response.status}`);
        return response.json() as Promise<IndexData>;
      })
      .then(setIndex)
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        console.error("Could not load player search:", reason);
        setError(true);
      });
    return () => controller.abort();
  }, [open, index]);

  const items = useMemo<CommandItem[]>(() => {
    const players = index?.players ?? [];
    const toItem = (player: PlayerIndex, group?: string): CommandItem => ({
      id: `${group ?? "result"}-${player.id}`,
      label: player.name,
      group,
      detail: <ClubStatus club={player.club} active={player.active} asOf={player.asOf} />,
      badge: <span className="text-xs text-tone-400">
        {player.inWindow === false ? `No goals since ${index?.windowStart}` : `${player.goalCount} goals`}
      </span>,
      onSelect: () => {
        setRecent(rememberRecentPlayer(player.id));
        onSelectPlayer(player.id);
      },
    });
    if (query.trim()) return searchPlayerCommands(players, query).map((player) => toItem(player));
    // Before typing: up to three recent picks, then a few suggestions.
    const byId = new Map(players.map((player) => [player.id, player]));
    const recentPlayers = recent.flatMap((id) => byId.get(id) ?? []);
    const day = Math.floor(Date.parse(index?.windowEnd ?? index?.dataUpTo ?? "1970-01-01") / 86_400_000);
    return [
      ...recentPlayers.map((player) => toItem(player, "Recent")),
      ...suggestedPlayers(players, recentPlayers.map((player) => player.id), day).map((player) => toItem(player, "Suggested")),
    ];
  }, [index, query, recent, onSelectPlayer]);

  const emptyMessage = error ? "Could not load players. Close and reopen search to retry."
    : !index ? "Loading players…" : !query.trim() ? "Type a player name to search." : (
      <>Not in our data. We cover top-flight leagues, major cups and international tournaments.{" "}
        <Link href="/coverage" className="text-scored-400 underline">View coverage</Link>.
      </>
    );

  const changeOpen = (next: boolean) => {
    if (next && !open) {
      setError(false);
      setQuery("");
      setRecent(readRecentPlayers());
    }
    setOpen(next);
  };

  return (
    <>
      <button type="button" className={className} onClick={() => changeOpen(true)}>
        <span className="inline-flex items-center gap-2">{icon}{label}</span>
        {shortcut && (
          <kbd className="rounded border border-tone-700 px-1.5 py-0.5 text-xs text-tone-400">⌘ / Ctrl {shortcut.toUpperCase()}</kbd>
        )}
      </button>
      <CommandPalette
        open={open}
        onOpenChange={changeOpen}
        onQueryChange={setQuery}
        shortcut={shortcut}
        items={items}
        placeholder="Search players"
        emptyMessage={emptyMessage}
        labels={{ dialog: "Search players", list: "Player results" }}
      />
    </>
  );
}
