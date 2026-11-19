export type MinuteOwner = "both" | "a" | "b" | "none";

export interface ComparedMinute {
  minute: number;
  a: number;
  b: number;
  owner: MinuteOwner;
}

export interface Comparison {
  minutes: ComparedMinute[];
  both: number[];
  onlyA: number[];
  onlyB: number[];
  neither: number[];
}

/** Minute-by-minute comparison of two players' regulation grids (1–90). */
export function compareMinutes(a: Record<string, number>, b: Record<string, number>): Comparison {
  const result: Comparison = { minutes: [], both: [], onlyA: [], onlyB: [], neither: [] };
  for (let minute = 1; minute <= 90; minute++) {
    const countA = a[String(minute)] ?? 0;
    const countB = b[String(minute)] ?? 0;
    const owner: MinuteOwner = countA > 0 && countB > 0 ? "both" : countA > 0 ? "a" : countB > 0 ? "b" : "none";
    result.minutes.push({ minute, a: countA, b: countB, owner });
    ({ both: result.both, a: result.onlyA, b: result.onlyB, none: result.neither })[owner].push(minute);
  }
  return result;
}

/** Parses ?a=&b= values: a positive whole number, else null. */
export function parsePlayerId(value: string | string[] | undefined): number | null {
  if (typeof value !== "string" || !/^[1-9]\d{0,9}$/.test(value)) return null;
  return Number(value);
}
