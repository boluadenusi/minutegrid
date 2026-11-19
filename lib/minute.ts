/** Parses a regulation-minute URL parameter, defaulting to minute 1. */
export function getInitialMinute(value: string | string[] | undefined): number {
  return typeof value === "string" && /^(?:[1-9]|[1-8]\d|90)$/.test(value)
    ? Number(value)
    : 1;
}
