import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  config: vi.fn(),
  monaco: { editor: { create: vi.fn() } },
  editor: vi.fn(),
  diff: vi.fn(),
  workers: Object.fromEntries(["editor", "json", "css", "html", "typescript"].map(
    (kind) => [kind, vi.fn(class { readonly kind = kind; })],
  )),
}));

vi.mock("@monaco-editor/react", () => ({
  Editor: mocks.editor,
  DiffEditor: mocks.diff,
  loader: { config: mocks.config },
}));
vi.mock("monaco-editor", () => mocks.monaco);
vi.mock("monaco-editor/esm/vs/editor/editor.worker?worker", () => ({ default: mocks.workers.editor }));
vi.mock("monaco-editor/esm/vs/language/json/json.worker?worker", () => ({ default: mocks.workers.json }));
vi.mock("monaco-editor/esm/vs/language/css/css.worker?worker", () => ({ default: mocks.workers.css }));
vi.mock("monaco-editor/esm/vs/language/html/html.worker?worker", () => ({ default: mocks.workers.html }));
vi.mock("monaco-editor/esm/vs/language/typescript/ts.worker?worker", () => ({ default: mocks.workers.typescript }));

describe("offline workspace Monaco", () => {
  it("gives the React loader the local engine once, even for concurrent imports", async () => {
    const [files, diff] = await Promise.all([
      import("@/neko-chill/workspace-monaco"),
      import("@/neko-chill/workspace-monaco"),
    ]);
    expect(files.Editor).toBe(mocks.editor);
    expect(diff.DiffEditor).toBe(mocks.diff);
    expect(mocks.config).toHaveBeenCalledExactlyOnceWith({ monaco: mocks.monaco });
  });

  it.each([
    ["editorWorkerService", "editor"], ["plaintext", "editor"], ["unknown", "editor"],
    ["json", "json"], ["css", "css"], ["scss", "css"], ["less", "css"],
    ["html", "html"], ["handlebars", "html"], ["razor", "html"],
    ["typescript", "typescript"], ["javascript", "typescript"],
  ])("routes %s to a new local %s worker", (label, kind) => {
    const getWorker = globalThis.MonacoEnvironment!.getWorker!;
    const first = getWorker("unused", label);
    const second = getWorker("unused", label);
    expect(first).toBeInstanceOf(mocks.workers[kind]);
    expect(second).toBeInstanceOf(mocks.workers[kind]);
    expect(first).not.toBe(second);
  });

  it("keeps both workspace editors behind the configured lazy module", () => {
    const pane = readFileSync(resolve(process.cwd(), "src/neko-chill/components/NekoWorkspacePane.tsx"), "utf8");
    expect(pane.match(/await import\("\.\.\/workspace-monaco"\)/g)).toHaveLength(2);
    expect(pane).not.toContain('import("@monaco-editor/react")');
  });
});
