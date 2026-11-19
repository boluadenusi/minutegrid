import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import React from "react";
import { ImageResponse } from "next/og.js";
import { heatLevel } from "../lib/heat.ts";

test("heat levels distinguish one goal and increase with count", () => {
  assert.deepEqual([0, 1, 2, 3, 4, 5, 50].map(heatLevel), [0, 1, 2, 3, 3, 4, 4]);
});

const source = readFileSync(new URL("../app/theme.css", import.meta.url), "utf8");
const css = source.replace(/\/\*[\s\S]*?\*\//g, "");
function color(name, stylesheet = css) {
  const values = [...stylesheet.matchAll(new RegExp(`--${name}:\\s*#([\\da-f]{6});`, "gi"))];
  assert.ok(values.length, `Missing hex token ${name}`);
  return values.at(-1)[1].match(/../g).map((part) => parseInt(part, 16) / 255);
}
function luminance(rgb, matrix = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]) {
  const linear = rgb.map((v) => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
  return matrix.reduce((sum, row, i) => sum + [0.2126, 0.7152, 0.0722][i] *
    Math.max(0, Math.min(1, row.reduce((value, coefficient, j) => value + coefficient * linear[j], 0))), 0);
}
function contrast(a, b, stylesheet = css) {
  const [low, high] = [luminance(color(a, stylesheet)), luminance(color(b, stylesheet))].sort((x, y) => x - y);
  return (high + 0.05) / (low + 0.05);
}

test("body text and heat labels meet AA on their surfaces", () => {
  for (const [foreground, background] of [
    ["foreground", "background"], ["foreground", "card"], ["muted-foreground", "background"],
    ["muted-foreground", "card"], ["foreground", "surface-hover"], ["heat-1-text", "heat-1"], ["heat-text", "heat-2"],
    ["heat-text", "heat-3"], ["heat-text", "heat-4"],
  ]) assert.ok(contrast(foreground, background) >= 4.5, `${foreground} on ${background}`);
});

test("the one-file alternate packs retain accessible text and heat labels", () => {
  const presets = [...source.matchAll(/\/\*\s*(:root \{[\s\S]*?\})\s*\*\//g)];
  assert.equal(presets.length, 2);
  for (const [, preset] of presets) {
    const stylesheet = `${css}\n${preset}`;
    for (const [foreground, background] of [
      ["foreground", "background"], ["muted-foreground", "card"], ["foreground", "surface-hover"], ["heat-1-text", "heat-1"],
      ["heat-text", "heat-2"], ["heat-text", "heat-3"], ["heat-text", "heat-4"],
    ]) assert.ok(contrast(foreground, background, stylesheet) >= 4.5, `${foreground} on ${background}`);
  }
});

test("heat steps remain ordered under simulated color-vision deficiencies", () => {
  const matrices = [
    [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
    [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],
    [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]],
  ];
  for (const matrix of matrices) {
    const values = ["background", "heat-1", "heat-2", "heat-3", "heat-4"].map((name) => luminance(color(name), matrix));
    assert.ok((values[1] + 0.05) / (values[0] + 0.05) >= 3);
    for (let i = 2; i < values.length; i++) assert.ok((values[i] + 0.05) / (values[i - 1] + 0.05) >= 1.1);
  }
});

test("each selectable font renders through next/og", async () => {
  for (const file of ["jersey15.ttf", "rubik.ttf", "rubik-bold.ttf", "bricolage.ttf", "bricolage-bold.ttf",
    "newsreader.ttf", "newsreader-bold.ttf", "cormorant.ttf", "cormorant-bold.ttf", "literata.ttf", "literata-bold.ttf"]) {
    const data = readFileSync(new URL(`../app/fonts/${file}`, import.meta.url));
    const response = new ImageResponse(React.createElement("div", { style: { fontFamily: "test" } }, "Minute 45"), {
      width: 200, height: 100, fonts: [{ name: "test", data, weight: 400, style: "normal" }],
    });
    assert.ok((await response.arrayBuffer()).byteLength > 0, file);
  }
});
