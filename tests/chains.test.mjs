import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { getChains } from "../lib/chains.ts";

function playerCounts(id) {
  return JSON.parse(readFileSync(new URL(`../data/players/${id}.json`, import.meta.url))).minuteGoalCounts;
}

test("chains stop at gaps, sum goals, and are limited to minutes 1 to 90", () => {
  assert.deepEqual(getChains({ 1: 2, 2: 3, 4: 1, 90: 4, 91: 9 }), [
    { start: 1, end: 2, length: 2, goals: 5 },
    { start: 4, end: 4, length: 1, goals: 1 },
    { start: 90, end: 90, length: 1, goals: 4 },
  ]);
  assert.deepEqual(getChains({}), []);
});

// Frozen shape of Haaland's grid (Nov 2026); live data can merge or split these chains.
test("five chains with 47 to 72 longest, from a fixed grid", () => {
  const counts = {};
  for (const [start, end] of [[2, 7], [9, 20], [22, 45], [47, 72], [74, 90]]) {
    for (let minute = start; minute <= end; minute++) counts[minute] = 1;
  }
  counts[50] = 3;
  const chains = getChains(counts);
  assert.equal(chains.length, 5);
  assert.deepEqual(chains.reduce((a, b) => a.length >= b.length ? a : b), {
    start: 47, end: 72, length: 26, goals: 28,
  });
});

// Holds whatever minutes the data update adds or drops.
test("Haaland's live chains cover exactly his scored minutes 1 to 90", () => {
  const counts = playerCounts(418560);
  const chains = getChains(counts);
  const scored = Object.keys(counts).map(Number).filter((m) => m >= 1 && m <= 90 && counts[m] > 0);
  assert.equal(chains.reduce((sum, c) => sum + c.length, 0), scored.length);
  chains.forEach((chain, i) => {
    assert.ok(chain.start >= 1 && chain.end <= 90 && chain.length === chain.end - chain.start + 1);
    let goals = 0;
    for (let m = chain.start; m <= chain.end; m++) goals += counts[String(m)] ?? 0;
    assert.equal(chain.goals, goals);
    if (i > 0) assert.ok(chain.start > chains[i - 1].end + 1, "chains never touch");
  });
});

test("a player with every minute has a single chain across all 90 minutes", () => {
  const counts = Object.fromEntries(Array.from({ length: 90 }, (_, i) => [String(i + 1), 2]));
  assert.deepEqual(getChains(counts), [{ start: 1, end: 90, length: 90, goals: 180 }]);
});
