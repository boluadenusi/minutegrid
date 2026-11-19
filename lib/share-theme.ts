import { readFileSync } from "node:fs";
import { join } from "node:path";
import { heatLevel } from "./heat";

const css = readFileSync(join(process.cwd(), "app", "theme.css"), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");

function token(name: string): string {
  const match = [...css.matchAll(new RegExp(`^\\s*--${name}:\\s*([^;]+);`, "gm"))].at(-1);
  if (!match) throw new Error(`Missing share theme token: ${name}`);
  return match[1].trim().replace(/^"|"$/g, "");
}

const fontFiles: Record<string, Buffer> = {
  "jersey15.ttf": readFileSync(join(process.cwd(), "app", "fonts", "jersey15.ttf")),
  "rubik.ttf": readFileSync(join(process.cwd(), "app", "fonts", "rubik.ttf")),
  "rubik-bold.ttf": readFileSync(join(process.cwd(), "app", "fonts", "rubik-bold.ttf")),
  "bricolage.ttf": readFileSync(join(process.cwd(), "app", "fonts", "bricolage.ttf")),
  "bricolage-bold.ttf": readFileSync(join(process.cwd(), "app", "fonts", "bricolage-bold.ttf")),
  "newsreader.ttf": readFileSync(join(process.cwd(), "app", "fonts", "newsreader.ttf")),
  "newsreader-bold.ttf": readFileSync(join(process.cwd(), "app", "fonts", "newsreader-bold.ttf")),
  "cormorant.ttf": readFileSync(join(process.cwd(), "app", "fonts", "cormorant.ttf")),
  "cormorant-bold.ttf": readFileSync(join(process.cwd(), "app", "fonts", "cormorant-bold.ttf")),
  "literata.ttf": readFileSync(join(process.cwd(), "app", "fonts", "literata.ttf")),
  "literata-bold.ttf": readFileSync(join(process.cwd(), "app", "fonts", "literata-bold.ttf")),
};

function fontFile(name: string, bold = false): Buffer {
  const filename = token(name);
  const file = fontFiles[bold ? filename.replace(".ttf", "-bold.ttf") : filename];
  if (!file) throw new Error(`Unknown share font for ${name}`);
  return file;
}

export const shareTheme = {
  background: token("background"),
  foreground: token("foreground"),
  card: token("card"),
  muted: token("muted-foreground"),
  accent: token("accent"),
  gap: token("gap"),
  heatText: token("heat-text"),
  heatOneText: token("heat-1-text"),
  bodyFont: token("og-body-name"),
  displayFont: token("og-display-name"),
  fonts: [
    { name: token("og-body-name"), data: fontFile("og-body-file"), weight: 400 as const, style: "normal" as const },
    { name: token("og-body-name"), data: fontFile("og-body-file", true), weight: 700 as const, style: "normal" as const },
    { name: token("og-display-name"), data: fontFile("og-display-file"), weight: 400 as const, style: "normal" as const },
  ],
};

export function shareHeat(count: number) {
  const level = heatLevel(count);
  return {
    background: level ? token(`heat-${level}`) : shareTheme.card,
    color: level === 1 ? shareTheme.heatOneText : level ? shareTheme.heatText : shareTheme.gap,
  };
}
