"use client";

import { useState, useEffect, useRef, useCallback } from "react";

interface TimelineStripProps {
  minuteGoalCounts: Record<string, number>;
  selectedMinute: number;
  onSelectMinute: (minute: number) => void;
  reducedMotion?: boolean;
}

const TOTAL_MINUTES = 90;
const SWEEP_DURATION_MS = 20000;
const STEP_INTERVAL_MS = Math.round(SWEEP_DURATION_MS / TOTAL_MINUTES); // ~222ms per minute

export default function TimelineStrip({
  minuteGoalCounts,
  selectedMinute,
  onSelectMinute,
  reducedMotion = false,
}: TimelineStripProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const trackRef = useRef<HTMLDivElement>(null);
  const isDraggingRef = useRef(false);

  // Maximum goals in any minute (for histogram scaling)
  const maxGoals = Math.max(
    1,
    ...Array.from({ length: TOTAL_MINUTES }, (_, i) => minuteGoalCounts[String(i + 1)] ?? 0)
  );

  // Compute minute from pointer position
  const getMinuteFromPointer = useCallback((clientX: number): number => {
    if (!trackRef.current) return 1;
    const rect = trackRef.current.getBoundingClientRect();
    const x = clientX - rect.left;
    const clampedRatio = Math.max(0, Math.min(1, x / rect.width));
    const minute = Math.min(
      TOTAL_MINUTES,
      Math.max(1, Math.round(clampedRatio * (TOTAL_MINUTES - 1)) + 1)
    );
    return minute;
  }, []);

  // Pointer drag handling
  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (isPlaying) setIsPlaying(false);
    isDraggingRef.current = true;
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    const m = getMinuteFromPointer(e.clientX);
    onSelectMinute(m);
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDraggingRef.current) return;
    const m = getMinuteFromPointer(e.clientX);
    if (m !== selectedMinute) {
      onSelectMinute(m);
    }
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    isDraggingRef.current = false;
    try {
      (e.target as HTMLElement).releasePointerCapture?.(e.pointerId);
    } catch {}
  };

  // Keyboard navigation for slider
  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      if (isPlaying) setIsPlaying(false);
      onSelectMinute(Math.max(1, selectedMinute - 1));
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      if (isPlaying) setIsPlaying(false);
      onSelectMinute(Math.min(TOTAL_MINUTES, selectedMinute + 1));
    } else if (e.key === "Home") {
      e.preventDefault();
      if (isPlaying) setIsPlaying(false);
      onSelectMinute(1);
    } else if (e.key === "End") {
      e.preventDefault();
      if (isPlaying) setIsPlaying(false);
      onSelectMinute(TOTAL_MINUTES);
    } else if (e.key === " " || e.key === "Enter") {
      e.preventDefault();
      togglePlay();
    }
  };

  // Play button sweep timer (sweeps 1 to 90 over ~20s)
  useEffect(() => {
    if (!isPlaying || reducedMotion) return;

    const timeout = setTimeout(() => {
      const next = Math.min(TOTAL_MINUTES, selectedMinute + 1);
      onSelectMinute(next);
      if (next === TOTAL_MINUTES) setIsPlaying(false);
    }, STEP_INTERVAL_MS);

    return () => clearTimeout(timeout);
  }, [isPlaying, reducedMotion, selectedMinute, onSelectMinute]);

  const togglePlay = () => {
    if (reducedMotion) return;
    if (isPlaying) {
      setIsPlaying(false);
    } else {
      // If at end, wrap to start
      if (selectedMinute >= TOTAL_MINUTES) {
        onSelectMinute(1);
      }
      setIsPlaying(true);
    }
  };

  const currentCount = minuteGoalCounts[String(selectedMinute)] ?? 0;

  return (
    <div className="w-full rounded-xl border border-tone-800 bg-tone-900/80 p-4">
      {/* Header with play controls */}
      <div className="mb-3 flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <button
            onClick={togglePlay}
            disabled={reducedMotion}
            className={`flex items-center gap-1.5 rounded-lg border px-3 py-1 font-semibold transition cursor-pointer ${
              isPlaying
                ? "border-gap-500/50 bg-gap-500/20 text-gap-300 hover:bg-gap-500/30"
                : "border-tone-700 bg-tone-800 text-tone-200 hover:border-tone-500 hover:bg-tone-700 hover:text-foreground"
            } ${reducedMotion ? "opacity-40 cursor-not-allowed" : ""}`}
            title={isPlaying ? "Pause clock sweep" : "Sweep clock (1 to 90 over 20s)"}
          >
            {isPlaying ? (
              <>
                <svg className="h-3 w-3 fill-current" viewBox="0 0 24 24">
                  <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
                </svg>
                Pause
              </>
            ) : (
              <>
                <svg className="h-3 w-3 fill-current" viewBox="0 0 24 24">
                  <path d="M8 5v14l11-7z" />
                </svg>
                Play sweep
              </>
            )}
          </button>

          <span className="text-tone-500">
            {isPlaying ? "Sweeping minutes…" : "Drag playhead or use ← / →"}
          </span>
        </div>

        {/* Current Playhead Value */}
        <div className="flex items-center gap-2 font-mono text-tone-400">
          <span className="text-foreground font-bold text-sm">
            {selectedMinute}′
          </span>
          <span className="text-tone-600">/ 90′</span>
          <span className="ml-1 text-[11px] rounded bg-tone-800 px-1.5 py-0.5 text-tone-300">
            {currentCount} goal{currentCount !== 1 ? "s" : ""}
          </span>
        </div>
      </div>

      {/* Histogram & Timeline Strip with Slider Accessibility */}
      <div
        ref={trackRef}
        role="slider"
        tabIndex={0}
        aria-label="Minute scrubber"
        aria-valuemin={1}
        aria-valuemax={TOTAL_MINUTES}
        aria-valuenow={selectedMinute}
        aria-valuetext={`Minute ${selectedMinute}, ${currentCount} goal${currentCount !== 1 ? "s" : ""}`}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onKeyDown={handleKeyDown}
        className="relative h-14 w-full select-none rounded-lg bg-tone-950 p-1 flex items-end cursor-pointer outline-none focus:ring-1 focus:ring-scored-500/50"
      >
        {/* 90 Histogram Bars */}
        <div className="flex h-full w-full items-end gap-[1px]">
          {Array.from({ length: TOTAL_MINUTES }, (_, i) => i + 1).map((m) => {
            const cnt = minuteGoalCounts[String(m)] ?? 0;
            const isSelected = m === selectedMinute;
            const isSpecial = m === 45 || m === 90;

            // Height scaled to maxGoals
            const heightPct =
              cnt > 0 ? Math.max(18, Math.round((cnt / maxGoals) * 100)) : 8;

            return (
              <div
                key={m}
                style={{ height: `${heightPct}%` }}
                className={`relative flex-1 rounded-t-sm transition-colors ${
                  isSelected
                    ? "bg-foreground z-10 shadow-md"
                    : cnt > 0
                    ? isSpecial
                      ? "bg-scored-400 hover:bg-scored-300"
                      : "bg-scored-500/80 hover:bg-scored-400"
                    : isSpecial
                    ? "bg-tone-700/80 hover:bg-tone-600"
                    : "bg-tone-800/60 hover:bg-tone-700"
                }`}
                title={`Minute ${m}: ${cnt} goal${cnt !== 1 ? "s" : ""}`}
              />
            );
          })}
        </div>

        {/* Draggable Playhead Needle & Thumb */}
        <div
          style={{
            left: `${((selectedMinute - 0.5) / TOTAL_MINUTES) * 100}%`,
          }}
          className="pointer-events-none absolute bottom-0 top-0 -translate-x-1/2 flex flex-col items-center z-20 transition-all duration-75"
        >
          {/* Thumb label */}
          <div className="flex h-4 items-center justify-center rounded bg-foreground px-1 text-[9px] font-bold text-tone-950 shadow-md">
            {selectedMinute}
          </div>
          {/* Needle */}
          <div className="w-[2px] flex-1 bg-foreground shadow-md" />
        </div>
      </div>

      {/* Axis markers */}
      <div className="mt-1 flex justify-between px-0.5 text-[9px] font-mono text-tone-500">
        <span>1′</span>
        <span>15′</span>
        <span>30′</span>
        <span className="text-gap-400 font-semibold">45′+</span>
        <span>60′</span>
        <span>75′</span>
        <span className="text-gap-400 font-semibold">90′+</span>
      </div>
    </div>
  );
}
