"use client";

import { useMemo } from "react";

interface MinuteGridProps {
  minutesScored: number[];
  minuteGoalCounts: Record<string, number>;
  extraTimeMinutes: number[];
}

const COLS = 10;
const ROWS = 9; // 9 rows × 10 cols = 90

export default function MinuteGrid({
  minutesScored,
  minuteGoalCounts,
  extraTimeMinutes,
}: MinuteGridProps) {
  const scoredSet = useMemo(() => new Set(minutesScored), [minutesScored]);
  const extraSet = useMemo(() => new Set(extraTimeMinutes), [extraTimeMinutes]);

  return (
    <div>
      {/* Main 90-cell grid */}
      <div
        className="grid gap-1"
        style={{ gridTemplateColumns: `repeat(${COLS}, minmax(0, 1fr))` }}
      >
        {Array.from({ length: 90 }, (_, i) => i + 1).map((minute) => {
          const scored = scoredSet.has(minute);
          const count = minuteGoalCounts[String(minute)] ?? 0;
          const isSpecial = minute === 45 || minute === 90;

          return (
            <div
              key={minute}
              title={
                scored
                  ? `${count} goal${count !== 1 ? "s" : ""} in minute ${minute}${isSpecial ? " (incl. stoppage time)" : ""}`
                  : `No goals in minute ${minute}${isSpecial ? " (incl. stoppage time)" : ""}`
              }
              className={[
                "relative flex flex-col items-center justify-center rounded aspect-square select-none transition-transform hover:scale-110 cursor-default",
                scored
                  ? "bg-emerald-500 text-white shadow-lg shadow-emerald-500/30"
                  : "bg-zinc-800 text-zinc-500",
                isSpecial && scored
                  ? "ring-2 ring-offset-1 ring-offset-zinc-950 ring-amber-400"
                  : "",
                isSpecial && !scored
                  ? "ring-1 ring-inset ring-zinc-600"
                  : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <span className="text-[10px] font-semibold leading-none">{minute}</span>
              {isSpecial && (
                <span
                  className={`text-[7px] leading-none mt-0.5 ${scored ? "text-amber-200" : "text-zinc-600"}`}
                >
                  +
                </span>
              )}
              {scored && count > 1 && (
                <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-amber-400 text-[8px] font-bold text-zinc-900">
                  {count}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Extra-time strip */}
      {extraTimeMinutes.length > 0 && (
        <div className="mt-4">
          <p className="text-xs text-zinc-500 mb-2 uppercase tracking-wider font-medium">
            Extra Time
          </p>
          <div className="flex flex-wrap gap-1">
            {extraTimeMinutes.map((minute) => {
              const count = minuteGoalCounts[String(minute)] ?? 0;
              return (
                <div
                  key={minute}
                  title={`${count} goal${count !== 1 ? "s" : ""} in minute ${minute} (extra time)`}
                  className="relative flex items-center justify-center rounded bg-violet-600 text-white px-2 py-1 text-[10px] font-semibold shadow shadow-violet-600/30 hover:scale-110 transition-transform cursor-default"
                >
                  {minute}′
                  {count > 1 && (
                    <span className="ml-1 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-amber-400 text-[7px] font-bold text-zinc-900">
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
