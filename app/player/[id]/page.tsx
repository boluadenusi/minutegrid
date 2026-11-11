import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { getAllPlayerIds, getPlayerData } from "@/lib/data";
import MinuteGrid from "@/components/MinuteGrid";
import Link from "next/link";

interface Props {
  params: Promise<{ id: string }>;
}

// ---------------------------------------------------------------------------
// Static generation
// ---------------------------------------------------------------------------
export async function generateStaticParams() {
  const ids = getAllPlayerIds();
  return ids.map((id) => ({ id: String(id) }));
}

// ---------------------------------------------------------------------------
// Metadata / link previews
// ---------------------------------------------------------------------------
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const player = getPlayerData(Number(id));
  if (!player) return { title: "Player not found | Minute Grid" };

  const description = `${player.name} has scored in ${player.minutesScoredCount} of 90 minutes · ${player.totalGoals} total goals`;
  const ogImageUrl = `/player/${id}/og`;

  return {
    title: `${player.name} | Minute Grid`,
    description,
    openGraph: {
      title: `${player.name} | Minute Grid`,
      description,
      images: [{ url: ogImageUrl, width: 1200, height: 630 }],
    },
    twitter: {
      card: "summary_large_image",
      title: `${player.name} | Minute Grid`,
      description,
      images: [ogImageUrl],
    },
  };
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default async function PlayerPage({ params }: Props) {
  const { id } = await params;
  const player = getPlayerData(Number(id));
  if (!player) notFound();

  return (
    <main className="max-w-3xl mx-auto px-4 py-10">
      {/* Back */}
      <Link
        href="/"
        className="text-sm text-zinc-500 hover:text-white transition mb-6 inline-block"
      >
        ← Search
      </Link>

      {/* Player header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-1">{player.name}</h1>
        <div className="flex flex-wrap gap-4 text-sm text-zinc-400">
          <span>
            <span className="text-white font-semibold">{player.totalGoals}</span> total goals
          </span>
          <span>
            <span className="text-white font-semibold">{player.minutesScoredCount}</span> of 90 minutes
          </span>
          {player.extraGoals > 0 && (
            <span>
              <span className="text-violet-400 font-semibold">{player.extraGoals}</span> in extra time
            </span>
          )}
          <span className="text-zinc-600">Data up to {player.dataUpTo}</span>
        </div>
      </div>

      {/* Grid */}
      <MinuteGrid
        minutesScored={player.minutesScored}
        minuteGoalCounts={player.minuteGoalCounts}
        extraTimeMinutes={player.extraTimeMinutes}
      />

      {/* Stats strip */}
      <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <StatCard label="Minutes scored" value={`${player.minutesScoredCount} / 90`} />
        <StatCard label="Total goals" value={player.totalGoals} />
        <StatCard
          label="Silent minutes"
          value={90 - player.minutesScoredCount}
          sub="(never scored)"
        />
      </div>

      {/* Missing minutes */}
      {player.missingMinutes.length > 0 && (
        <section className="mt-8">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 mb-3">
            Minutes never scored ({player.missingMinutes.length})
          </h2>
          <div className="flex flex-wrap gap-1.5">
            {player.missingMinutes.map((m) => (
              <span
                key={m}
                className="rounded bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400 font-mono"
              >
                {m}′
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Legend */}
      <div className="mt-10 flex flex-wrap gap-4 text-xs text-zinc-500">
        <LegendItem color="bg-emerald-500" label="Scored" />
        <LegendItem color="bg-zinc-800" label="Never scored" />
        <LegendItem color="bg-violet-600" label="Extra time goal" />
        <span className="flex items-center gap-1.5">
          <span className="inline-flex h-4 w-4 items-center justify-center rounded bg-emerald-500 ring-2 ring-amber-400 text-[6px]" />
          Minute 45 or 90 (incl. stoppage time)
        </span>
      </div>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------
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
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3">
      <p className="text-xs text-zinc-500 mb-1">{label}</p>
      <p className="text-xl font-bold text-white">{value}</p>
      {sub && <p className="text-xs text-zinc-600 mt-0.5">{sub}</p>}
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
