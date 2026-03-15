/**
 * Sprint 150: StreamBuffer — rAF-based token smoothing tests.
 *
 * Tests:
 * 1.  Construction defaults — pending=0, running=false
 * 2.  push accumulates — multiple pushes concatenate
 * 3.  push starts rAF loop — running=true after first push
 * 4.  push ignores empty — no loop start on empty string
 * 5.  rAF flushes chars — onFlush called per frame
 * 6.  All content emitted — multiple frames drain completely
 * 7.  Loop self-pauses — stops when buffer empty
 * 8.  Loop restarts — push after pause restarts loop
 * 9.  Adaptive: min chars — small buffer → minCharsPerFrame
 * 10. Adaptive: max chars — large buffer → maxCharsPerFrame
 * 11. Adaptive: proportional — medium buffer → proportional
 * 12. drain flushes all — immediate, synchronous flush
 * 13. drain no-op empty — no callback on empty buffer
 * 14. drain stops loop — running=false after drain
 * 15. drain partial — drains remaining after some frames
 * 16. discard throws away — no callback, buffer cleared
 * 17. discard stops loop — running=false
 * 18. setOnFlush replaces — new callback receives buffered text
 * 19. Markdown boundary — doesn't split ** markers
 * 20. Concurrent push during flush — push inside onFlush callback works
 * 21. Rapid push-drain — multiple pushes then drain = 1 flush
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { StreamBuffer } from "@/lib/stream-buffer";

// ── Mock rAF + performance.now ──────────────────────────────────────────

let rafCallbacks: Array<(timestamp: number) => void> = [];
let rafIdCounter = 1;
let mockNow = 0;

function mockRaf(cb: (timestamp: number) => void): number {
  const id = rafIdCounter++;
  rafCallbacks.push(cb);
  return id;
}

function mockCancelRaf(_id: number): void {
  // In real usage cancelAnimationFrame removes the callback,
  // but for tests we just clear the queue on discard/drain.
}

/** Advance one rAF frame: runs all pending callbacks then clears them. */
function tickFrame(advanceMs = 17): void {
  mockNow += advanceMs;
  const cbs = [...rafCallbacks];
  rafCallbacks = [];
  for (const cb of cbs) {
    cb(mockNow);
  }
}

/** Advance N frames. */
function tickFrames(n: number, advanceMs = 17): void {
  for (let i = 0; i < n; i++) {
    tickFrame(advanceMs);
  }
}

beforeEach(() => {
  rafCallbacks = [];
  rafIdCounter = 1;
  mockNow = 0;
  vi.stubGlobal("requestAnimationFrame", mockRaf);
  vi.stubGlobal("cancelAnimationFrame", mockCancelRaf);
  vi.stubGlobal("performance", { now: () => mockNow });
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── Tests ───────────────────────────────────────────────────────────────

describe("StreamBuffer", () => {
  // 1. Construction defaults
  it("has pending=0 and running=false on construction", () => {
    const buf = new StreamBuffer({ onFlush: vi.fn(), initialHoldMs: 0 });
    expect(buf.pending).toBe(0);
    expect(buf.running).toBe(false);
  });

  // 2. push accumulates
  it("accumulates multiple pushes into the buffer", () => {
    const buf = new StreamBuffer({ onFlush: vi.fn(), initialHoldMs: 0 });
    buf.push("Hello");
    buf.push(" ");
    buf.push("World");
    expect(buf.pending).toBe(11);
  });

  // 3. push starts rAF loop
  it("starts rAF loop after first push", () => {
    const buf = new StreamBuffer({ onFlush: vi.fn(), initialHoldMs: 0 });
    expect(buf.running).toBe(false);
    buf.push("x");
    expect(buf.running).toBe(true);
  });

  // 4. push ignores empty
  it("ignores empty string push — no loop start", () => {
    const buf = new StreamBuffer({ onFlush: vi.fn(), initialHoldMs: 0 });
    buf.push("");
    expect(buf.running).toBe(false);
    expect(buf.pending).toBe(0);
  });

  // 5. rAF flushes chars
  it("calls onFlush each frame with extracted chars", () => {
    const onFlush = vi.fn();
    const buf = new StreamBuffer({
      onFlush,
      minCharsPerFrame: 2,
      maxCharsPerFrame: 5,
      targetFrames: 4,
      minFlushInterval: 0, initialHoldMs: 0,
    });
    buf.push("abcdefgh"); // 8 chars
    tickFrame(); // Should flush some chars
    expect(onFlush).toHaveBeenCalled();
    expect(onFlush.mock.calls[0][0].length).toBeGreaterThan(0);
  });

  // 6. All content emitted
  it("emits all content across multiple frames", () => {
    const chunks: string[] = [];
    const buf = new StreamBuffer({
      onFlush: (c) => chunks.push(c),
      minCharsPerFrame: 1,
      maxCharsPerFrame: 3,
      targetFrames: 4,
      minFlushInterval: 0, initialHoldMs: 0,
    });
    buf.push("Hello World!"); // 12 chars
    // Tick enough frames to drain everything
    tickFrames(20);
    const result = chunks.join("");
    expect(result).toBe("Hello World!");
  });

  // 7. Loop self-pauses when empty
  it("self-pauses when buffer is drained by rAF", () => {
    const buf = new StreamBuffer({
      onFlush: vi.fn(),
      minCharsPerFrame: 100, // Will drain in 1 frame
      maxCharsPerFrame: 100,
      minFlushInterval: 0, initialHoldMs: 0,
    });
    buf.push("short");
    expect(buf.running).toBe(true);
    tickFrame();
    expect(buf.running).toBe(false);
    expect(buf.pending).toBe(0);
  });

  // 8. Loop restarts after pause
  it("restarts loop when push is called after pause", () => {
    const buf = new StreamBuffer({
      onFlush: vi.fn(),
      minCharsPerFrame: 100,
      maxCharsPerFrame: 100,
      minFlushInterval: 0, initialHoldMs: 0,
    });
    buf.push("first");
    tickFrame(); // Drains, pauses
    expect(buf.running).toBe(false);
    buf.push("second");
    expect(buf.running).toBe(true);
  });

  // 9. Adaptive: min chars
  it("uses minCharsPerFrame for small buffers", () => {
    const chunks: string[] = [];
    const buf = new StreamBuffer({
      onFlush: (c) => chunks.push(c),
      minCharsPerFrame: 1,
      maxCharsPerFrame: 12,
      targetFrames: 8,
      minFlushInterval: 0, initialHoldMs: 0,
    });
    buf.push("ab"); // 2 chars, ceil(2/8)=1, clamped to min=1
    tickFrame();
    expect(chunks[0].length).toBe(1); // minCharsPerFrame
  });

  // 10. Adaptive: max chars (disable ease-in to test raw adaptive logic)
  it("caps at maxCharsPerFrame for large buffers", () => {
    const chunks: string[] = [];
    const buf = new StreamBuffer({
      onFlush: (c) => chunks.push(c),
      minCharsPerFrame: 1,
      maxCharsPerFrame: 5,
      targetBufferDepth: 40,
      minFlushInterval: 0, initialHoldMs: 0,
      easeInFrames: 0,
    });
    buf.push("a".repeat(200)); // bufferRatio=1 → max=5
    tickFrame();
    expect(chunks[0].length).toBe(5);
  });

  // 11. Adaptive: proportional (disable ease-in)
  it("uses proportional chars for medium buffers", () => {
    const chunks: string[] = [];
    const buf = new StreamBuffer({
      onFlush: (c) => chunks.push(c),
      minCharsPerFrame: 1,
      maxCharsPerFrame: 20,
      targetBufferDepth: 40,
      minFlushInterval: 0, initialHoldMs: 0,
      easeInFrames: 0,
    });
    buf.push("a".repeat(20)); // bufferRatio=0.5 → 1+(20-1)*0.5=10.5 → ~11
    tickFrame();
    expect(chunks[0].length).toBeGreaterThanOrEqual(5);
    expect(chunks[0].length).toBeLessThanOrEqual(15);
  });

  // 12. drain flushes all immediately
  it("drain() flushes all remaining content synchronously", () => {
    const chunks: string[] = [];
    const buf = new StreamBuffer({
      onFlush: (c) => chunks.push(c),
      minCharsPerFrame: 1,
      maxCharsPerFrame: 3,
      minFlushInterval: 0, initialHoldMs: 0,
    });
    buf.push("Hello World");
    buf.drain();
    expect(chunks.length).toBe(1);
    expect(chunks[0]).toBe("Hello World");
    expect(buf.pending).toBe(0);
  });

  // 13. drain no-op on empty
  it("drain() does nothing when buffer is empty", () => {
    const onFlush = vi.fn();
    const buf = new StreamBuffer({ onFlush, initialHoldMs: 0 });
    buf.drain();
    expect(onFlush).not.toHaveBeenCalled();
  });

  // 14. drain stops loop
  it("drain() stops the rAF loop", () => {
    const buf = new StreamBuffer({
      onFlush: vi.fn(),
      minCharsPerFrame: 1,
      maxCharsPerFrame: 2,
      minFlushInterval: 0, initialHoldMs: 0,
    });
    buf.push("abcdefghij");
    expect(buf.running).toBe(true);
    buf.drain();
    expect(buf.running).toBe(false);
  });

  // 15. drain after partial flush
  it("drain() flushes remaining content after partial rAF flush", () => {
    const chunks: string[] = [];
    const buf = new StreamBuffer({
      onFlush: (c) => chunks.push(c),
      minCharsPerFrame: 2,
      maxCharsPerFrame: 3,
      targetFrames: 4,
      minFlushInterval: 0, initialHoldMs: 0,
    });
    buf.push("Hello World!"); // 12 chars
    tickFrame(); // Flush ~3 chars
    const partialLen = chunks.join("").length;
    expect(partialLen).toBeGreaterThan(0);
    expect(partialLen).toBeLessThan(12);
    buf.drain(); // Flush rest
    expect(chunks.join("")).toBe("Hello World!");
    expect(buf.pending).toBe(0);
  });

  // 16. discard throws away content
  it("discard() clears buffer without calling onFlush", () => {
    const onFlush = vi.fn();
    const buf = new StreamBuffer({ onFlush, initialHoldMs: 0 });
    buf.push("secret data");
    buf.discard();
    expect(onFlush).not.toHaveBeenCalled();
    expect(buf.pending).toBe(0);
  });

  // 17. discard stops loop
  it("discard() stops the rAF loop", () => {
    const buf = new StreamBuffer({ onFlush: vi.fn(), initialHoldMs: 0 });
    buf.push("data");
    expect(buf.running).toBe(true);
    buf.discard();
    expect(buf.running).toBe(false);
  });

  // 18. setOnFlush replaces callback
  it("setOnFlush() replaces the flush callback", () => {
    const first = vi.fn();
    const second = vi.fn();
    const buf = new StreamBuffer({
      onFlush: first,
      minCharsPerFrame: 100,
      maxCharsPerFrame: 100,
      minFlushInterval: 0, initialHoldMs: 0,
    });
    buf.push("initial");
    buf.setOnFlush(second);
    tickFrame();
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledWith("initial");
  });

  // 19. Markdown boundary awareness — doesn't split **
  it("doesn't split ** markdown markers", () => {
    const chunks: string[] = [];
    const buf = new StreamBuffer({
      onFlush: (c) => chunks.push(c),
      minCharsPerFrame: 3,
      maxCharsPerFrame: 3,
      targetFrames: 1,
      minFlushInterval: 0, initialHoldMs: 0,
    });
    // "ab**cd" — if we extract 3, we'd land between the two *.
    // The buffer should extend to include both **.
    buf.push("ab**cd");
    tickFrame();
    // Should extract "ab**" (4 chars) to avoid splitting **
    expect(chunks[0]).toBe("ab**");
  });

  // 20. Concurrent push during flush
  it("handles push inside onFlush callback", () => {
    let pushCount = 0;
    const chunks: string[] = [];
    const buf = new StreamBuffer({
      onFlush: (c) => {
        chunks.push(c);
        // Push more data during first flush
        if (pushCount === 0) {
          pushCount++;
          buf.push(" extra");
        }
      },
      minCharsPerFrame: 100,
      maxCharsPerFrame: 100,
      minFlushInterval: 0, initialHoldMs: 0,
      initialHoldMs: 0,
    });
    buf.push("initial");
    tickFrame(); // Flushes "initial", callback pushes " extra"
    tickFrame(); // Flushes " extra"
    expect(chunks.join("")).toBe("initial extra");
  });

  // 21. Rapid push-drain
  it("multiple pushes then drain produces single flush", () => {
    const chunks: string[] = [];
    const buf = new StreamBuffer({
      onFlush: (c) => chunks.push(c),
    });
    buf.push("a");
    buf.push("b");
    buf.push("c");
    buf.drain();
    expect(chunks.length).toBe(1);
    expect(chunks[0]).toBe("abc");
  });
});
