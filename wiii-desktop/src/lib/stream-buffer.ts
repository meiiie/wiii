/**
 * Sprint 150: StreamBuffer — rAF-based token smoothing.
 *
 * Sits between SSE event handlers and Zustand store to buffer incoming
 * tokens and flush them at ~60fps via requestAnimationFrame, producing
 * smooth, consistent text rendering instead of bursty TCP-paced updates.
 *
 * Flow:  SSE event → buffer.push(chunk)  [no re-render]
 *                          ↓
 *                  rAF loop (~60fps)
 *                          ↓
 *                  buffer.flush(N chars) → onFlush()  [1 re-render/frame]
 */

export interface StreamBufferOptions {
  /** Called each rAF frame with the chars to render */
  onFlush: (chars: string) => void;
  /** Minimum chars to emit per frame (default: 1) */
  minCharsPerFrame?: number;
  /** Maximum chars to emit per frame (default: 12) */
  maxCharsPerFrame?: number;
  /** Target frames to drain the current buffer (default: 8 ≈ 133ms at 60fps) */
  targetFrames?: number;
  /** Minimum interval between flushes in ms (default: 16 ≈ 60fps cap) */
  minFlushInterval?: number;
}

// Markdown tokens that should not be split mid-sequence
const MD_PAIRS = ["```", "**", "__", "~~", "``", "`"];

export class StreamBuffer {
  private _buffer = "";
  private _rafId: number | null = null;
  private _lastFlushTime = 0;
  private _onFlush: (chars: string) => void;
  private _minChars: number;
  private _maxChars: number;
  private _targetFrames: number;
  private _minFlushInterval: number;

  constructor(opts: StreamBufferOptions) {
    this._onFlush = opts.onFlush;
    this._minChars = opts.minCharsPerFrame ?? 1;
    this._maxChars = opts.maxCharsPerFrame ?? 12;
    this._targetFrames = opts.targetFrames ?? 8;
    this._minFlushInterval = opts.minFlushInterval ?? 16;
  }

  /** Number of characters waiting in the buffer */
  get pending(): number {
    return this._buffer.length;
  }

  /** Whether the rAF loop is currently active */
  get running(): boolean {
    return this._rafId !== null;
  }

  /** Replace the flush callback (e.g. when switching streams) */
  setOnFlush(fn: (chars: string) => void): void {
    this._onFlush = fn;
  }

  /** Add tokens to the buffer. Auto-starts the rAF loop if idle. */
  push(chunk: string): void {
    if (!chunk) return;
    this._buffer += chunk;
    if (!this._rafId) {
      this._startLoop();
    }
  }

  /** Flush ALL remaining chars synchronously. Use before block boundaries. */
  drain(): void {
    this._stopLoop();
    if (this._buffer.length > 0) {
      const out = this._buffer;
      this._buffer = "";
      this._onFlush(out);
    }
  }

  /** Discard all buffered content without emitting. Use on cancel/error. */
  discard(): void {
    this._stopLoop();
    this._buffer = "";
  }

  // -- Internal -----------------------------------------------------------

  private _startLoop(): void {
    this._rafId = requestAnimationFrame(this._tick);
  }

  private _stopLoop(): void {
    if (this._rafId !== null) {
      cancelAnimationFrame(this._rafId);
      this._rafId = null;
    }
  }

  private _tick = (_timestamp?: number): void => {
    // Respect min flush interval
    const now = performance.now();
    if (now - this._lastFlushTime < this._minFlushInterval) {
      // Too soon — schedule next frame
      this._rafId = requestAnimationFrame(this._tick);
      return;
    }

    if (this._buffer.length === 0) {
      // Nothing left — self-pause
      this._rafId = null;
      return;
    }

    // Adaptive: chars = clamp(bufferLen / targetFrames, min, max)
    const raw = Math.ceil(this._buffer.length / this._targetFrames);
    const count = Math.max(this._minChars, Math.min(this._maxChars, raw));

    const extracted = this._extractChars(count);
    this._lastFlushTime = now;
    this._onFlush(extracted);

    // Continue loop if more content remains
    if (this._buffer.length > 0) {
      this._rafId = requestAnimationFrame(this._tick);
    } else {
      this._rafId = null;
    }
  };

  /**
   * Extract `count` chars from the front of the buffer, avoiding splits
   * in the middle of markdown tokens (**, ```, __, ~~, \n).
   */
  private _extractChars(count: number): string {
    if (count >= this._buffer.length) {
      const out = this._buffer;
      this._buffer = "";
      return out;
    }

    // Prefer splitting at a newline if one is within ±3 chars of the cut point
    const searchStart = Math.max(0, count - 3);
    const searchEnd = Math.min(this._buffer.length, count + 3);
    const nearSlice = this._buffer.slice(searchStart, searchEnd);
    const nlIdx = nearSlice.indexOf("\n");
    if (nlIdx !== -1) {
      const splitAt = searchStart + nlIdx + 1; // include the newline
      const out = this._buffer.slice(0, splitAt);
      this._buffer = this._buffer.slice(splitAt);
      return out;
    }

    // Check if we'd split a markdown token
    for (const token of MD_PAIRS) {
      const tLen = token.length;
      // Check if the cut point (count) lands inside a token occurrence
      // Look at a window around the cut point
      const windowStart = Math.max(0, count - tLen + 1);
      const windowEnd = Math.min(this._buffer.length, count + tLen - 1);
      const window = this._buffer.slice(windowStart, windowEnd);
      const tokenPos = window.indexOf(token);
      if (tokenPos !== -1) {
        const absoluteStart = windowStart + tokenPos;
        const absoluteEnd = absoluteStart + tLen;
        // If cut point is inside this token, extend to include it
        if (absoluteStart < count && count < absoluteEnd) {
          const out = this._buffer.slice(0, absoluteEnd);
          this._buffer = this._buffer.slice(absoluteEnd);
          return out;
        }
      }
    }

    // No markdown boundary conflict — split at count
    const out = this._buffer.slice(0, count);
    this._buffer = this._buffer.slice(count);
    return out;
  }
}
