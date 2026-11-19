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

test("Haaland has five chains, with minutes 47 to 72 longest", () => {
  const counts = playerCounts(418560);
  const chains = getChains(counts);
  assert.equal(chains.length, 5);
  // Goal totals grow with live updates, so sum them from the data.
  let goals = 0;
  for (let minute = 47; minute <= 72; minute++) goals += counts[String(minute)] ?? 0;
  assert.deepEqual(chains.reduce((a, b) => a.length >= b.length ? a : b), {
    start: 47, end: 72, length: 26, goals,
  });
});

test("Lewandowski has a single chain across all 90 minutes", () => {
  // Goals in the rolling 10-year window, so the total moves as the window does.
  const player = JSON.parse(readFileSync(new URL("../data/players/38253.json", import.meta.url)));
  assert.deepEqual(getChains(player.minuteGoalCounts), [
    { start: 1, end: 90, length: 90, goals: player.regularGoals },
  ]);
});
