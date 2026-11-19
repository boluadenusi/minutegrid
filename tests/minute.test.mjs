import { test } from "node:test";
import assert from "node:assert/strict";
import { getInitialMinute } from "../lib/minute.ts";

test("valid minute links select the requested minute", () => {
  for (const minute of [1, 8, 21, 46, 90]) {
    assert.equal(getInitialMinute(String(minute)), minute);
  }
});

test("invalid or ambiguous minute links use the normal initial playhead", () => {
  for (const minute of [undefined, "", "0", "91", "-1", "1.5", "08", "1x", ["8", "9"]]) {
    assert.equal(getInitialMinute(minute), 1);
  }
});
