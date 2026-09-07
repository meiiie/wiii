import { describe, expect, it, vi } from "vitest";
import {
  findCompleteMarkdownBlockBoundary,
  SemanticStreamBuffer,
} from "@/lib/semantic-stream-buffer";

describe("SemanticStreamBuffer complete-block presentation", () => {
  it("does not expose partial paragraph tokens", () => {
    const onFlush = vi.fn();
    const buffer = new SemanticStreamBuffer({ onFlush });

    buffer.push("Wiii đang ");
    buffer.push("chuẩn bị câu trả lời hoàn chỉnh.");

    expect(onFlush).not.toHaveBeenCalled();
    expect(buffer.pending).toBeGreaterThan(0);
  });

  it("commits a paragraph only when its blank-line boundary arrives", () => {
    const flushes: string[] = [];
    const buffer = new SemanticStreamBuffer({ onFlush: (text) => flushes.push(text) });

    buffer.push("Đây là một paragraph hoàn chỉnh.");
    expect(flushes).toEqual([]);

    buffer.push("\n\n");
    expect(flushes).toEqual(["Đây là một paragraph hoàn chỉnh.\n\n"]);
    expect(buffer.pending).toBe(0);
  });

  it("commits multiple complete paragraphs as separate presentation updates", () => {
    const flushes: string[] = [];
    const buffer = new SemanticStreamBuffer({ onFlush: (text) => flushes.push(text) });

    buffer.push("Đoạn một.\n\nĐoạn hai.\n\nĐoạn ba đang viết");

    expect(flushes).toEqual(["Đoạn một.\n\n", "Đoạn hai.\n\n"]);
    expect(buffer.pending).toBe("Đoạn ba đang viết".length);
  });

  it("commits an ATX heading when its line completes", () => {
    const onFlush = vi.fn();
    const buffer = new SemanticStreamBuffer({ onFlush });

    buffer.push("## Kết quả");
    expect(onFlush).not.toHaveBeenCalled();
    buffer.push("\n");

    expect(onFlush).toHaveBeenCalledWith("## Kết quả\n");
  });

  it("keeps a whole Markdown list together", () => {
    const flushes: string[] = [];
    const buffer = new SemanticStreamBuffer({ onFlush: (text) => flushes.push(text) });

    buffer.push("- Mục một\n");
    buffer.push("- Mục hai\n");
    expect(flushes).toEqual([]);

    buffer.push("\n");
    expect(flushes).toEqual(["- Mục một\n- Mục hai\n\n"]);
  });

  it("waits for the closing fence before committing code", () => {
    const flushes: string[] = [];
    const buffer = new SemanticStreamBuffer({ onFlush: (text) => flushes.push(text) });

    buffer.push("```ts\n");
    buffer.push("const value = 1;\n");
    expect(flushes).toEqual([]);

    buffer.push("```\n");
    expect(flushes).toEqual(["```ts\nconst value = 1;\n```\n"]);
  });

  it("keeps a complete Markdown table together", () => {
    const flushes: string[] = [];
    const buffer = new SemanticStreamBuffer({ onFlush: (text) => flushes.push(text) });

    buffer.push("| Agent | State |\n");
    buffer.push("| --- | --- |\n");
    buffer.push("| Codex | Running |\n");
    expect(flushes).toEqual([]);

    buffer.push("\n");
    expect(flushes).toEqual([
      "| Agent | State |\n| --- | --- |\n| Codex | Running |\n\n",
    ]);
  });

  it("recognizes Setext headings without treating ordinary wrapped prose as complete", () => {
    expect(findCompleteMarkdownBlockBoundary("Architecture\n===\n")).toBe(
      "Architecture\n===\n".length,
    );
    expect(findCompleteMarkdownBlockBoundary("ordinary wrapped\nprose")).toBe(0);
  });

  it("finalizes an unfinished block at a tool or lifecycle boundary", () => {
    const onFlush = vi.fn();
    const buffer = new SemanticStreamBuffer({ onFlush });

    buffer.push("Phần trả lời cuối không có blank line");
    buffer.drain();

    expect(onFlush).toHaveBeenCalledWith("Phần trả lời cuối không có blank line");
    expect(buffer.pending).toBe(0);
    expect(buffer.running).toBe(false);
  });

  it("discards presentation-only text without emitting it", () => {
    const onFlush = vi.fn();
    const buffer = new SemanticStreamBuffer({ onFlush });

    buffer.push("Không được hiển thị");
    buffer.discard();

    expect(onFlush).not.toHaveBeenCalled();
    expect(buffer.pending).toBe(0);
  });
});
