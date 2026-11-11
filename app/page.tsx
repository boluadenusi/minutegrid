"use client";

import { useState, useMemo, useEffect } from "react";
import Link from "next/link";

interface PlayerIndex {
  id: number;
  name: string;
  goalCount: number;
}

interface IndexData {
  dataUpTo: string;
  players: PlayerIndex[];
}

export default function SearchPage() {
  const [indexData, setIndexData] = useState<IndexData | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    fetch("/api/index")
      .then((r) => r.json())
      .then(setIndexData);
  }, []);

  const results = useMemo(() => {
    if (!indexData) return [];
    const q = query.trim().toLowerCase();
    if (!q) return indexData.players.slice(0, 20);
    return indexData.players
      .filter((p) => p.name.toLowerCase().includes(q))
      .slice(0, 20);
  }, [query, indexData]);

  return (
    <main className="max-w-2xl mx-auto px-4 py-16">
      {/* Header */}
      <div className="mb-10 text-center">
        <h1 className="text-4xl font-bold tracking-tight text-white mb-2">
          Minute Grid
        </h1>
        <p className="text-zinc-400 text-sm">
          Which minutes did your player score in?
        </p>
      </div>

      {/* Search box */}
      <div className="relative mb-6">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search player…"
          className="w-full rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 text-white placeholder-zinc-500 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition"
          autoFocus
        />
        {query && (
          <button
            onClick={() => setQuery("")}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-white"
          >
            ✕
          </button>
        )}
      </div>

      {/* Results */}
      {!indexData ? (
        <p className="text-zinc-500 text-center py-10">Loading…</p>
      ) : (
        <ul className="space-y-2">
          {results.map((player) => (
            <li key={player.id}>
              <Link
                href={`/player/${player.id}`}
                className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-3 hover:border-emerald-600 hover:bg-zinc-800 transition"
              >
                <span className="font-medium text-white">{player.name}</span>
                <span className="text-xs text-zinc-400">
                  {player.goalCount} goal{player.goalCount !== 1 ? "s" : ""}
                </span>
              </Link>
            </li>
          ))}
          {results.length === 0 && (
            <p className="text-zinc-500 text-center py-6">No players found.</p>
          )}
        </ul>
      )}

      {indexData && (
        <p className="mt-8 text-center text-xs text-zinc-600">
          Data up to {indexData.dataUpTo} · {indexData.players.length.toLocaleString()} players
        </p>
      )}
    </main>
  );
}
