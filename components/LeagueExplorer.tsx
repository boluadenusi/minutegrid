"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { LeagueDetail, LeagueSummary } from "@/lib/data";
import Avatar from "@/components/Avatar";

interface LeagueExplorerProps {
  leagues: LeagueSummary[];
}

type Status = "idle" | "loading" | "error";

const plural = (count: number, word: string) => `${count.toLocaleString()} ${word}${count === 1 ? "" : "s"}`;

export default function LeagueExplorer({ leagues }: LeagueExplorerProps) {
  const [leagueId, setLeagueId] = useState<string | null>(null);
  const [clubIndex, setClubIndex] = useState<number | null>(null);
  const [details, setDetails] = useState<Record<string, LeagueDetail>>({});
  const [status, setStatus] = useState<Status>("idle");
  const headingRef = useRef<HTMLHeadingElement>(null);
  const moved = useRef(false);

  const league = leagueId ? details[leagueId] : undefined;
  const summary = leagues.find((item) => item.id === leagueId);
  const club = league && clubIndex !== null ? league.clubs[clubIndex] : undefined;

  useEffect(() => {
    if (!leagueId || details[leagueId]) return;
    const controller = new AbortController();
    setStatus("loading");
    fetch(`/api/league/${encodeURIComponent(leagueId)}`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`League request failed: ${response.status}`);
        return response.json() as Promise<LeagueDetail>;
      })
      .then((detail) => {
        setDetails((current) => ({ ...current, [detail.id]: detail }));
        setStatus("idle");
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        console.error("Could not load league:", reason);
        setStatus("error");
      });
    return () => controller.abort();
  }, [leagueId, details]);

  // Move focus to the new level's heading after a tap, so keyboard and screen
  // reader users land on what changed.
  useEffect(() => {
    if (moved.current) headingRef.current?.focus();
  }, [leagueId, clubIndex, league]);

  const go = (nextLeague: string | null, nextClub: number | null = null) => {
    moved.current = true;
    setLeagueId(nextLeague);
    setClubIndex(nextClub);
    if (nextLeague !== leagueId) setStatus("idle");
  };

  if (leagues.length === 0) return null;

  const heading = club ? club.name : summary ? summary.name : "Browse by league";

  return (
    <section className="space-y-3" aria-label="Browse by league">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 ref={headingRef} tabIndex={-1} className="flex items-center gap-2 text-xl font-semibold text-foreground outline-none">
          {club ? <Avatar key={club.name} src={club.logo} name={club.name} size={24} kind="logo" />
            : summary ? <Avatar key={summary.id} src={summary.logo} name={summary.name} size={24} kind="logo" /> : null}
          {heading}
        </h2>
        <p className="text-xs text-tone-400">
          {club ? summary?.name
            : summary ? summary.country ?? "International"
            : "Tap a league, then a club, then a player"}
        </p>
      </div>

      {leagueId && (
        <nav aria-label="League explorer" className="explorer-crumbs">
          <button type="button" onClick={() => go(null)}>All leagues</button>
          <span aria-hidden="true">›</span>
          {club ? (
            <>
              <button type="button" onClick={() => go(leagueId)}>{summary?.name}</button>
              <span aria-hidden="true">›</span>
              <span aria-current="page">{club.name}</span>
            </>
          ) : (
            <span aria-current="page">{summary?.name}</span>
          )}
        </nav>
      )}

      <div aria-live="polite" aria-busy={status === "loading"}>
        {!leagueId && (
          <ul className="explorer-grid">
            {leagues.map((item) => (
              <li key={item.id}>
                <button type="button" className="explorer-tile explorer-tile-club" onClick={() => go(item.id)}>
                  <Avatar src={item.logo} name={item.name} size={32} kind="logo" />
                  <span className="min-w-0">
                    <span className="explorer-tile-title">{item.name}</span>
                    <span className="explorer-tile-meta">{item.country ?? "International"}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}

        {leagueId && !league && status === "loading" && (
          <p className="explorer-note">Loading clubs…</p>
        )}
        {leagueId && !league && status === "error" && (
          <p className="explorer-note">
            Could not load this league.{" "}
            <button type="button" className="text-scored-400 underline" onClick={() => {
              setStatus("idle");
              setDetails((current) => ({ ...current }));
            }}>Try again</button>
          </p>
        )}

        {league && !club && (
          <ul className="explorer-grid">
            {league.clubs.map((item, index) => (
              <li key={item.id ?? item.name}>
                <button type="button" className="explorer-tile explorer-tile-club" onClick={() => go(league.id, index)}>
                  <Avatar src={item.logo} name={item.name} size={32} kind="logo" />
                  <span className="explorer-tile-title">{item.name}</span>
                </button>
              </li>
            ))}
          </ul>
        )}

        {club && (
          <ol className="explorer-players">
            {club.players.map((player) => (
              <li key={player.id}>
                <Link href={`/player/${player.id}`} className="explorer-player">
                  <span className="flex min-w-0 items-center gap-3">
                    <Avatar src={player.image} name={player.name} size={36} />
                    <span className="explorer-tile-title">{player.name}</span>
                  </span>
                  <span className="explorer-player-stats">
                    <span className="explorer-meter" role="img" aria-label={`${player.minutes} of 90 minutes scored`}>
                      <span style={{ inlineSize: `${(player.minutes / 90) * 100}%` }} />
                    </span>
                    <span className="tabular-nums">{player.minutes}/90</span>
                    <span className="tabular-nums text-tone-400">{plural(player.goals, "goal")}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}
