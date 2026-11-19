import Link from "next/link";
import HomeSearch from "@/components/HomeSearch";
import ClubStatus from "@/components/ClubStatus";
import { getBoards, getIndex, getLeagues, windowStartLabel, type BoardEntry, type GapClosed } from "@/lib/data";
import LeagueExplorer from "@/components/LeagueExplorer";
import Avatar from "@/components/Avatar";
import { GitCompareArrows } from "lucide-react";
import { formatGoalDate } from "@/lib/goal-format";
import HeroGrid from "@/components/HeroGrid";
import GapTicker from "@/components/GapTicker";

// The 10-year window moves every day; rebuild this page at most hourly.
export const revalidate = 3600;

function Board({ title, description, players, almost = false }: {
  title: string;
  description: string;
  players: BoardEntry[];
  almost?: boolean;
}) {
  return (
    <section className="space-y-3" aria-label={title}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xl font-semibold text-foreground">{title}</h2>
        <p className="text-xs text-tone-400">{description}</p>
      </div>
      {players.length === 0 ? (
        <p className="rounded-xl border border-tone-800 bg-tone-900 p-4 text-sm text-tone-400">No players on this board yet.</p>
      ) : (
        <ol className="space-y-2">
          {players.map((player) => (
            <li key={player.id} className="board-row" title={player.club && player.asOf ? `Club as of ${player.asOf}` : undefined}>
              <div className="board-row-head flex flex-wrap items-center justify-between gap-2">
                <h3 className="board-row-title flex items-center gap-3 font-semibold text-foreground">
                  <Avatar src={player.image} name={player.name} size={40} />
                  <Link className="board-row-link" href={`/player/${player.id}`}>{player.name}</Link>
                </h3>
                <p className="board-row-stats text-xs tabular-nums text-tone-400">
                  <span className="board-row-goals">{player.goals} goals</span>
                  <span className="board-row-sep"> · </span>
                  <span>last scored <time dateTime={player.lastGoalDate}>{player.lastGoalDate}</time></span>
                </p>
              </div>
              <div className="board-row-club">
                <ClubStatus club={player.club} active={player.active} asOf={player.asOf} />
              </div>
              <div className="board-strip" aria-label={`${90 - player.missing.length} of 90 minutes scored`} role="img">
                {player.counts.map((count, index) => (
                  <span key={index} className={count > 0 ? "board-strip-scored" : "board-strip-gap"} />
                ))}
              </div>
              {almost && (
                <div className="board-chips" aria-label={`Missing minutes for ${player.name}`}>
                  <span className="text-xs text-tone-400">Needs</span>
                  {player.missing.map((minute) => (
                    <Link key={minute} href={`/player/${player.id}?minute=${minute}`}
                      className="board-chip" aria-label={`${player.name}, jump to minute ${minute}`}>
                      {minute}
                    </Link>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
  "September", "October", "November", "December"];

const GAPS_SHOWN = 12;

function GapCards({ gaps }: { gaps: GapClosed[] }) {
  return (
    <ul className="gap-closed-list">
      {gaps.map((gap) => (
        <li key={`${gap.id}-${gap.minute}`}>
          <Link href={`/player/${gap.id}?minute=${gap.minute}`} className="gap-closed-card"
            aria-label={`${gap.name} closed minute ${gap.minute} on ${formatGoalDate(gap.date)}`}>
            <span className="gap-closed-minute" aria-hidden="true">{gap.minute}&apos;</span>
            <span className="min-w-0">
              <span className="gap-closed-name">{gap.name}</span>
              <time className="gap-closed-date" dateTime={gap.date}>{formatGoalDate(gap.date)}</time>
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function GapsClosed({ gaps, month }: { gaps: GapClosed[]; month?: string }) {
  const [year, monthNumber] = (month ?? "").split("-");
  const monthLabel = monthNumber ? `${MONTHS[Number(monthNumber) - 1]} ${year}` : "this month";
  return (
    <section className="space-y-3" aria-label="Gap closed this month">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xl font-semibold text-foreground">Gap closed this month</h2>
        <p className="text-xs text-tone-400">First-ever goal in a minute, {monthLabel}</p>
      </div>
      {gaps.length === 0 ? (
        <p className="rounded-xl border border-tone-800 bg-tone-900 p-4 text-sm text-tone-400">No gaps closed yet this month.</p>
      ) : (
        <>
          <GapCards gaps={gaps.slice(0, GAPS_SHOWN)} />
          {gaps.length > GAPS_SHOWN && (
            <details className="gap-closed-more">
              <summary>Show {gaps.length - GAPS_SHOWN} more</summary>
              <GapCards gaps={gaps.slice(GAPS_SHOWN)} />
            </details>
          )}
        </>
      )}
    </section>
  );
}

export default function HomePage() {
  const boards = getBoards();
  const { dataUpTo, windowStart, windowEnd, players } = getIndex();
  const leagues = getLeagues();
  // A different board player is featured each day.
  const featuredPool = [...boards.complete, ...boards.almost];
  const day = Math.floor(Date.parse(windowEnd ?? dataUpTo) / 86_400_000);
  const featured = featuredPool.length ? featuredPool[day % featuredPool.length] : null;
  // Quick picks: the active players with the most goals in the window.
  const quickPicks = players.filter((player) => player.active).slice(0, 4);
  return (
    <main className="home mx-auto max-w-3xl space-y-8 px-4 py-12 lg:max-w-6xl lg:px-8">
      {/* Phones: title, then search. Wide screens: a two-column hero. */}
      <header className="home-hero">
        <div className="home-hero-text space-y-2 text-center">
          <h1 className="text-4xl font-bold tracking-tight text-foreground">Minute Grid</h1>
          <p className="text-sm text-tone-400">Which minutes did your player score in?</p>
          <p className="home-hero-stats">
            {players.length.toLocaleString("en-US")} players across {leagues.length} top flights,
            counting every goal from the last ten years, since {formatGoalDate(windowStartLabel(windowStart)).toLowerCase()}.
          </p>
          <div className="home-hero-ticker">
            <GapTicker gaps={(boards.gapsClosed ?? []).slice(0, 10)} dataUpTo={dataUpTo} />
          </div>
        </div>
        <div className="home-hero-actions space-y-2">
          {featured && (
            <div className="home-hero-feature">
              <HeroGrid id={featured.id} name={featured.name} counts={featured.counts} />
            </div>
          )}
          <HomeSearch />
          {quickPicks.length > 0 && (
            <p className="home-quick-picks">
              or try{" "}
              {quickPicks.map((player, index) => (
                <span key={player.id}>
                  {index > 0 && (index === quickPicks.length - 1 ? " or " : ", ")}
                  <Link href={`/player/${player.id}`} className="home-quick-pick" aria-label={player.name} title={player.name}>
                    {player.name.split(/\s+/).at(-1)}
                  </Link>
                </span>
              ))}
            </p>
          )}
          <div className="flex justify-end">
            <Link href="/compare" className="compare-button">
              <GitCompareArrows size={18} aria-hidden="true" />
              Compare two players
            </Link>
          </div>
        </div>
      </header>
      <div className="home-layout">
        <div className="home-boards space-y-8">
          <Board title="Complete" description="Scored in every minute" players={boards.complete} />
          <Board title="Almost complete" description="One to five minutes away" players={boards.almost} almost />
        </div>
        <div className="home-explorer">
          <LeagueExplorer leagues={leagues} />
        </div>
        <aside className="home-side">
          <GapsClosed gaps={boards.gapsClosed ?? []} month={boards.gapsClosedMonth} />
        </aside>
      </div>
      <p className="home-footnote text-xs text-tone-400">
        Based on goals since {windowStartLabel(windowStart)} in the competitions covered. Added time counts in minutes 45 and 90.
        {" "}Data up to {dataUpTo}. Top 5 leagues, their cups and super cups, and UEFA club competitions. Updated from ESPN every few hours.
        {" "}<Link href="/coverage" className="text-scored-400 underline">View coverage</Link>.
      </p>
    </main>
  );
}
