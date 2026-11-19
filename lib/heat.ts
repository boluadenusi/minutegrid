/** Shared absolute buckets keep the same count the same color for every player. */
export function heatLevel(count: number): 0 | 1 | 2 | 3 | 4 {
  if (count <= 0) return 0;
  if (count === 1) return 1;
  if (count === 2) return 2;
  if (count < 5) return 3;
  return 4;
}
