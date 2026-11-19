"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { PlayerData } from "@/lib/data";
import { compareMinutes, type MinuteOwner } from "@/lib/compare";
import { formatCompetition, formatGoalDate } from "@/lib/goal-format";
import { getLastGoal } from "@/lib/last-goal";
import Avatar from "@/components/Avatar";
import ClubStatus from "@/components/ClubStatus";
import PlayerCommandSearch from "@/components/PlayerCommandSearch";
import { ArrowLeftRight, Search, UserRoundPlus } from "lucide-react";

type Side = "a" | "b";

interface CompareViewProps {
  initialA: PlayerData | null;
  initialB: PlayerData | null;
}

const surname = (name: string) => name.split(/\s+/).filter(Boolean).at(-1) ?? name;

function compareUrl(a: PlayerData | null, b: PlayerData | null): string {
  const params = new URLSearchParams();
  if (a) params.set("a", String(a.id));
  if (b) params.set("b", String(b.id));
  const query = params.toString();
  return query ? `/compare?${query}` : "/compare";
}

function PlayerSlot({ side, player, other, loading, onPick }: {
  side: Side;
  player: PlayerData | null;
  other: PlayerData | null;
  loading: boolean;
  onPick: (id: number) => void;
}) {
  const last = player ? getLastGoal(player) : null;
  const label = side === "a" ? "first" : "second";
  return (
    <section className={`compare-slot compare-slot-${side}`} aria-label={player ? player.name : `Pick the ${label} player`}>
      {player ? (
        <>
          <div className="flex items-center gap-3">
            <Avatar key={player.id} src={player.image} name={player.name} size={56} />
            <div className="min-w-0">
              <h2 className="truncate text-lg font-bold text-foreground">
                <Link href={`/player/${player.id}`} className="hover:underline">{player.name}</Link>
              </h2>
              <ClubStatus club={player.club} active={player.active} asOf={player.asOf} />
            </div>
          </div>
          <dl className="compare-stats">
            <div><dt>Minutes</dt><dd>{player.minutesScoredCount}/90</dd></div>
            <div><dt>Goals</dt><dd>{player.totalGoals}</dd></div>
            <div><dt>Extra time</dt><dd>{player.extraGoals}</dd></div>
          </dl>
          <p className="text-xs text-tone-400">
            {last ? <>Last goal <time dateTime={last.date}>{formatGoalDate(last.date)}</time></> : "No goals in the last 10 years"}
          </p>
        </>
      ) : (
        <p className="text-sm text-tone-400">{loading ? "Loading player…" : `Pick the ${label} player to compare.`}</p>
      )}
      <PlayerCommandSearch
        onSelectPlayer={(id) => { if (id !== player?.id && id !== other?.id) onPick(id); }}
        label={player ? "Change player" : `Add ${label} player`}
        shortcut={side === "a" ? "k" : ""}
        icon={player ? <Search size={16} aria-hidden="true" /> : <UserRoundPlus size={18} aria-hidden="true" />}
        className={player ? "compare-pick compare-pick-change" : "compare-pick compare-pick-add"}
      />
    </section>
  );
}

function GoalsAt({ player, minute }: { player: PlayerData; minute: number }) {
  const goals = player.minutes[String(minute)]?.goals ?? [];
  return (
    <div className="space-y-2">
      <h4 className="text-sm font-semibold text-foreground">
        {player.name} · {goals.length} goal{goals.length === 1 ? "" : "s"}
      </h4>
      {goals.length === 0 ? (
        <p className="text-xs text-tone-400">No goal in minute {minute} yet.</p>
      ) : (
        <ul className="space-y-1 text-xs text-tone-400">
          {goals.map((goal, index) => (
            <li key={`${goal.date}-${index}`}>
              <time dateTime={goal.date} className="text-foreground">{formatGoalDate(goal.date)}</time>
              {goal.opponent && goal.opponent !== "Unknown" ? ` vs ${goal.opponent}` : ""} · {formatCompetition(goal.competition)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const OWNER_TEXT: Record<MinuteOwner, (a: string, b: string) => string> = {
  both: () => "both scored",
  a: (a) => `only ${a} scored`,
  b: (_a, b) => `only ${b} scored`,
  none: () => "neither scored",
};

export default function CompareView({ initialA, initialB }: CompareViewProps) {
  const router = useRouter();
  const [players, setPlayers] = useState<{ a: PlayerData | null; b: PlayerData | null }>({ a: initialA, b: initialB });
  const [loading, setLoading] = useState<Side | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [minute, setMinute] = useState<number | null>(null);
  const { a, b } = players;

  const comparison = useMemo(
    () => (a && b ? compareMinutes(a.minuteGoalCounts, b.minuteGoalCounts) : null),
    [a, b]
  );

  const pick = async (side: Side, id: number) => {
    setLoading(side);
    setError(null);
    try {
      const response = await fetch(`/api/player/${id}`);
      if (!response.ok) throw new Error(`Player request failed: ${response.status}`);
      const player = (await response.json()) as PlayerData;
      const next = { ...players, [side]: player };
      setPlayers(next);
      router.replace(compareUrl(next.a, next.b), { scroll: false });
    } catch (reason) {
      console.error("Could not load player:", reason);
      setError("Could not load that player. Try again.");
    } finally {
      setLoading(null);
    }
  };

  const swap = () => {
    const next = { a: b, b: a };
    setPlayers(next);
    router.replace(compareUrl(next.a, next.b), { scroll: false });
  };

  const nameA = a ? surname(a.name) : "A";
  const nameB = b ? surname(b.name) : "B";
  const selected = comparison && minute ? comparison.minutes[minute - 1] : null;

  return (
    <main className="mx-auto max-w-3xl space-y-6 px-4 py-8">
      <Link href="/" className="text-xs text-tone-500 hover:text-foreground">← Back to all players</Link>
      <header className="space-y-1">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Compare players</h1>
        <p className="text-sm text-tone-400">See which minutes each player has scored in, side by side.</p>
      </header>

      <div className="compare-slots">
        <PlayerSlot side="a" player={a} other={b} loading={loading === "a"} onPick={(id) => pick("a", id)} />
        <button type="button" className="compare-swap" onClick={swap} disabled={!a || !b}
          aria-label="Swap players" title="Swap players">
          <ArrowLeftRight size={18} aria-hidden="true" />
        </button>
        <PlayerSlot side="b" player={b} other={a} loading={loading === "b"} onPick={(id) => pick("b", id)} />
      </div>
      {error && <p role="alert" className="text-sm text-gap-400">{error}</p>}

      {a && b && comparison && (
        <section className="space-y-4" aria-label="Minute comparison">
          <ul className="compare-summary">
            <li><span className="compare-swatch compare-cell-both" aria-hidden="true" />Both <strong>{comparison.both.length}</strong></li>
            <li><span className="compare-swatch compare-cell-a" aria-hidden="true" />Only {nameA} <strong>{comparison.onlyA.length}</strong></li>
            <li><span className="compare-swatch compare-cell-b" aria-hidden="true" />Only {nameB} <strong>{comparison.onlyB.length}</strong></li>
            <li><span className="compare-swatch compare-cell-none" aria-hidden="true" />Neither <strong>{comparison.neither.length}</strong></li>
          </ul>

          <div className="compare-grid" role="group" aria-label="Minutes 1 to 90">
            {comparison.minutes.map((cell) => (
              <button
                key={cell.minute}
                type="button"
                className={`compare-cell compare-cell-${cell.owner} ${minute === cell.minute ? "compare-cell-selected" : ""}`}
                aria-pressed={minute === cell.minute}
                aria-label={`Minute ${cell.minute}: ${OWNER_TEXT[cell.owner](nameA, nameB)}. ${nameA} ${cell.a}, ${nameB} ${cell.b}`}
                title={`${cell.minute}': ${nameA} ${cell.a} · ${nameB} ${cell.b}`}
                onClick={() => setMinute(minute === cell.minute ? null : cell.minute)}
              >
                {cell.minute}
              </button>
            ))}
          </div>
          <p className="text-xs text-tone-500">Minutes 45 and 90 include added time. Select a minute to see both players&apos; goals.</p>

          {selected && (
            <div className="compare-detail" aria-live="polite">
              <h3 className="text-base font-semibold text-foreground">
                Minute {selected.minute} · {OWNER_TEXT[selected.owner](nameA, nameB)}
              </h3>
              <div className="grid gap-4 sm:grid-cols-2">
                <GoalsAt player={a} minute={selected.minute} />
                <GoalsAt player={b} minute={selected.minute} />
              </div>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
