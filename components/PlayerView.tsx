"use client";

import { useState, useEffect, useCallback, useMemo, useTransition } from "react";
import Link from "next/link";
import type { PlayerData } from "@/lib/data";
import TimelineStrip from "@/components/TimelineStrip";
import GoalDetailPanel from "@/components/GoalDetailPanel";
import PlayerSearchBox from "@/components/PlayerSearchBox";
import ChainView from "@/components/ChainView";
import ExtraTimeStrip from "@/components/ExtraTimeStrip";
import ClubStatus from "@/components/ClubStatus";
import Avatar from "@/components/Avatar";
import { GitCompareArrows } from "lucide-react";
import { getChains } from "@/lib/chains";
import { formatGoalMinute, getLastGoal } from "@/lib/last-goal";
import { formatCompetition, formatGoalDate } from "@/lib/goal-format";

interface PlayerViewProps {
  initialPlayer: PlayerData;
  initialMinute: number;
}

export default function PlayerView({ initialPlayer, initialMinute }: PlayerViewProps) {
  const [player, setPlayer] = useState<PlayerData>(initialPlayer);
  const [activeMinute, setActiveMinute] = useState<number | null>(null);
  const [pinnedMinute, setPinnedMinute] = useState<number | null>(null);
  const [selectedMinute, setSelectedMinute] = useState<number>(initialMinute);
  const [isMorphed, setIsMorphed] = useState<boolean>(false);
  const [isCrossFading, setIsCrossFading] = useState<boolean>(false);
  const [reducedMotion, setReducedMotion] = useState<boolean>(false);
  const [, startTransition] = useTransition();

  // Detect prefers-reduced-motion
  useEffect(() => {
    if (typeof window === "undefined") return;
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(media.matches);
    const handler = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    media.addEventListener("change", handler);
    return () => media.removeEventListener("change", handler);
  }, []);

  // Fetch and morph to player
  const morphToPlayer = useCallback(
    async (id: number, shouldPushState = true) => {
      try {
        if (!reducedMotion) {
          setIsCrossFading(true);
        }

        const res = await fetch(`/api/player/${id}`);
        if (!res.ok) throw new Error("Failed to load player");
        const newPlayerData: PlayerData = await res.json();

        startTransition(() => {
          setPlayer(newPlayerData);
          setIsMorphed(true);
        });

        // Update URL and document title
        if (shouldPushState) {
          const url = new URL(window.location.href);
          url.pathname = `/player/${id}`;
          window.history.pushState(
            { playerId: id },
            "",
            url.pathname + url.search + url.hash
          );
        }
        document.title = `${newPlayerData.name} | Minute Grid`;

        if (!reducedMotion) {
          setTimeout(() => {
            setIsCrossFading(false);
          }, 300);
        } else {
          setIsCrossFading(false);
        }
      } catch (err) {
        console.error("Error morphing player:", err);
        setIsCrossFading(false);
      }
    },
    [reducedMotion]
  );

  // Handle browser back/forward buttons (popstate)
  useEffect(() => {
    const handlePopState = () => {
      setActiveMinute(null);
      setPinnedMinute(null);
      const match = window.location.pathname.match(/\/player\/(\d+)/);
      if (match && match[1]) {
        const targetId = Number(match[1]);
        if (targetId && targetId !== player.id) {
          morphToPlayer(targetId, false);
        }
      }
    };

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [player.id, morphToPlayer]);

  // Goals for selected minute
  const minuteData = player.minutes[String(selectedMinute)];
  const selectedGoals = minuteData?.goals ?? [];
  const selectedCount = minuteData?.count ?? 0;
  const isSpecial = selectedMinute === 45 || selectedMinute === 90;
  const chains = useMemo(() => getChains(player.minuteGoalCounts), [player.minuteGoalCounts]);
  const gapsClosed = useMemo(() => Object.fromEntries(
    Object.entries(player.minutes)
      .filter(([, detail]) => detail.gapClosed)
      .map(([minute, detail]) => [minute, detail.gapClosed as string])
  ), [player.minutes]);
  const lastGoal = useMemo(() => getLastGoal(player), [player]);
  const longest = chains.reduce<(typeof chains)[number] | null>(
    (best, chain) => !best || chain.length > best.length ? chain : best,
    null
  );
  const highlightedMinute = activeMinute ?? pinnedMinute;
  const shownMinute = highlightedMinute ?? selectedMinute;
  const shownChain = chains.find((chain) => shownMinute >= chain.start && shownMinute <= chain.end);

  return (
    <main className="max-w-3xl mx-auto px-4 py-8 space-y-6">
      {/* Top Bar: Back Link & In-Page Player Search Box */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <Link
          href="/"
          className="text-xs text-tone-500 hover:text-foreground transition flex items-center gap-1.5"
        >
          <span>←</span> Back to all players
        </Link>
        <Link
          href={`/compare?a=${player.id}`}
          className="compare-button compare-button-sm self-start sm:ml-auto sm:mr-1 sm:self-auto"
          aria-label={`Compare ${player.name} with another player`}
        >
          <GitCompareArrows size={16} aria-hidden="true" />
          Compare
        </Link>

        {/* Feature 4: Search box on player page for instant morphing */}
        <PlayerSearchBox
          onSelectPlayer={(id) => morphToPlayer(id, true)}
          currentPlayerId={player.id}
        />
      </div>

      {/* Player Header (Cross-fades on morph) */}
      <div
        className={`transition-opacity duration-300 ${
          isCrossFading ? "opacity-30" : "opacity-100"
        }`}
      >
        <div className="flex items-center gap-4 mb-2">
          <Avatar key={player.id} src={player.image} name={player.name} size={72} />
          <div className="min-w-0">
            <h1 className="text-3xl font-bold text-foreground mb-1 tracking-tight">
              {player.name}
            </h1>
            <ClubStatus club={player.club} active={player.active} asOf={player.asOf} />
          </div>
        </div>
        <div className="flex flex-wrap gap-4 text-sm text-tone-400">
          <span>
            <span className="text-foreground font-semibold">{player.totalGoals}</span> total goals
          </span>
          <span>
            <span className="text-foreground font-semibold">{player.minutesScoredCount}</span> of 90 minutes
          </span>
          {player.extraGoals > 0 && (
            <span>
              <span className="text-extra-400 font-semibold">{player.extraGoals}</span> in extra time
            </span>
          )}
          <span className="text-tone-600" title={`Newest goal in the data: ${player.dataUpTo}`}>
            Goals from {player.windowStart ?? "2012"} to {player.windowEnd ?? player.dataUpTo}
          </span>
        </div>
        {lastGoal && (
          <p className="mt-2 text-sm text-tone-400">
            Last goal{" "}
            <time dateTime={lastGoal.date} className="text-foreground font-medium">{formatGoalDate(lastGoal.date)}</time>
            {" · "}
            {lastGoal.extraTime ? (
              <span className="text-extra-400">{formatGoalMinute(lastGoal)}</span>
            ) : (
              <button
                type="button"
                className="text-foreground underline decoration-tone-600 underline-offset-2 hover:decoration-foreground"
                aria-label={`Show minute ${lastGoal.minute}`}
                onClick={() => { setSelectedMinute(lastGoal.minute); setPinnedMinute(lastGoal.minute); }}
              >
                {formatGoalMinute(lastGoal)}
              </button>
            )}
            {lastGoal.penalty ? " (pen)" : ""}
            {lastGoal.opponent && lastGoal.opponent !== "Unknown" ? ` vs ${lastGoal.opponent}` : ""}
            {" · "}{formatCompetition(lastGoal.competition)}
            {lastGoal.club && lastGoal.club !== "Unknown" && lastGoal.club !== player.club?.name
              ? ` · for ${lastGoal.club}` : ""}
          </p>
        )}
        {player.inWindow === false && (
          <p className="mt-2 text-sm text-tone-400">
            No goals since {player.windowStart}. Minute Grid counts goals from the last 10 years only.
          </p>
        )}
      </div>

      <ChainView
        counts={player.minuteGoalCounts}
        chains={chains}
        selectedMinute={selectedMinute}
        activeMinute={highlightedMinute}
        onSelectMinute={(minute) => {
          setSelectedMinute(minute);
          setPinnedMinute(minute);
        }}
        onActiveMinute={setActiveMinute}
        isMorphed={isMorphed}
        isCrossFading={isCrossFading}
        gapsClosed={gapsClosed}
      />

      <ExtraTimeStrip minutes={player.extraTimeMinutes} counts={player.minuteGoalCounts} details={player.extraTime} />

      {/* Feature 3: Scrub the Clock (Timeline Strip & Histogram) */}
      <TimelineStrip
        minuteGoalCounts={player.minuteGoalCounts}
        selectedMinute={selectedMinute}
        onSelectMinute={(m) => { setSelectedMinute(m); setPinnedMinute(null); }}
        reducedMotion={reducedMotion}
      />

      {/* Feature 3: Goal Detail Panel for Selected Minute (Cross-fades on minute change or morph) */}
      <div
        className={`transition-opacity duration-300 ${
          isCrossFading ? "opacity-30" : "opacity-100"
        }`}
      >
        <div className="mb-3 rounded-xl border border-scored-500/20 bg-tone-900 px-4 py-3" aria-live="polite">
            {shownChain ? (
              <p className="text-sm text-tone-300">
                <strong className="text-scored-400">Minutes {shownChain.start} to {shownChain.end}</strong>
                {" · "}{shownChain.length} minute{shownChain.length === 1 ? "" : "s"} long
                {" · "}{shownChain.goals} goal{shownChain.goals === 1 ? "" : "s"}
              </p>
            ) : <p className="text-sm text-gap-300">Minute {shownMinute} is a gap and does not belong to a chain.</p>}
        </div>
        <GoalDetailPanel
          minute={selectedMinute}
          count={selectedCount}
          goals={selectedGoals}
          isSpecial={isSpecial}
        />
      </div>

      {/* Stats Cards */}
      <div
        className={`grid grid-cols-2 gap-3 sm:grid-cols-3 transition-opacity duration-300 ${
          isCrossFading ? "opacity-30" : "opacity-100"
        }`}
      >
        <StatCard label="Separate chains" value={chains.length} />
        <StatCard label="Longest chain" value={longest ? `${longest.length} minutes` : "None"}
          sub={longest ? `Minutes ${longest.start} to ${longest.end}, ${longest.length} long` : "No scored minutes"} />
        <StatCard label="Minutes scored" value={`${chains.reduce((sum, chain) => sum + chain.length, 0)} / 90`} />
      </div>

      {/* Missing minutes list */}
      {player.missingMinutes.length > 0 && (
        <section
          className={`transition-opacity duration-300 ${
            isCrossFading ? "opacity-30" : "opacity-100"
          }`}
        >
          <h2 className="text-xs font-semibold uppercase tracking-wider text-tone-500 mb-2">
            Minutes never scored ({player.missingMinutes.length})
          </h2>
          <div className="flex flex-wrap gap-1.5">
            {player.missingMinutes.map((m) => (
              <button
                key={m}
                onClick={() => { setSelectedMinute(m); setPinnedMinute(null); }}
                className={`rounded px-2 py-0.5 text-xs font-mono transition cursor-pointer ${
                  m === selectedMinute
                    ? "bg-gap-500 text-tone-950 font-bold ring-2 ring-gap-300"
                    : "bg-tone-800 text-tone-400 hover:bg-tone-700 hover:text-foreground"
                }`}
                title={`Jump playhead to minute ${m}`}
              >
                {m}′
              </button>
            ))}
          </div>
        </section>
      )}

      {/* Legend */}
      <div className="flex flex-wrap gap-4 text-xs text-tone-500 pt-2 border-t border-tone-800/80">
        <LegendItem color="bg-scored-500" label="Scored" />
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded bg-tone-800 ring-2 ring-gap-400" />
          Gap minute (never scored)
        </span>
        <LegendItem color="bg-extra-600" label="Extra time goal" />
        <span className="flex items-center gap-1.5">
          <span className="inline-flex h-3 w-3 items-center justify-center rounded bg-scored-500 ring-2 ring-gap-400 text-[6px]" />
          Minute 45 or 90 (incl. stoppage time)
        </span>
      </div>
    </main>
  );
}

function StatCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="rounded-xl border border-tone-800 bg-tone-900 px-4 py-3">
      <p className="text-xs text-tone-500 mb-1">{label}</p>
      <p className="text-xl font-bold text-foreground font-mono">{value}</p>
      {sub && <p className="text-xs text-tone-600 mt-0.5">{sub}</p>}
    </div>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`inline-block h-3 w-3 rounded ${color}`} />
      {label}
    </span>
  );
}
