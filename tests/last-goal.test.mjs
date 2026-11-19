import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { formatGoalMinute, getLastGoal } from "../lib/last-goal.ts";

const goal = (date, extra = {}) => ({ date, opponent: "X", competition: "serie-a", club: "Y", ...extra });

function player(minutes, extraTime = []) {
  const all = {};
  for (let m = 1; m <= 90; m++) all[m] = { count: 0, firstDate: null, goals: minutes[m] ?? [] };
  return { minutes: all, extraTime };
}

test("latest date wins, then latest minute on the same day", () => {
  const last = getLastGoal(player({ 10: [goal("2026-11-14")], 81: [goal("2026-11-14")], 88: [goal("2026-10-01")] }));
  assert.equal(last.minute, 81);
  assert.equal(last.date, "2026-11-14");
});

test("extra-time goals count and are labelled", () => {
  const last = getLastGoal(player({ 30: [goal("2026-07-01")] }, [{ minute: 112, count: 1, firstDate: "2026-07-01", goals: [goal("2026-07-01")] }]));
  assert.equal(formatGoalMinute(last), "112' (ET)");
});

test("added time and no goals", () => {
  assert.equal(formatGoalMinute({ minute: 90, extraTime: false, addedTime: true }), "90+'");
  assert.equal(getLastGoal(player({})), null);
});

test("Haaland's last goal comes from the built data", () => {
  const data = JSON.parse(readFileSync(new URL("../data/players/418560.json", import.meta.url)));
  const last = getLastGoal(data);
  assert.ok(last && last.date <= data.dataUpTo);
});
