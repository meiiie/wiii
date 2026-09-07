import { describe, expect, it, vi } from "vitest";
import {
  findCompleteMarkdownBlockBoundary,
  SemanticStreamBuffer,
} from "@/lib/semantic-stream-buffer";

describe("SemanticStreamBuffer complete-block presentation", () => {
  it("does not treat a partial Setext underline or closing fence as complete", () => {
    const onFlush = vi.fn();
    const buffer = new SemanticStreamBuffer({ onFlush });
    buffer.push("Title\n-");
    expect(onFlush).not.toHaveBeenCalled();
    buffer.push(" item\n\n");
    expect(onFlush).toHaveBeenCalledExactlyOnceWith("Title\n- item\n\n");
    onFlush.mockClear();
    buffer.push("```js\ncode\n```");
    expect(onFlush).not.toHaveBeenCalled();
    buffer.push("not a closing fence\n```\n");
    expect(onFlush).toHaveBeenCalledExactlyOnceWith("```js\ncode\n```not a closing fence\n```\n");
  });

  it("keeps block boundaries identical across arbitrary delta splits", () => {
    const text = "\r\n# Heading\r\nTitle\n===\n\n- first\n- second\n\n```ts\n\nvalue\n```\ntrailing";
    const expected: string[] = [];
    const whole = new SemanticStreamBuffer({ onFlush: (part) => expected.push(part) });
    whole.push(text);
    whole.drain();
    for (let split = 0; split <= text.length; split += 1) {
      const parts: string[] = [];
      const buffer = new SemanticStreamBuffer({ onFlush: (part) => parts.push(part) });
      buffer.push(text.slice(0, split));
      buffer.push(text.slice(split));
      buffer.drain();
      expect(parts).toEqual(expected);
      expect(parts.join("")).toBe(text);
    }
  });

  it("scans only incoming text while a long paragraph remains unfinished", () => {
    const original = String.prototype.indexOf;
    let scanned = 0;
    const scan = vi.spyOn(String.prototype, "indexOf").mockImplementation(function (this: string, search, position = 0) {
      if (search === "\n") scanned += this.length - position;
      return original.call(this, search, position);
    });
    const flushes: string[] = [];
    const buffer = new SemanticStreamBuffer({ onFlush: (part) => flushes.push(part) });
    try {
      for (let i = 0; i < 1000; i += 1) buffer.push("x".repeat(1000));
    } finally {
      scan.mockRestore();
    }
    expect(scanned).toBe(1_000_000);
    expect(flushes).toEqual([]);
    buffer.push("\n\n");
    expect(flushes).toEqual(["x".repeat(1_000_000) + "\n\n"]);
  });

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
