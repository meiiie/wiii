import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { compile } from "tailwindcss";
import { describe, expect, it } from "vitest";

const require = createRequire(import.meta.url);
const styles = path.resolve("src/styles");

async function stylesheet(name: string) {
  return compile(await readFile(path.join(styles, name), "utf8"), {
    base: styles,
    loadStylesheet: async (id, base) => {
      const file = id.startsWith(".") ? path.resolve(base, id) : require.resolve(id);
      return { path: file, base: path.dirname(file), content: await readFile(file, "utf8") };
    },
  });
}

describe("Tailwind v3 visual compatibility", () => {
  it("preserves colors, fonts, ring defaults, hover and hidden-sibling spacing", async () => {
    const compiler = await stylesheet("globals.css");
    const css = compiler.build([
      "bg-red-500", "font-mono", "ring", "hover:bg-red-500", "dark:bg-red-500",
      "v3-space-y-1.5", "v3-divide-y", "v3-outline-none", "bg-linear-to-br",
    ]);
    expect(css).toContain("background-color: #ef4444");
    expect(css).toContain("font-family: var(--font-mono), Consolas, monospace");
    expect(css).toContain("calc(3px + var(--tw-ring-offset-width))");
    expect(css).toContain("--default-ring-color: #3b82f680");
    expect(css).toContain(":hover");
    expect(css).not.toContain("@media (hover: hover)");
    expect(css).toContain(".dark *");
    expect(css).toContain(" > :not([hidden]) ~ :not([hidden])");
    expect(css).toContain("margin-top:");
    expect(css).toContain("border-top-width:");
    expect(css).toContain("outline: 2px solid transparent");
    expect(css).toContain("to bottom right in srgb");
    expect(css).toContain("cursor: pointer");
    expect(css).toContain("#9ca3af");
  });

  it("compiles independently imported Markdown @apply rules", async () => {
    const compiler = await stylesheet("markdown.css");
    const css = compiler.build([]);
    expect(css).toContain(".markdown-content h1");
    expect(css).toContain("--font-weight-bold");
    expect(css).not.toContain("@apply");
  });

  it("does not emit utilities for an empty or unknown candidate set", async () => {
    const compiler = await stylesheet("globals.css");
    const empty = compiler.build([]);
    expect(compiler.build(["not-a-tailwind-utility"])).toBe(empty);
    expect(empty).not.toContain(".not-a-tailwind-utility");
  });
});
