"use client";

import { useState, useEffect, useMemo } from "react";
import type { MinuteGoalDetail, ExtraTimeGoalDetail } from "@/lib/data";
import { heatLevel } from "@/lib/heat";

interface MinuteGridProps {
  minutesScored: number[];
  minuteGoalCounts: Record<string, number>;
  extraTimeMinutes: number[];
  minutes?: Record<string, MinuteGoalDetail>;
  extraTime?: ExtraTimeGoalDetail[];
  selectedMinute?: number;
  onSelectMinute?: (minute: number) => void;
  isMorphed?: boolean;
}

const TOTAL_CELLS = 90;
const COLS = 10;
const ANIM_DURATION_MS = 4000;

function formatFirstDate(isoString: string | null | undefined): string {
  if (!isoString) return "";
  const parts = isoString.split("-");
  if (parts.length < 3) return isoString;
  const year = parts[0];
  const month = parseInt(parts[1], 10);
  const day = parseInt(parts[2], 10);
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  return `${day} ${months[month - 1] || parts[1]} ${year}`;
}

export default function MinuteGrid({
  minutesScored,
  minuteGoalCounts,
  extraTimeMinutes,
  minutes = {},
  extraTime = [],
  selectedMinute = 1,
  onSelectMinute,
  isMorphed = false,
}: MinuteGridProps) {
  const scoredSet = useMemo(() => new Set(minutesScored), [minutesScored]);
  const totalScoredCount = scoredSet.size;

  // Order of lighting up: earliest firstDate first, ties broken by minute number
  const fillOrder = useMemo(() => {
    return Array.from({ length: TOTAL_CELLS }, (_, i) => i + 1)
      .filter((m) => scoredSet.has(m))
      .map((m) => ({
        minute: m,
        firstDate: minutes[String(m)]?.firstDate || "9999-99-99",
      }))
      .sort((a, b) => {
        if (a.firstDate !== b.firstDate) {
          return a.firstDate.localeCompare(b.firstDate);
        }
        return a.minute - b.minute;
      });
  }, [scoredSet, minutes]);

  // Map each scored minute to its index in the lighting sequence
  const scoredIndexMap = useMemo(() => {
    const map = new Map<number, number>();
    fillOrder.forEach((item, index) => {
      map.set(item.minute, index);
    });
    return map;
  }, [fillOrder]);

  // Missing minutes in order 1..90
  const gapMinutes = useMemo(() => {
    return Array.from({ length: TOTAL_CELLS }, (_, i) => i + 1).filter(
      (m) => !scoredSet.has(m)
    );
  }, [scoredSet]);

  const gapIndexMap = useMemo(() => {
    const map = new Map<number, number>();
    gapMinutes.forEach((m, index) => {
      map.set(m, index);
    });
    return map;
  }, [gapMinutes]);

  // Animation state (defaults to final state on server to prevent mismatch)
  const [replayKey, setReplayKey] = useState(0);
  const [isSkipped, setIsSkipped] = useState(isMorphed);
  const [isFinished, setIsFinished] = useState(isMorphed);
  const [hasStarted, setHasStarted] = useState(false);
  const [activeStep, setActiveStep] = useState<number>(-1);
  const [hoveredMessage, setHoveredMessage] = useState<string | null>(null);
  const [reducedMotion, setReducedMotion] = useState(false);

  // If morphed, do not replay fill-in
  useEffect(() => {
    if (isMorphed) {
      setIsSkipped(true);
      setIsFinished(true);
    }
  }, [isMorphed]);

  // Check prefers-reduced-motion
  useEffect(() => {
    if (typeof window === "undefined") return;
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (media.matches) {
      setReducedMotion(true);
      setIsSkipped(true);
      setIsFinished(true);
      setHasStarted(true);
      return;
    }

    setHasStarted(true);
  }, []);

  // Ticker timeline timer (only on fresh load, never on morph)
  useEffect(() => {
    if (isMorphed || !hasStarted || reducedMotion || isSkipped || totalScoredCount === 0) {
      setIsFinished(true);
      return;
    }

    setIsFinished(false);
    setActiveStep(0);
    const startTime = Date.now();
    let frameId: number;

    const tick = () => {
      const elapsed = Date.now() - startTime;
      if (elapsed >= ANIM_DURATION_MS) {
        setIsFinished(true);
        setActiveStep(totalScoredCount - 1);
        return;
      }

      const progress = elapsed / ANIM_DURATION_MS;
      const step = Math.min(
        totalScoredCount - 1,
        Math.floor(progress * totalScoredCount)
      );
      setActiveStep(step);

      frameId = requestAnimationFrame(tick);
    };

    frameId = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(frameId);
    };
  }, [hasStarted, replayKey, isSkipped, totalScoredCount, reducedMotion, isMorphed]);

  // Skip on clicking anywhere on the grid
  const handleGridClick = () => {
    if (!isFinished && !isSkipped) {
      setIsSkipped(true);
      setIsFinished(true);
    }
  };

  const handleReplay = () => {
    setIsSkipped(false);
    setIsFinished(false);
    setHoveredMessage(null);
    setReplayKey((k) => k + 1);
  };

  const currentLighting =
    hasStarted && !isFinished && activeStep >= 0 && activeStep < fillOrder.length
      ? fillOrder[activeStep]
      : null;

  const currentCounter =
    !hasStarted || isFinished
      ? totalScoredCount
      : activeStep >= 0
      ? activeStep + 1
      : 0;

  return (
    <div key={replayKey} className="w-full">
      {/* Ticker & Controls bar */}
      <div className="mb-4 flex flex-col gap-2 rounded-xl border border-tone-800 bg-tone-900/90 p-3.5 backdrop-blur sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-1 items-center gap-3 min-h-[28px]">
          {/* Climbing counter */}
          <span className="flex items-center rounded-lg bg-scored-500/10 px-2.5 py-1 text-xs font-bold text-foreground border border-scored-500/20 font-mono">
            {currentCounter} of 90
          </span>

          {/* Ticker live text / Hover message */}
          <div className="text-xs text-tone-300 font-medium truncate">
            {hoveredMessage ? (
              <span className="text-gap-300 font-semibold transition-all">
                {hoveredMessage}
              </span>
            ) : !isFinished && currentLighting ? (
              <span className="animate-pulse">
                Minute {currentLighting.minute}, first scored{" "}
                <strong className="text-scored-300">
                  {formatFirstDate(currentLighting.firstDate)}
                </strong>
              </span>
            ) : gapMinutes.length === 0 ? (
              <span className="text-scored-400 font-semibold">
                All 90 minutes completed
              </span>
            ) : (
              <span className="text-tone-400">
                {totalScoredCount} minutes filled ·{" "}
                <span className="text-gap-400 font-semibold">
                  {gapMinutes.length} gap{gapMinutes.length !== 1 ? "s" : ""}
                </span>{" "}
                pulsing below
              </span>
            )}
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 self-end sm:self-auto">
          {!isFinished && !isSkipped && !reducedMotion && hasStarted && (
            <button
              onClick={() => {
                setIsSkipped(true);
                setIsFinished(true);
              }}
              className="text-xs text-tone-400 hover:text-foreground px-2 py-1 rounded bg-tone-800 hover:bg-tone-700 transition"
              title="Skip animation to end"
            >
              Skip
            </button>
          )}

          <button
            onClick={handleReplay}
            className="flex items-center gap-1.5 rounded-lg border border-tone-700 bg-tone-800 px-3 py-1 text-xs font-semibold text-tone-200 hover:border-tone-500 hover:bg-tone-700 hover:text-foreground transition cursor-pointer"
            title="Replay fill-in animation"
          >
            <svg
              className="h-3 w-3"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2.5}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
            Replay
          </button>
        </div>
      </div>

      {/* No gaps badge (Lewandowski) */}
      {gapMinutes.length === 0 && (
        <div
          style={
            !reducedMotion && !isSkipped && !isMorphed
              ? {
                  animation: `fadeInBadge 0.6s ease-out 4.0s backwards`,
                }
              : undefined
          }
          className="mb-4 flex items-center gap-2 rounded-xl border border-scored-500/40 bg-scored-950/40 px-4 py-2.5 text-xs font-semibold text-scored-300 shadow-lg shadow-scored-950/40 badge-fade-anim transition-opacity duration-500"
        >
          <span className="flex h-2 w-2 rounded-full bg-scored-400 animate-ping" />
          <span>Every minute covered (added time counted in 45 and 90)</span>
        </div>
      )}

      {/* 90-Cell Main Grid */}
      <div
        onClick={handleGridClick}
        className={[
          "grid gap-1 select-none",
          !isFinished && !isSkipped && !reducedMotion ? "cursor-pointer" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        style={{ gridTemplateColumns: `repeat(${COLS}, minmax(0, 1fr))` }}
        title={
          !isFinished && !isSkipped && !reducedMotion
            ? "Click grid to skip animation"
            : undefined
        }
      >
        {Array.from({ length: TOTAL_CELLS }, (_, i) => i + 1).map((minute) => {
          const scored = scoredSet.has(minute);
          const count = minuteGoalCounts[String(minute)] ?? 0;
          const isSpecial = minute === 45 || minute === 90;
          const isSelected = minute === selectedMinute;
          const firstDate = minutes[String(minute)]?.firstDate;

          // Fill-in timing for fresh load
          const scoredOrder = scoredIndexMap.get(minute);
          const fillDelay =
            scoredOrder !== undefined && totalScoredCount > 1
              ? Number(
                  ((scoredOrder / totalScoredCount) * (ANIM_DURATION_MS / 1000)).toFixed(3)
                )
              : 0;

          // Gap cell timing
          const gapOrder = gapIndexMap.get(minute);
          const gapDelay =
            gapOrder !== undefined
              ? Number((ANIM_DURATION_MS / 1000 + gapOrder * 0.18).toFixed(3))
              : 0;

          const isGap = !scored;

          // Wave transition delay when morphing (staggered left to right across columns)
          const col = (minute - 1) % COLS;
          const waveDelayMs = reducedMotion ? 0 : col * 45;

          const hoverText = scored
            ? `${count} goal${count !== 1 ? "s" : ""} in minute ${minute}${
                firstDate ? ` · First: ${formatFirstDate(firstDate)}` : ""
              }${isSpecial ? " (incl. stoppage time)" : ""}`
            : `Never scored in minute ${minute}${
                isSpecial ? " (incl. stoppage time)" : ""
              }`;

          // Animation and transition style calculation
          const animStyle: React.CSSProperties = {};

          if (isMorphed) {
            // Feature 4: Morph between players - wave transition ~600ms staggered left to right
            animStyle.transition = reducedMotion
              ? "none"
              : "background-color 600ms ease, box-shadow 600ms ease, color 600ms ease, transform 600ms ease";
            animStyle.transitionDelay = `${waveDelayMs}ms`;
            if (isGap && !reducedMotion) {
              animStyle.animation = `gapRingPulse 3s ease-in-out infinite`;
            }
          } else if (!reducedMotion && !isSkipped) {
            // Fresh load fill-in
            if (scored) {
              animStyle.animation = `cellLightUp 0.35s ease-out backwards`;
              animStyle.animationDelay = `${fillDelay}s`;
            } else if (isGap) {
              animStyle.animation = `gapAppearAndBreathe 3s ease-in-out infinite`;
              animStyle.animationDelay = `${gapDelay}s`;
              animStyle.animationFillMode = "backwards";
            }
          } else if (isGap && !reducedMotion) {
            animStyle.animation = `gapRingPulse 3s ease-in-out infinite`;
          }

          return (
            <div
              key={minute}
              onMouseEnter={() => setHoveredMessage(hoverText)}
              onMouseLeave={() => setHoveredMessage(null)}
              onClick={(e) => {
                e.stopPropagation();
                onSelectMinute?.(minute);
              }}
              title={hoverText}
              style={animStyle}
              className={[
                "relative flex flex-col items-center justify-center rounded aspect-square transition-transform cursor-pointer",
                isSelected
                  ? "ring-2 ring-foreground ring-offset-2 ring-offset-tone-950 scale-110 z-20 shadow-xl"
                  : "hover:scale-105",
                scored
                  ? `heat-${heatLevel(count)} shadow-lg shadow-scored-500/30 cell-fill-anim`
                  : "bg-tone-800 text-tone-500 grid-gap gap-ring-anim gap-ring-static",
                isSpecial && scored && !isSelected
                  ? "ring-2 ring-offset-1 ring-offset-tone-950 ring-gap-400"
                  : "",
                isSpecial && !scored && !isGap && !isSelected
                  ? "ring-1 ring-inset ring-tone-600"
                  : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <span className="text-[10px] font-semibold leading-none pointer-events-none">
                {minute}
              </span>

              {isSpecial && (
                <span
                  className={`text-[7px] leading-none mt-0.5 pointer-events-none ${
                    scored ? "text-inherit" : "text-tone-600"
                  }`}
                >
                  +
                </span>
              )}

              {scored && count > 1 && (
                <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-gap-400 text-[8px] font-bold text-tone-900 pointer-events-none shadow">
                  {count}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Extra-time strip */}
      {extraTimeMinutes.length > 0 && (
        <div className="mt-5 rounded-xl border border-tone-800/80 bg-tone-900/40 p-3">
          <p className="text-xs text-tone-500 mb-2 uppercase tracking-wider font-semibold">
            Extra Time (minute &gt; 90)
          </p>
          <div className="flex flex-wrap gap-1.5">
            {extraTimeMinutes.map((minute) => {
              const count = minuteGoalCounts[String(minute)] ?? 0;
              const extDetail = extraTime.find((e) => e.minute === minute);
              const tooltip = `${count} goal${
                count !== 1 ? "s" : ""
              } in minute ${minute} (extra time)${
                extDetail?.firstDate
                  ? ` · First: ${formatFirstDate(extDetail.firstDate)}`
                  : ""
              }`;

              return (
                <div
                  key={minute}
                  onMouseEnter={() => setHoveredMessage(tooltip)}
                  onMouseLeave={() => setHoveredMessage(null)}
                  title={tooltip}
                  className="relative flex items-center justify-center rounded bg-extra-600 text-foreground px-2.5 py-1 text-[11px] font-semibold shadow shadow-extra-600/30 hover:scale-110 transition-transform cursor-pointer"
                >
                  {minute}′
                  {count > 1 && (
                    <span className="ml-1.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-gap-400 text-[8px] font-bold text-tone-900">
                      {count}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
