"use client";

import { useState, useEffect } from "react";
import type { GoalDetail } from "@/lib/data";
import { formatCompetition, formatGoalDate } from "@/lib/goal-format";
import { Collapsible, CollapsibleContent, CollapsibleIndicator, CollapsibleTrigger } from "@/components/motion/collapsible";

interface GoalDetailPanelProps {
  minute: number;
  count: number;
  goals: GoalDetail[];
  isSpecial?: boolean; // 45 or 90
}

function GoalsList({ goals }: { goals: GoalDetail[] }) {
  return (
    <ul className="divide-y divide-tone-800/60 rounded-lg border border-tone-800 bg-tone-950/60 overflow-hidden">
      {goals.map((g, idx) => (
        <li key={`${g.date}-${g.opponent}-${idx}`}
          className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 px-4 py-2.5 text-xs hover:bg-tone-800/40 transition">
          <div className="flex items-center gap-2">
            <span className="text-tone-500 font-mono text-[11px] min-w-[75px]">{formatGoalDate(g.date)}</span>
            <span className="text-foreground font-medium">vs {g.opponent}</span>
          </div>
          <div className="flex items-center gap-3 text-tone-400 text-[11px]">
            <span className="rounded bg-tone-800/80 px-2 py-0.5 text-tone-300 font-medium">{formatCompetition(g.competition)}</span>
            {g.club && g.club !== "Unknown" && <span className="text-tone-500 hidden md:inline">({g.club})</span>}
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function GoalDetailPanel({
  minute,
  count,
  goals,
  isSpecial = false,
}: GoalDetailPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Reset expansion when minute changes
  useEffect(() => {
    setIsExpanded(false);
  }, [minute]);

  const remainingCount = goals.length - 5;

  return (
    <div className="w-full rounded-xl border border-tone-800 bg-tone-900/90 p-5 backdrop-blur transition-opacity duration-300">
      {/* Minute Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-tone-800 pb-3 mb-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-scored-500/10 border border-scored-500/20 text-foreground font-bold text-base font-mono">
            {minute}′
          </div>
          <div>
            <h3 className="text-base font-bold text-foreground flex items-center gap-2">
              Minute {minute}
              {isSpecial && (
                <span className="text-[10px] rounded bg-gap-500/20 text-gap-300 border border-gap-500/30 px-2 py-0.5 font-normal">
                  Added time included
                </span>
              )}
            </h3>
            <p className="text-xs text-tone-400">
              {count > 0 ? (
                <span>
                  <strong className="text-foreground">{count}</strong> goal
                  {count !== 1 ? "s" : ""} scored in this minute
                </span>
              ) : (
                <span className="text-gap-400 font-medium">Gap minute</span>
              )}
            </p>
          </div>
        </div>

        {/* Added time explanatory note for 45 and 90 */}
        {isSpecial && (
          <div className="text-right text-xs text-gap-300/90 bg-gap-950/40 border border-gap-500/20 rounded-lg px-3 py-1.5">
            Includes added-time goals
          </div>
        )}
      </div>

      {/* Content: Goals List or Gap Message */}
      {count === 0 ? (
        <div className="flex items-center gap-3 rounded-lg border border-gap-500/30 bg-gap-950/20 p-4 text-gap-200">
          <div className="flex h-7 w-7 items-center justify-center rounded-full border-2 border-gap-400/80 bg-gap-500/10 shadow">
            <span className="h-2 w-2 rounded-full bg-gap-400 animate-pulse" />
          </div>
          <div>
            <p className="text-sm font-semibold text-gap-300">
              Never scored in minute {minute}
            </p>
            <p className="text-xs text-tone-400 mt-0.5">
              This minute remains one of the player&apos;s silent gaps on the clock.
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <GoalsList goals={goals.slice(0, 5)} />
          {remainingCount > 0 && (
            <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
              <CollapsibleTrigger className="w-fit rounded-lg border border-scored-500/20 bg-scored-500/10 px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-scored-500/20 hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-scored-400">
                {isExpanded ? "Show less" : `+${remainingCount} more goal${remainingCount !== 1 ? "s" : ""}`}
                <CollapsibleIndicator className="text-foreground" />
              </CollapsibleTrigger>
              <CollapsibleContent contentClassName="pt-2">
                <GoalsList goals={goals.slice(5)} />
              </CollapsibleContent>
            </Collapsible>
          )}
        </div>
      )}
    </div>
  );
}
