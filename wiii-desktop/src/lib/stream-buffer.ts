/**
 * Sprint V5: StreamBuffer — Claude-quality token smoothing engine.
 *
 * 5 layers processing each frame:
 *   1. Adaptive Pacing — chars/frame scales with buffer depth
 *   2. Ease-in — cubic smoothstep ramp over first N frames
 *   3. Word Boundary Snap — flush at space/punctuation, never mid-word
 *   4. Markdown Guard — don't break inside **, ```, [], ()
 *   5. Drain Mode — accelerated flush when stream ends
 *
 * Flow:  SSE event → buffer.push(chunk)
 *                          ↓
 *                  initial hold (~80ms)
 *                          ↓
 *                  rAF loop (~60fps)
 *                          ↓
 *                  adaptive flush → onFlush()
 *
 * Based on StreamBufferV2 architecture from Claude AI analysis.
 */

export interface StreamBufferOptions {
  /** Called each rAF frame with the chars to render */
  onFlush: (chars: string) => void;
  /** ms to wait before first flush (default: 80 — accumulate initial tokens) */
  initialHoldMs?: number;
  /** Minimum chars to flush per frame (default: 3 — prevents stalling) */
  minCharsPerFrame?: number;
  /** Maximum chars to flush per frame (default: 28 — prevents massive bursts) */
  maxCharsPerFrame?: number;
  /** Buffer depth at which we flush at max rate (default: 40) */
  targetBufferDepth?: number;
  /** Number of frames for cubic ease-in ramp (default: 15) */
  easeInFrames?: number;
  /** @deprecated Use targetBufferDepth. Kept for backward compat. */
  targetFrames?: number;
  /** @deprecated V2 uses rAF pacing only. Kept for backward compat (ignored). */
  minFlushInterval?: number;
}

// Markdown tokens that should not be split mid-sequence
const MD_PAIRS = ["```", "**", "__", "~~", "``", "`"];

export class StreamBuffer {
  private _buffer = "";
  private _rafId: number | null = null;
  private _onFlush: (chars: string) => void;
  private _minChars: number;
  private _maxChars: number;
  private _targetBufferDepth: number;
  private _initialHoldMs: number;
  private _easeInFrames: number;
  private _holdTimer: ReturnType<typeof setTimeout> | null = null;
  private _started = false;
  private _running = false;
  private _frameCount = 0;
  private _streamEnded = false;
  // SOTA 2026: Intl.Segmenter for Vietnamese word boundary detection
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private _segmenter = typeof Intl !== "undefined" && (Intl as any).Segmenter
    ? new (Intl as any).Segmenter("vi", { granularity: "word" })
    : null;

  constructor(opts: StreamBufferOptions) {
    this._onFlush = opts.onFlush;
    this._minChars = opts.minCharsPerFrame ?? 3;
    this._maxChars = opts.maxCharsPerFrame ?? 28;
    this._targetBufferDepth = opts.targetBufferDepth ?? 40;
    this._initialHoldMs = opts.initialHoldMs ?? 80;
    this._easeInFrames = opts.easeInFrames ?? 15;
  }

  /** Number of characters waiting in the buffer */
  get pending(): number {
    return this._buffer.length;
  }

  /** Whether the rAF loop is currently active */
  get running(): boolean {
    return this._running;
  }

  /** Replace the flush callback (e.g. when switching streams) */
  setOnFlush(fn: (chars: string) => void): void {
    this._onFlush = fn;
  }

  /** Add tokens to the buffer. Auto-starts after initial hold. */
  push(chunk: string): void {
    if (!chunk) return;
    this._buffer += chunk;

    if (!this._started && !this._holdTimer) {
      if (this._initialHoldMs <= 0) {
        // No hold — start immediately (useful for testing)
        this._started = true;
        if (!this._running) this._startLoop();
      } else {
        // First token — start initial hold timer
        this._holdTimer = setTimeout(() => {
          this._started = true;
          this._holdTimer = null;
          if (!this._running) this._startLoop();
        }, this._initialHoldMs);
      }
    } else if (this._started && !this._running) {
      this._startLoop();
    }
  }

  /** Signal stream ended. Triggers accelerated drain. */
  end(): void {
    this._streamEnded = true;
    if (!this._started) {
      // Still in hold — flush immediately
      if (this._holdTimer) {
        clearTimeout(this._holdTimer);
        this._holdTimer = null;
      }
      this._started = true;
      if (!this._running) this._startLoop();
    }
  }

  /** Flush ALL remaining chars synchronously. Use before block boundaries. */
  drain(): void {
    this._stopLoop();
    if (this._holdTimer) {
      clearTimeout(this._holdTimer);
      this._holdTimer = null;
    }
    this._started = true;
    if (this._buffer.length > 0) {
      const out = this._buffer;
      this._buffer = "";
      this._onFlush(out);
    }
  }

  /** Discard all buffered content without emitting. Use on cancel/error. */
  discard(): void {
    this._stopLoop();
    if (this._holdTimer) {
      clearTimeout(this._holdTimer);
      this._holdTimer = null;
    }
    this._buffer = "";
    this._started = false;
    this._running = false;
    this._frameCount = 0;
    this._streamEnded = false;
  }

  // -- Internal -----------------------------------------------------------

  private _startLoop(): void {
    this._running = true;
    this._rafId = requestAnimationFrame(this._tick);
  }

  private _stopLoop(): void {
    if (this._rafId !== null) {
      cancelAnimationFrame(this._rafId);
      this._rafId = null;
    }
    this._running = false;
  }

  private _tick = (): void => {
    if (this._buffer.length === 0) {
      this._running = false;
      this._rafId = null;
      return;
    }

    this._frameCount++;

    // Layer 1: Adaptive pacing — scale chars/frame with buffer depth
    const bufferRatio = Math.min(1, this._buffer.length / this._targetBufferDepth);
    let targetChars = this._minChars + (this._maxChars - this._minChars) * bufferRatio;

    // Layer 2: Ease-in — cubic smoothstep t²(3-2t) over first N frames
    if (this._frameCount <= this._easeInFrames) {
      const t = this._frameCount / this._easeInFrames;
      const eased = t * t * (3 - 2 * t); // smoothstep
      targetChars = Math.max(this._minChars, targetChars * eased);
    }

    // Layer 5: Drain mode — stream ended, accelerate to finish
    if (this._streamEnded && this._buffer.length < this._targetBufferDepth) {
      targetChars = Math.max(targetChars, Math.ceil(this._buffer.length * 0.25));
    }

    let count = Math.round(targetChars);
    count = Math.max(1, Math.min(count, this._buffer.length));

    // Layer 3: Word boundary snap
    count = this._snapToWordBoundary(count);

    // Layer 4: Markdown guard
    count = this._avoidMarkdownBreak(count);

    // Safety
    count = Math.max(1, Math.min(count, this._buffer.length));

    const extracted = this._buffer.slice(0, count);
    this._buffer = this._buffer.slice(count);
    this._onFlush(extracted);

    // Continue loop if more content remains
    if (this._buffer.length > 0) {
      this._rafId = requestAnimationFrame(this._tick);
    } else {
      this._running = false;
      this._rafId = null;
    }
  };

  /**
   * Snap flush count to nearest word boundary.
   * SOTA 2026: Uses Intl.Segmenter("vi") for Vietnamese/CJK-aware word breaks.
   * Falls back to ASCII punctuation scan when Segmenter unavailable.
   *
   * Both branches cap overshoot at SNAP_RANGE chars past count. A "word"
   * whose end sits beyond that range (e.g. a long URL or repeated-char
   * buffer) is NOT allowed to override adaptive pacing — otherwise
   * pathological streams would burst-flush the entire buffer in one frame.
   */
  private _snapToWordBoundary(count: number): number {
    if (count >= this._buffer.length) return count;

    const SNAP_RANGE = 6;

    // Try Intl.Segmenter first — handles Vietnamese diacritics correctly
    if (this._segmenter) {
      const searchLimit = Math.min(this._buffer.length, count + SNAP_RANGE);
      const slice = this._buffer.slice(0, searchLimit);
      const segments = this._segmenter.segment(slice);
      let pos = 0;
      for (const seg of segments) {
        pos += seg.segment.length;
        if (pos >= count) {
          // Only snap if within SNAP_RANGE. A segment that ends exactly
          // at slice-edge likely reflects the slice truncation, not a
          // real word boundary, so require strict less-than.
          if (pos - count < SNAP_RANGE) {
            return Math.min(pos, this._buffer.length);
          }
          break;
        }
      }
      return count;
    }

    // Fallback: ASCII punctuation scan ±SNAP_RANGE chars
    const SEARCH_RANGE = SNAP_RANGE;
    const searchStart = Math.max(1, count - SEARCH_RANGE);
    const searchEnd = Math.min(this._buffer.length, count + SEARCH_RANGE);

    let bestPos = count;
    let bestDist = SEARCH_RANGE + 1;

    for (let i = searchStart; i <= searchEnd; i++) {
      const ch = this._buffer[i];
      if (ch === " " || ch === "\n" || ch === "\t" ||
          ch === "," || ch === "." || ch === "!" || ch === "?" ||
          ch === ";" || ch === ":" || ch === ")" || ch === "]") {
        const dist = Math.abs(i - count);
        // Bias: prefer positions at/after target (flush more, not less)
        const adjustedDist = i >= count ? dist : dist + 1;
        if (adjustedDist < bestDist) {
          bestDist = adjustedDist;
          bestPos = i + 1; // include boundary character
        }
      }
    }

    return Math.max(1, bestPos);
  }

  /**
   * Avoid breaking inside markdown tokens: **, ```, __, ~~
   */
  private _avoidMarkdownBreak(count: number): number {
    if (count >= this._buffer.length) return count;

    for (const token of MD_PAIRS) {
      const tLen = token.length;
      const windowStart = Math.max(0, count - tLen + 1);
      const windowEnd = Math.min(this._buffer.length, count + tLen - 1);
      const window = this._buffer.slice(windowStart, windowEnd);
      const tokenPos = window.indexOf(token);
      if (tokenPos !== -1) {
        const absoluteStart = windowStart + tokenPos;
        const absoluteEnd = absoluteStart + tLen;
        if (absoluteStart < count && count < absoluteEnd) {
          return Math.min(absoluteEnd, this._buffer.length);
        }
      }
    }

    return count;
  }
}
