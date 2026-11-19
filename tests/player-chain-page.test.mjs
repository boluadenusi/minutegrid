import { test } from "node:test";
import assert from "node:assert/strict";

const baseUrl = process.env.TEST_BASE_URL ?? "http://localhost:3011";

for (const query of ["", "?view=chain", "?view=grid&minute=45"]) {
  test(`player page renders only chains for ${query || "the default URL"}`, async () => {
    const response = await fetch(`${baseUrl}/player/418560${query}`);
    assert.equal(response.status, 200);
    const html = await response.text();
    assert.ok(html.includes('aria-label="Scoring chains"'), "chain view is rendered on the server");
    assert.equal((html.match(/class="chain-node /g) ?? []).length, 90);
    assert.ok(!html.includes('aria-label="Visualization view"'), "view toggle is absent");
    assert.ok(html.includes('aria-label="Extra time goals"'), "extra-time minutes remain visible");
    assert.ok(/property="og:image"[^>]+\/player\/418560\/chain-image/.test(html), "chain share card is used");
    if (query.includes("minute=45")) assert.ok(html.includes('aria-valuenow="45"'));
  });
}
