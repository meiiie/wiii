"""Phase 33a stream smoother — Runtime Migration #207.

Locks the boundary-aware flushing contract:
- Hard flush on .!?\\n
- Soft flush on ,;: AFTER MIN_SOFT_FLUSH_CHARS chars buffered
- Force flush at MAX_BUFFER_CHARS
- Time watchdog after MAX_FLUSH_INTERVAL_MS
- flush_remaining drains the tail at end-of-stream
"""

from __future__ import annotations

import time

from app.engine.runtime.stream_smoother import (
    MAX_BUFFER_CHARS,
    MAX_FLUSH_INTERVAL_MS,
    MIN_SOFT_FLUSH_CHARS,
    StreamSmoother,
)


def test_empty_chunk_yields_nothing():
    s = StreamSmoother()
    assert s.feed("") == []


def test_period_triggers_hard_flush():
    s = StreamSmoother()
    out = s.feed("Hello world.")
    assert out == ["Hello world."]
    assert s.buffer == ""


def test_question_mark_triggers_hard_flush():
    s = StreamSmoother()
    out = s.feed("How are you?")
    assert out == ["How are you?"]


def test_newline_triggers_hard_flush():
    s = StreamSmoother()
    out = s.feed("First line\nSecond line.")
    assert out == ["First line\n", "Second line."]


def test_comma_alone_does_not_flush_under_min_chars():
    """A leading ", " in a short utterance must not flush — flushing
    "I," then " think" would produce stuttering UI repaints."""
    s = StreamSmoother()
    out = s.feed("I,")
    assert out == []
    # Buffered, not flushed.
    assert s.buffer == "I,"


def test_comma_flushes_after_min_chars():
    s = StreamSmoother()
    primer = "x" * MIN_SOFT_FLUSH_CHARS  # at threshold
    out = s.feed(primer + ",")
    assert out == [primer + ","]


def test_max_buffer_force_flushes_without_punctuation():
    s = StreamSmoother()
    long_run = "a" * (MAX_BUFFER_CHARS + 5)
    out = s.feed(long_run)
    # First flush at exactly MAX_BUFFER_CHARS, remainder buffered.
    assert len(out) == 1
    assert len(out[0]) == MAX_BUFFER_CHARS
    assert s.buffer == "a" * 5


def test_multiple_sentences_in_one_chunk_emit_separate_flushes():
    s = StreamSmoother()
    out = s.feed("Hello. World! Done?")
    assert out == ["Hello.", " World!", " Done?"]
    assert s.buffer == ""


def test_flush_remaining_drains_tail():
    s = StreamSmoother()
    s.feed("trailing text without punctuation")
    # Flush whatever is left.
    tail = s.flush_remaining()
    assert tail == "trailing text without punctuation"
    assert s.buffer == ""
    # Calling again is a no-op.
    assert s.flush_remaining() == ""


def test_watchdog_flushes_when_provider_stalls(monkeypatch):
    """If the buffer hasn't been flushed for MAX_FLUSH_INTERVAL_MS,
    feed() should flush even without a punctuation boundary."""
    s = StreamSmoother()
    # First chunk lays down some content but no flush boundary.
    out1 = s.feed("hello")
    assert out1 == []
    # Fast-forward time by manipulating monkeypatch on time.monotonic.
    real_monotonic = time.monotonic
    fake_now = real_monotonic() + (MAX_FLUSH_INTERVAL_MS + 50) / 1000.0
    monkeypatch.setattr(
        "app.engine.runtime.stream_smoother.time.monotonic",
        lambda: fake_now,
    )
    # Second chunk arrives long after — watchdog flushes the combined buffer.
    out2 = s.feed(" world")
    # The watchdog flushes everything accumulated so far.
    assert out2 == ["hello world"]


def test_vietnamese_punctuation_boundaries():
    """Sanity check VN content hits the same boundaries as English."""
    s = StreamSmoother()
    out = s.feed("Chào cậu! Có gì để học không? Mình giúp nha.")
    assert out == [
        "Chào cậu!",
        " Có gì để học không?",
        " Mình giúp nha.",
    ]


def test_streaming_chunk_by_chunk_simulates_provider_burst():
    """A realistic provider that emits 1-2 chars per chunk should
    accumulate into clean sentence-level flushes."""
    s = StreamSmoother()
    chunks = ["He", "ll", "o", " w", "or", "ld", "."]
    output: list[str] = []
    for c in chunks:
        output.extend(s.feed(c))
    output.append(s.flush_remaining())
    output = [o for o in output if o]
    assert output == ["Hello world."]


def test_streaming_long_paragraph_with_commas():
    """A multi-clause Vietnamese sentence should flush on the period,
    not on the early commas (because we're under MIN_SOFT_FLUSH_CHARS
    when the first comma arrives)."""
    s = StreamSmoother()
    # First chunk: "Bạn ơi," is 8 chars before the comma — under min.
    out = s.feed("Bạn ơi, ")
    assert out == []
    # Build past the soft threshold so the next comma flushes.
    # Total buffer "Bạn ơi, mình muốn nói rằng," — comma at end after >18 chars.
    out = s.feed("mình muốn nói rằng, hôm nay vui lắm.")
    # Expect a soft flush at "rằng," (>= 18 chars at boundary), then a
    # hard flush at "lắm." for the period.
    joined = "".join(out) + s.flush_remaining()
    assert "Bạn ơi, mình muốn nói rằng, hôm nay vui lắm." == joined
    # And expect at least 2 flush events (we don't pin the exact split,
    # only that boundary-driven flushing happened).
    assert len(out) >= 2
