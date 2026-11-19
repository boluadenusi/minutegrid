import Link from "next/link";
import type { CSSProperties } from "react";
import { heatLevel } from "@/lib/heat";

interface HeroGridProps {
  id: number;
  name: string;
  /** Goals per minute, minutes 1–90. */
  counts: number[];
}

/** A featured player's 90-minute grid, drawn as square pixels that fill in row by row. */
export default function HeroGrid({ id, name, counts }: HeroGridProps) {
  const scored = counts.filter((count) => count > 0).length;
  const line = scored === 90
    ? "has scored in every one of the 90 minutes."
    : `has scored in ${scored} of the 90 minutes, ${90 - scored} to go.`;
  return (
    <Link href={`/player/${id}`} className="hero-grid-card" aria-label={`Today's grid: ${name} ${line} Open player`}>
      <span className="hero-grid" aria-hidden="true">
        {counts.map((count, index) => (
          <span
            key={index}
            className={`hero-cell ${count > 0 ? `hero-cell-scored heat-${heatLevel(count)}` : "hero-cell-gap"}`}
            style={{ "--hero-delay": `${Math.floor(index / 10) * 70}ms` } as CSSProperties}
          />
        ))}
      </span>
      <span className="hero-grid-caption">
        <span className="hero-grid-label">today&apos;s grid</span>
        <span className="hero-grid-name">{name}</span>
        <span className="hero-grid-meta">{line}</span>
      </span>
    </Link>
  );
}
