import Link from "next/link";
import { getCoverage, getIndex, type CoverageData } from "@/lib/data";

type Competition = CoverageData["leagues"][number];

const kinds: { key: keyof CoverageData; label: string }[] = [
  { key: "leagues", label: "League" },
  { key: "cups", label: "Cup" },
  { key: "superCups", label: "Super cup" },
  { key: "uefa", label: "UEFA" },
  { key: "international", label: "International" },
];

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function formatDate(iso?: string): string {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  return `${d} ${MONTHS[m - 1]} ${y}`;
}

function daysBetween(a: string, b: string): number {
  return Math.max(0, (Date.parse(b) - Date.parse(a)) / 86_400_000);
}

// The 10-year window moves every day; rebuild this page at most hourly.
export const revalidate = 3600;

export default function CoveragePage() {
  const coverage = getCoverage();
  const { dataUpTo, windowStart, windowEnd, liveFrom, liveCompetitions = [], players } = getIndex();
  const live = new Set(liveCompetitions);
  const start = windowStart ?? dataUpTo;
  const end = windowEnd ?? dataUpTo;

  // Countries in the order the data lists them, each with its league, cups and super cup.
  const countries = new Map<string, { competition: Competition; kind: string }[]>();
  const european: { competition: Competition; kind: string }[] = [];
  let total = 0;
  for (const { key, label } of kinds) {
    for (const competition of coverage[key] ?? []) {
      total += 1;
      const entry = { competition, kind: label };
      if (!competition.country) european.push(entry);
      else countries.set(competition.country, [...(countries.get(competition.country) ?? []), entry]);
    }
  }
  const cards = [
    ...[...countries].map(([name, items]) => ({ name, items })),
    ...(european.length ? [{ name: "UEFA", items: european }] : []),
  ];

  const historyShare = liveFrom
    ? Math.min(100, Math.max(0, (daysBetween(start, liveFrom) / Math.max(1, daysBetween(start, end))) * 100))
    : 100;

  const stats = [
    { value: String(total), label: "competitions", note: "5 countries and UEFA" },
    { value: players.length.toLocaleString("en-GB"), label: "players", note: "at top-5 league clubs" },
    { value: "10 years", label: "of goals", note: `since ${formatDate(start)}` },
    { value: "3 hours", label: "between updates", note: `data up to ${formatDate(dataUpTo)}` },
  ];

  return (
    <main className="coverage mx-auto max-w-3xl space-y-10 px-4 py-12 lg:max-w-5xl lg:px-8">
      <Link href="/" className="inline-flex items-center gap-1.5 text-xs text-tone-500 transition hover:text-foreground">
        <span aria-hidden>←</span> Back to all players
      </Link>

      <header className="space-y-3">
        <h1 className="text-4xl font-bold tracking-tight text-foreground">Coverage</h1>
        <p className="text-sm text-tone-400">
          Every goal from the top 5 European leagues, their domestic cups and super cups, and the UEFA club
          competitions, over a rolling 10-year window that moves on every day. Only players currently at a top-5
          league club are shown.
        </p>
      </header>

      <section aria-label="At a glance" className="coverage-stats">
        {stats.map((stat) => (
          <div key={stat.label} className="coverage-stat">
            <p className="coverage-stat-value">{stat.value}</p>
            <p className="coverage-stat-label">{stat.label}</p>
            <p className="coverage-stat-note">{stat.note}</p>
          </div>
        ))}
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-xl font-semibold text-foreground">Where the goals come from</h2>
          <span className="text-xs text-tone-400">{formatDate(start)} to {formatDate(end)}</span>
        </div>
        <div className="coverage-card space-y-4">
          <div className="coverage-timeline" role="img"
            aria-label={`History from ${formatDate(start)}${liveFrom ? `, live updates from ${formatDate(liveFrom)}` : ""}`}>
            <span className="coverage-timeline-history" style={{ inlineSize: `${historyShare}%` }} />
            {liveFrom && <span className="coverage-timeline-live" />}
          </div>
          <div className="coverage-sources">
            <div>
              <p className="coverage-source-title"><span className="coverage-swatch coverage-swatch-history" />History</p>
              <p className="coverage-source-text">
                Transfermarkt{liveFrom ? ` up to ${formatDate(daysBefore(liveFrom))}` : ""}, with ESPN for the EFL
                Cup, Coupe de France and Coupe de la Ligue. For the other cups and super cups, each season uses
                whichever source has more goals; sources are never mixed within a season.
              </p>
            </div>
            {liveFrom && (
              <div>
                <p className="coverage-source-title"><span className="coverage-swatch coverage-swatch-live" />Live</p>
                <p className="coverage-source-text">
                  ESPN from {formatDate(liveFrom)}, checked every 3 hours. New goals show up on the grid as gaps
                  closed.
                </p>
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="coverage-why" aria-labelledby="why-window">
        <span className="coverage-why-sticker" aria-hidden>it&rsquo;s all a game</span>
        <h2 id="why-window" className="coverage-why-title">Why a 10-year rolling window?</h2>
        <div className="coverage-why-body">
          <p>
            Because football never forgets, but this grid does, on purpose. Every midnight the oldest day falls off
            the back of the window and takes its goals with it. That 37th-minute tap-in from a wet Tuesday in 2016?
            Gone. Square&rsquo;s empty again. Go and score another one.
          </p>
          <p>
            Ten years is long enough for a whole career to fill all 90 minutes, and short enough that nobody coasts
            on old goals. No pensions, no lifetime achievement awards. A player can drop off a board without kicking
            a ball. Rude? Yes. Fair? Also yes.
          </p>
        </div>
        <ol className="coverage-why-rules">
          <li><span>1</span>Score in all 90 minutes.</li>
          <li><span>2</span>Keep doing it.</li>
        </ol>
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-xl font-semibold text-foreground">Competitions</h2>
        </div>
        <div className="coverage-countries">
          {cards.map(({ name, items }) => (
            <article key={name} className="coverage-card coverage-country">
              <header className="coverage-country-head">
                <h3 className="coverage-country-name">{name}</h3>
                <span className="text-xs tabular-nums text-tone-400">{items.length}</span>
              </header>
              <ul className="coverage-list">
                {items.map(({ competition, kind }) => (
                  <li key={competition.id} className="coverage-item">
                    <span className="coverage-item-name">{competition.name}</span>
                    <span className="coverage-item-meta">
                      {name !== "UEFA" && <span className="coverage-kind">{kind}</span>}
                      {!live.has(competition.id) && <span className="coverage-ended">Ended</span>}
                    </span>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-foreground">How goals count</h2>
        <ul className="coverage-rules">
          <li><strong>Added time</strong> counts in minute 45 or 90.</li>
          <li><strong>Extra time</strong> goals are shown, but outside the 90-minute grid.</li>
          <li><strong>Penalties</strong> count; own goals and shoot-out kicks don&rsquo;t.</li>
          <li><strong>UEFA</strong> competitions from the group or league phase on; no qualifying rounds.</li>
        </ul>
      </section>
    </main>
  );
}

function daysBefore(iso: string): string {
  const d = new Date(Date.parse(iso) - 86_400_000);
  return d.toISOString().slice(0, 10);
}
