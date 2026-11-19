import { strict as assert } from "node:assert";
import { test } from "node:test";
import { searchPlayerCommands } from "../lib/player-search.ts";

test("player search only shows results after typing", () => {
  const players = [{ id: 1, name: "Erling Haaland", goalCount: 100 }];
  assert.deepEqual(searchPlayerCommands(players, "  "), []);
});

test("player search matches names case-insensitively and limits results", () => {
  const players = Array.from({ length: 25 }, (_, id) => ({
    id, name: `Player ${id}`, goalCount: id,
  }));
  assert.deepEqual(searchPlayerCommands(players, "PLAYER").map((player) => player.id),
    Array.from({ length: 20 }, (_, id) => id));
  assert.equal(searchPlayerCommands(players, "player 24")[0].id, 24);
});
