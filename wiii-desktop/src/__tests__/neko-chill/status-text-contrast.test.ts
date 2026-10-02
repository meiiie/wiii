import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
const theme = readFileSync(resolve(process.cwd(), "src/neko-chill/theme.css"), "utf8");

function luminance(hex: string): number {
  const channels = [1, 3, 5].map(offset => parseInt(hex.slice(offset, offset + 2), 16) / 255)
    .map(value => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}
function contrast(a: string, b: string): number {
  const values = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (values[0] + 0.05) / (values[1] + 0.05);
}
const blocks = [...theme.matchAll(/(?:^|\n)(?:\.dark )?\.nk-root \{([^}]+)\}/g)];
const foregrounds = ["text", "text-2", "text-3", "ghost", "success", "warning", "danger"];
const backgrounds = ["canvas", "sidebar", "raised", "composer", "inset"];
describe("Neko small-text token pairs (not whole-app accessibility certification)", () => {
  it("tests both light and dark palettes", () => expect(blocks).toHaveLength(2));
  blocks.forEach((block, index) => {
    const tokens = Object.fromEntries([...block[1].matchAll(/--nk-([\w-]+):\s*(#[\da-f]{6});/gi)].map(match => [match[1], match[2]]));
    const mode = index === 0 ? "light" : "dark";
    for (const fg of foregrounds) for (const bg of backgrounds) {
      it(`${mode}: ${fg} on ${bg} is at least 4.5:1`, () => {
        expect(tokens[fg]).toBeDefined(); expect(tokens[bg]).toBeDefined();
        expect(contrast(tokens[fg], tokens[bg])).toBeGreaterThanOrEqual(4.5);
      });
    }
    it(`${mode}: inverse button text is at least 4.5:1`, () => {
      expect(contrast(tokens["on-inverse"], tokens.inverse)).toBeGreaterThanOrEqual(4.5);
    });
  });
});
