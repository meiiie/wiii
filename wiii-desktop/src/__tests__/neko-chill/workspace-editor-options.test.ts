import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { WORKSPACE_CODE_EDITOR_OPTIONS } from "@/neko-chill/workspace-editor-options";

describe("workspace code editor gutter", () => {
  it("keeps one numbered gutter row per source line", () => {
    expect(WORKSPACE_CODE_EDITOR_OPTIONS.wordWrap).toBe("off");
    expect(WORKSPACE_CODE_EDITOR_OPTIONS.lineNumbers).toBe("on");
    expect(WORKSPACE_CODE_EDITOR_OPTIONS.lineNumbersMinChars).toBeGreaterThanOrEqual(4);
    expect(WORKSPACE_CODE_EDITOR_OPTIONS.stickyScroll).toEqual({ enabled: false });
    expect(WORKSPACE_CODE_EDITOR_OPTIONS.letterSpacing).toBe(0);
  });

  it("neutralizes react-shiki's legacy line-number counter inside Monaco", () => {
    const globalsCss = readFileSync(resolve(process.cwd(), "src/styles/globals.css"), "utf8");
    const monacoOverride = globalsCss.match(
      /\.monaco-editor\s+\.margin-view-overlays\s+\.line-numbers::before\s*\{([^}]*)\}/,
    );

    expect(monacoOverride?.[1]).toContain("content: none");
    expect(monacoOverride?.[1]).toContain("counter-increment: none");
    expect(monacoOverride?.[1]).toContain("display: none");
  });
});
