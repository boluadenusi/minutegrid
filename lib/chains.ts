export interface Chain {
  start: number;
  end: number;
  length: number;
  goals: number;
}

/** Consecutive scored minutes in the regulation 1–90 grid. */
export function getChains(counts: Record<string, number>): Chain[] {
  const chains: Chain[] = [];
  let current: Chain | undefined;

  for (let minute = 1; minute <= 90; minute++) {
    const count = counts[String(minute)] ?? 0;
    if (count > 0) {
      if (!current) {
        current = { start: minute, end: minute, length: 0, goals: 0 };
        chains.push(current);
      }
      current.end = minute;
      current.length++;
      current.goals += count;
    } else {
      current = undefined;
    }
  }
  return chains;
}
