import type { ExtraTimeGoalDetail } from "@/lib/data";

export default function ExtraTimeStrip({
  minutes,
  counts,
  details,
}: {
  minutes: number[];
  counts: Record<string, number>;
  details: ExtraTimeGoalDetail[];
}) {
  if (minutes.length === 0) return null;

  return (
    <section className="rounded-xl border border-tone-800/80 bg-tone-900/40 p-3" aria-label="Extra time goals">
      <h2 className="text-xs text-tone-500 mb-2 uppercase tracking-wider font-semibold">
        Extra Time (minute &gt; 90)
      </h2>
      <div className="flex flex-wrap gap-1.5">
        {minutes.map((minute) => {
          const count = counts[String(minute)] ?? 0;
          const firstDate = details.find((goal) => goal.minute === minute)?.firstDate;
          const label = `${count} goal${count !== 1 ? "s" : ""} in minute ${minute} (extra time)${firstDate ? ` · First: ${firstDate}` : ""}`;
          return (
            <span key={minute} title={label} aria-label={label}
              className="relative flex items-center justify-center rounded bg-extra-600 text-foreground px-2.5 py-1 text-[11px] font-semibold shadow shadow-extra-600/30">
              {minute}′
              {count > 1 && <span className="ml-1.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-gap-400 text-[8px] font-bold text-tone-900">{count}</span>}
            </span>
          );
        })}
      </div>
    </section>
  );
}
