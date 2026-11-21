import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { compareMinutes, parsePlayerId } from "../lib/compare.ts";

test("minutes are split into both, only A, only B and neither", () => {
  const result = compareMinutes({ 1: 2, 2: 1, 91: 5 }, { 2: 3, 3: 1 });
  assert.deepEqual(result.both, [2]);
  assert.deepEqual(result.onlyA, [1]);
  assert.deepEqual(result.onlyB, [3]);
  assert.equal(result.neither.length, 87);
  assert.deepEqual(result.minutes[1], { minute: 2, a: 1, b: 3, owner: "both" });
  assert.equal(result.minutes.length, 90);
});

test("a complete player against Haaland adds up to 90 minutes", () => {
  const haaland = JSON.parse(readFileSync(new URL("../data/players/418560.json", import.meta.url))).minuteGoalCounts;
  const complete = Object.fromEntries(Array.from({ length: 90 }, (_, i) => [String(i + 1), 1]));
  const result = compareMinutes(complete, haaland);
  assert.equal(result.both.length + result.onlyA.length + result.onlyB.length + result.neither.length, 90);
  assert.equal(result.onlyB.length, 0); // A has every minute
});

test("player ids in the URL", () => {
  assert.equal(parsePlayerId("418560"), 418560);
  for (const bad of [undefined, "", "0", "-1", "1.5", "08", "abc", ["1", "2"]]) assert.equal(parsePlayerId(bad), null);
});
