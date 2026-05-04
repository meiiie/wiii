"""Punctuation-aware token batching for the SSE answer stream.

Phase 33a of the runtime migration epic (issue #207). Phase 32d cleared
status-event noise from the live timer; this module attacks the
answer-event cadence problem.

Today's stream emits each provider chunk as one ``answer_delta`` SSE
event. Some providers burst 30-50 tokens into one chunk, others trickle
single tokens. The UI repaints the message bubble on every chunk, so a
bursty provider creates the same jerky feeling as the status spam did
before Phase 32d.

The fix is a simple **boundary-aware buffer**:

- Accumulate tokens until we see a "natural" boundary (sentence-ending
  punctuation, paragraph break, comma after >= K chars, or a length
  threshold).
- Flush on boundary OR after a short time-since-last-flush watchdog so
  long-running tokens don't stall the UI.

This matches what Anthropic, OpenAI, and DeepSeek do in their first-
party UIs — token cadence at the UI layer is normalized, NOT the raw
provider stream.

Out of scope:
- Cross-language smarter tokenization (the Vietnamese flush rules
  here just look at ASCII punctuation, which is enough — VN text uses
  the same . , ! ? boundaries).
- Streaming TTFT optimization (Phase 33b).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

# Sentence-ending punctuation that always flushes.
_HARD_FLUSH_CHARS = frozenset(".!?\n")
# Soft boundaries — flush only if we've already buffered MIN_SOFT_FLUSH_CHARS.
_SOFT_FLUSH_CHARS = frozenset(",;:")
# Floor / ceiling for the buffer. Below FLOOR we never flush on a soft
# boundary (avoids stuttering on "I, " openings). Above CEILING we
# force-flush regardless of punctuation (stops a mid-paragraph token
# burst from stalling the UI for >100ms).
MIN_SOFT_FLUSH_CHARS = 18
MAX_BUFFER_CHARS = 60
# Time-since-last-flush watchdog. If the LLM stalls mid-sentence, flush
# whatever we have so the UI keeps moving.
MAX_FLUSH_INTERVAL_MS = 200


@dataclass
class StreamSmoother:
    """Boundary-aware accumulator that turns raw provider chunks into a
    cadence the UI can repaint smoothly.

    The pattern is deliberately stateful — Python instance state — so a
    caller can drive it from inside the existing async generator without
    plumbing channels around. Call ``feed()`` for each provider chunk;
    it returns 0+ flushed strings to yield as ``answer_delta`` events.
    Call ``flush_remaining()`` once at end-of-stream so the tail token
    doesn't get dropped.
    """

    buffer: str = ""
    last_flush_at_ms: float = 0.0

    def _now_ms(self) -> float:
        return time.monotonic() * 1000.0

    def feed(self, chunk: str) -> list[str]:
        """Accept a provider chunk. Return the strings to flush right now.

        Multiple flushes per chunk are possible — e.g. if the provider
        bursts ``"Hello. World!"`` in one shot, we emit two flushes
        ``"Hello. "`` and ``"World!"`` so the UI sees two clean
        sentence-ending repaints.
        """
        if not chunk:
            return []
        now_ms = self._now_ms()
        if self.last_flush_at_ms == 0.0:
            self.last_flush_at_ms = now_ms

        flushes: list[str] = []
        for ch in chunk:
            self.buffer += ch
            if self._should_flush_after_char(ch):
                flushes.append(self.buffer)
                self.buffer = ""
                self.last_flush_at_ms = now_ms

        # Watchdog: if we have unflushed bytes AND the last flush was >
        # MAX_FLUSH_INTERVAL_MS ago, ship what we have so the UI keeps
        # moving even when the provider stalls mid-sentence.
        if (
            self.buffer
            and now_ms - self.last_flush_at_ms >= MAX_FLUSH_INTERVAL_MS
        ):
            flushes.append(self.buffer)
            self.buffer = ""
            self.last_flush_at_ms = now_ms

        return flushes

    def _should_flush_after_char(self, ch: str) -> bool:
        if ch in _HARD_FLUSH_CHARS:
            return True
        if len(self.buffer) >= MAX_BUFFER_CHARS:
            return True
        if (
            ch in _SOFT_FLUSH_CHARS
            and len(self.buffer) >= MIN_SOFT_FLUSH_CHARS
        ):
            return True
        return False

    def flush_remaining(self) -> str:
        """Drain whatever is left in the buffer at end-of-stream.

        Call once when the inner generator finishes so the tail token
        ("ạ", "!", or a final "...") doesn't get silently dropped.
        Returns "" when the buffer is already empty.
        """
        if not self.buffer:
            return ""
        out = self.buffer
        self.buffer = ""
        self.last_flush_at_ms = self._now_ms()
        return out


__all__ = ["StreamSmoother"]
