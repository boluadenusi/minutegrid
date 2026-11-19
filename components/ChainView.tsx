"use client";

import type { CSSProperties } from "react";
import type { Chain } from "@/lib/chains";
import { chainLinkGeometry } from "@/lib/chain-geometry";
import { heatLevel } from "@/lib/heat";

interface ChainViewProps {
  counts: Record<string, number>;
  chains: Chain[];
  selectedMinute: number;
  activeMinute: number | null;
  onSelectMinute: (minute: number) => void;
  onActiveMinute: (minute: number | null) => void;
  isMorphed: boolean;
  isCrossFading: boolean;
  /** minute -> date the gap was closed by a live goal */
  gapsClosed?: Record<string, string>;
}

export default function ChainView({
  counts, chains, selectedMinute, activeMinute, onSelectMinute, onActiveMinute,
  isMorphed, isCrossFading, gapsClosed = {},
}: ChainViewProps) {
  const activeChain = chains.find(
    (chain) => activeMinute !== null && activeMinute >= chain.start && activeMinute <= chain.end
  );
  const gaps = 90 - chains.reduce((sum, chain) => sum + chain.length, 0);
  const gapPause = gaps ? Math.min(150, 2700 / gaps) : 0;
  const step = (3000 - gaps * gapPause) / 90;
  let elapsed = 0;

  const nodes = Array.from({ length: 90 }, (_, index) => {
    const minute = index + 1;
    const count = counts[String(minute)] ?? 0;
    const delay = elapsed;
    elapsed += step + (count > 0 ? 0 : gapPause);
    const chain = chains.find((item) => minute >= item.start && minute <= item.end);
    return { minute, count, delay, chain };
  });

  return (
    <section aria-label="Scoring chains">
      <p className="mb-3 text-xs text-tone-400">
        Select a minute to move the playhead. Highlight a node to explore its chain.
      </p>
      <div className="chain-scroll" role="region" aria-label="Scoring chains; scroll horizontally to see all minutes" tabIndex={0}>
      <div className={`chain-board ${isMorphed ? "chain-board-morphed" : ""}`}>
        <svg className={`chain-links ${isCrossFading ? "chain-links-fading" : ""}`} viewBox="0 0 600 540" aria-hidden="true">
          <defs>
            <marker id="chain-arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" markerUnits="userSpaceOnUse" orient="auto">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" />
            </marker>
          </defs>
          {nodes.filter(({ minute, count }) => count > 0 && minute < 90 && (counts[String(minute + 1)] ?? 0) > 0).map(({ minute, delay, chain }) => {
            const { path } = chainLinkGeometry(minute, 60, 60);
            return (
              <path
                key={minute}
                d={path}
                pathLength="1"
                markerEnd="url(#chain-arrow)"
                className={`chain-link ${activeMinute !== null && chain !== activeChain ? "chain-dimmed" : ""}`}
                style={{ "--chain-delay": `${delay}ms` } as CSSProperties}
              />
            );
          })}
        </svg>
        <div className="chain-nodes">
          {nodes.map(({ minute, count, delay, chain }) => {
            const special = minute === 45 || minute === 90;
            const dimmed = activeMinute !== null && (!activeChain || chain !== activeChain) && minute !== activeMinute;
            const closed = gapsClosed[String(minute)];
            const label = `Minute ${minute}, ${count} goal${count === 1 ? "" : "s"}${special ? ", includes added time" : ""}${closed ? `, gap closed ${closed}` : ""}`;
            return (
              <div className={`chain-cell ${dimmed ? "chain-dimmed" : ""}`} key={minute}>
                <button
                  type="button"
                  className={`chain-node ${count > 0 ? `chain-node-scored heat-${heatLevel(count)}` : "chain-node-gap"} ${chain?.start === minute ? "chain-node-head" : ""} ${selectedMinute === minute ? "chain-node-selected" : ""}`}
                  style={{ "--chain-delay": `${delay}ms`, "--wave-delay": `${((minute - 1) % 10) * 45}ms` } as CSSProperties}
                  aria-label={label}
                  aria-pressed={selectedMinute === minute}
                  title={label}
                  onMouseEnter={() => onActiveMinute(minute)}
                  onMouseLeave={() => onActiveMinute(null)}
                  onFocus={() => onActiveMinute(minute)}
                  onBlur={() => onActiveMinute(null)}
                  onClick={() => { onSelectMinute(minute); onActiveMinute(minute); }}
                >
                  <span>{minute}</span>
                  {special && <span className="chain-special" aria-hidden="true">+</span>}
                  {closed && <span className="chain-gap-closed" aria-hidden="true" />}
                </button>
              </div>
            );
          })}
        </div>
      </div>
      </div>
      <p className="mt-3 text-xs text-tone-500">+ Minutes 45 and 90 include added time. Dashed nodes are gaps.
        {Object.keys(gapsClosed).length > 0 && " A dot marks a gap closed by a goal since the last Transfermarkt update."}</p>
    </section>
  );
}
