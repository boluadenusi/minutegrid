"use client";

import PlayerCommandSearch from "@/components/PlayerCommandSearch";

interface PlayerSearchBoxProps {
  onSelectPlayer: (id: number) => void;
  currentPlayerId: number;
}

export default function PlayerSearchBox({ onSelectPlayer, currentPlayerId }: PlayerSearchBoxProps) {
  return <PlayerCommandSearch
    onSelectPlayer={(id) => { if (id !== currentPlayerId) onSelectPlayer(id); }}
    label="Morph to another player…"
    className="flex w-full max-w-xs items-center justify-between gap-2 rounded-lg border border-tone-700 bg-tone-900 px-3 py-2 text-left text-xs text-tone-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-scored-400 hover:border-scored-500"
  />;
}
