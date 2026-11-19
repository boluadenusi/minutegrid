import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { applyWindow, currentWindow, todayIso, windowedBoards, windowStartFor } from "../lib/window.ts";

test("the window starts on the same day ten years back", () => {
  assert.equal(windowStartFor("2026-11-18"), "2016-11-18");
  assert.equal(windowStartFor("2026-11-19"), "2016-11-19");
  assert.equal(windowStartFor("2028-02-29"), "2018-02-28");
  assert.equal(todayIso(new Date("2026-11-18T23:59:00Z")), "2026-11-18");
  assert.deepEqual(currentWindow(new Date("2026-11-19T00:01:00Z")), { start: "2016-11-19", end: "2026-11-19" });
});

const goal = (date, source) => ({ date, opponent: "X", competition: "c", club: "Y", ...(source ? { source } : {}) });

function player(minutes, extraTime = []) {
  const all = {};
  for (let m = 1; m <= 90; m++) {
    const goals = minutes[m] ?? [];
    all[m] = { count: goals.length, firstDate: goals[0]?.date ?? null, goals };
  }
  return { id: 1, name: "P", minutes: all, extraTime, minuteGoalCounts: {}, minutesScored: [], extraTimeMinutes: [],
    missingMinutes: [], totalGoals: 0, regularGoals: 0, extraGoals: 0, minutesScoredCount: 0, dataUpTo: "2026-11-14" };
}

test("a goal drops out the day after it turns ten years old", () => {
  const p = player({ 5: [goal("2016-11-18"), goal("2020-01-01")], 9: [goal("2016-11-18")] },
    [{ minute: 105, count: 1, firstDate: "2016-11-18", goals: [goal("2016-11-18")] }]);
  const today = applyWindow(p, { start: "2016-11-18", end: "2026-11-18" });
  assert.equal(today.totalGoals, 4);
  assert.deepEqual(today.extraTimeMinutes, [105]);
  const tomorrow = applyWindow(p, { start: "2016-11-19", end: "2026-11-19" });
  assert.equal(tomorrow.totalGoals, 1);
  assert.equal(tomorrow.minutes["5"].count, 1);
  assert.equal(tomorrow.minutes["5"].firstDate, "2020-01-01");
  assert.ok(tomorrow.missingMinutes.includes(9));
  assert.deepEqual(tomorrow.extraTime, []);
  assert.equal(tomorrow.windowStart, "2016-11-19");
});

test("gap closed is recomputed from what is left", () => {
  const p = player({ 7: [goal("2016-11-18"), goal("2026-11-10", "pitchapi")] });
  assert.equal(applyWindow(p, { start: "2016-11-18", end: "2026-11-18" }).minutes["7"].gapClosed, undefined);
  assert.equal(applyWindow(p, { start: "2016-11-19", end: "2026-11-19" }).minutes["7"].gapClosed, "2026-11-10");
});

test("boards drop a player whose window loses a minute", () => {
  const counts = Array(90).fill(1);
  const complete = player(Object.fromEntries(counts.map((_, i) => [i + 1, [goal(i === 0 ? "2016-11-18" : "2020-01-01")]])));
  const boards = { complete: [{ id: 1, name: "P", goals: 90, missing: [], lastGoalDate: "2020-01-01", counts }], almost: [] };
  const later = windowedBoards(boards, () => applyWindow(complete, { start: "2016-11-19", end: "2026-11-19" }));
  assert.equal(later.complete.length, 0);
  assert.deepEqual(later.almost[0].missing, [1]);
});

test("real data: Mbappé's file still reads as windowed", () => {
  const raw = JSON.parse(readFileSync(new URL("../data/players/342229.json", import.meta.url)));
  const windowed = applyWindow(raw, currentWindow());
  assert.ok(windowed.totalGoals <= raw.totalGoals);
  assert.equal(windowed.minutesScoredCount, 90 - windowed.missingMinutes.length);
});
