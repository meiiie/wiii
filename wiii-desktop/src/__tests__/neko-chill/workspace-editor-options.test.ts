import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";
import type { editor } from "monaco-editor";

import { syncWorkspaceDiffTabOrder, WORKSPACE_CODE_EDITOR_OPTIONS } from "@/neko-chill/workspace-editor-options";

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

describe("workspace diff keyboard navigation", () => {
  function fixture(initialContentWidth: number) {
    const originalInput = document.createElement("textarea");
    const modifiedInput = document.createElement("textarea");
    let layout = { contentWidth: initialContentWidth } as editor.EditorLayoutInfo;
    const layoutListeners = new Set<(layout: editor.EditorLayoutInfo) => void>();
    let onDispose = () => {};
    const original = {
      getLayoutInfo: () => layout,
      updateOptions: (options: editor.IEditorOptions) => {
        if (options.tabIndex !== undefined) originalInput.tabIndex = options.tabIndex;
      },
      onDidLayoutChange: (listener: (layout: editor.EditorLayoutInfo) => void) => {
        layoutListeners.add(listener);
        return { dispose: () => layoutListeners.delete(listener) };
      },
    };
    syncWorkspaceDiffTabOrder({
      getOriginalEditor: () => original,
      onDidDispose: (listener: () => void) => { onDispose = listener; },
    } as unknown as editor.IDiffEditor);
    return {
      originalInput,
      modifiedInput,
      layoutListeners,
      resize: (contentWidth: number) => {
        layout = { ...layout, contentWidth };
        for (const listener of layoutListeners) listener(layout);
      },
      dispose: () => onDispose(),
    };
  }

  it.each([0, -40])("skips a hidden/gutter-only original (%s) without removing the visible diff", (width) => {
    const diff = fixture(width);
    expect(diff.originalInput.tabIndex).toBe(-1);
    expect(diff.modifiedInput.tabIndex).toBe(0);
    diff.dispose();
  });

  it("keeps a visible original keyboard-reachable in side-by-side view", () => {
    const diff = fixture(400);
    expect(diff.originalInput.tabIndex).toBe(0);
    expect(diff.modifiedInput.tabIndex).toBe(0);
    diff.dispose();
  });

  it("restores the original on expansion and skips it again on collapse", () => {
    const diff = fixture(0);
    diff.resize(400);
    expect(diff.originalInput.tabIndex).toBe(0);
    diff.resize(-40);
    expect(diff.originalInput.tabIndex).toBe(-1);
    expect(diff.modifiedInput.tabIndex).toBe(0);
    diff.dispose();
  });

  it("stops observing layout when the diff is disposed", () => {
    const diff = fixture(0);
    diff.dispose();
    expect(diff.layoutListeners.size).toBe(0);
    diff.resize(400);
    expect(diff.originalInput.tabIndex).toBe(-1);
  });
});
