"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Pause, Play } from "lucide-react";
import type { GapClosed } from "@/lib/data";
import { formatGoalDate } from "@/lib/goal-format";

interface GapTickerProps {
  gaps: GapClosed[];
  dataUpTo: string;
}

const INTERVAL_MS = 5000;

function ordinal(n: number): string {
  const tens = n % 100;
  if (tens >= 11 && tens <= 13) return `${n}th`;
  return `${n}${({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th"}`;
}

const shortDate = (date: string) => formatGoalDate(date).replace(/ \d{4}$/, "").toLowerCase();

/** The latest "first goal in a minute" moments, said in plain words. Rotates
 * slowly, pauses on hover/focus or with the button, and stays still for
 * visitors who prefer reduced motion. */
export default function GapTicker({ gaps, dataUpTo }: GapTickerProps) {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const [held, setHeld] = useState(false);
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    if (gaps.length < 2 || paused || held || reduced) return;
    const timer = window.setInterval(() => setIndex((current) => (current + 1) % gaps.length), INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [gaps.length, paused, held, reduced]);

  const updated = <span className="hero-ticker-updated">goals up to {formatGoalDate(dataUpTo).toLowerCase()}</span>;
  if (gaps.length === 0) return <div className="hero-ticker">{updated}</div>;

  const gap = gaps[index % gaps.length];
  const rotating = gaps.length > 1 && !reduced;
  return (
    <div className="hero-ticker" onMouseEnter={() => setHeld(true)} onMouseLeave={() => setHeld(false)}
      onFocus={() => setHeld(true)} onBlur={() => setHeld(false)}>
      <p className="hero-ticker-line">
        <span className="hero-ticker-label">latest</span>{" "}
        <Link key={`${gap.id}-${gap.minute}`} href={`/player/${gap.id}?minute=${gap.minute}`} className="hero-ticker-item">
          <strong>{gap.name}</strong> scored in the {ordinal(gap.minute)} minute for the first time
        </Link>
        , {shortDate(gap.date)}.
        {rotating && (
          <button type="button" className="hero-ticker-toggle" onClick={() => setPaused((value) => !value)}
            aria-label={paused ? "Resume recent firsts" : "Pause recent firsts"} title={paused ? "Resume" : "Pause"}>
            {paused ? <Play size={12} aria-hidden="true" /> : <Pause size={12} aria-hidden="true" />}
          </button>
        )}
      </p>
      {updated}
    </div>
  );
}
