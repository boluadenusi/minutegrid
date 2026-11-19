import { strict as assert } from "node:assert";
import { test } from "node:test";
import { chainLinkGeometry } from "../lib/chain-geometry.ts";

test("horizontal links start at the rectangle edge and end before the next", () => {
  const link = chainLinkGeometry(1, 60, 60);
  assert.equal(link.path, "M 50 30 H 67");
  assert.equal(link.arrowPath, "M 61 27 L 67 30 L 61 33 Z");
});

test("row links leave the bottom and approach the next row from above", () => {
  const link = chainLinkGeometry(10, 60, 60);
  assert.equal(link.path, "M 570 45 V 60 H 30 V 72");
  assert.equal(link.arrowPath, "M 27 66 L 30 72 L 33 66 Z");
});

test("share card links align with the same rectangles in its wider grid", () => {
  assert.equal(chainLinkGeometry(1, 100, 46).path, "M 70 23 H 127");
  const link = chainLinkGeometry(10, 100, 46);
  assert.equal(link.path, "M 950 38 V 46 H 50 V 51");
  assert.equal(link.arrowPath, "M 47 45 L 50 51 L 53 45 Z");
});
