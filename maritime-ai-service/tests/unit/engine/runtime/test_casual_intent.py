"""Phase 33b casual-intent classifier — Runtime Migration #207.

Locks the conservative-bias contract:
- Greetings, acknowledgments, address-only → high confidence.
- Questions, knowledge markers, tool intents → confidence 0 (blocked).
- Long messages (> 80 chars) → confidence 0.
- Empty / whitespace → confidence 0.
"""

from __future__ import annotations

import pytest

from app.engine.runtime.casual_intent import classify


# ── empty + whitespace ──

@pytest.mark.parametrize("msg", ["", "   ", "\n\t"])
def test_empty_or_whitespace_returns_zero(msg):
    out = classify(msg)
    assert out.confidence == 0.0


# ── pure address ──

@pytest.mark.parametrize("msg", ["wiii", "Wiii", "WIII", "wiii ơi", "wiii à"])
def test_pure_address_high_confidence(msg):
    out = classify(msg)
    assert out.confidence >= 0.90
    assert "address" in out.reason


# ── greetings ──

@pytest.mark.parametrize("msg", [
    "alo", "alo Wiii", "chào", "Chào Wiii", "hi", "hello", "hey",
])
def test_greeting_high_confidence(msg):
    out = classify(msg)
    assert out.confidence >= 0.85, f"{msg!r} should be high-confidence casual"


# ── acknowledgments ──

@pytest.mark.parametrize("msg", [
    "ok", "oke", "vâng", "dạ", "ừ", "không", "không đâu", "thôi",
    "huhu", "hihi", "haha", "wow", "tốt",
])
def test_acknowledgment_high_confidence(msg):
    out = classify(msg)
    assert out.confidence >= 0.85, f"{msg!r} should be high-confidence casual"


# ── short multi-word with casual token ──

@pytest.mark.parametrize("msg", [
    "ok cảm ơn",
    "không đâu nha",
])
def test_short_with_casual_token_medium_confidence(msg):
    """Short multi-word with a casual marker but NOT a greeting prefix
    — these get the medium-confidence fast-path (≥ 0.7) but stay below
    the 0.9 hard-fast-path threshold so a borderline case can still
    fall back to the full pipeline."""
    out = classify(msg)
    assert 0.7 <= out.confidence < 0.9


def test_greeting_with_address_gets_high_confidence():
    """'hi cậu' starts with the greeting token + space, so it's
    treated as a full greeting (>= 0.9), not a 'short multi-word'
    soft signal."""
    out = classify("hi cậu")
    assert out.confidence >= 0.9


# ── questions BLOCK fast-path ──

@pytest.mark.parametrize("msg", [
    "Tên mình là gì?",
    "How do I use this?",
    "Làm sao để học COLREGs?",
    "Giải thích Quy tắc 13",
    "tóm tắt MARPOL",
    "tại sao lại vậy",
    "search Vietnamese maritime law",
])
def test_questions_blocked(msg):
    out = classify(msg)
    assert out.confidence == 0.0
    assert "blocked" in out.reason or "no casual markers" in out.reason


def test_question_mark_alone_blocks():
    """Even a short message ending in '?' shouldn't fast-path —
    user might be asking a real question with terse phrasing."""
    out = classify("ok?")
    assert out.confidence == 0.0


# ── knowledge / tool markers BLOCK ──

@pytest.mark.parametrize("msg", [
    "rule 13",
    "tìm thông tin về COLREGs",
    "code Python để xử lý",
    "Điều 15 SOLAS",
])
def test_knowledge_markers_blocked(msg):
    out = classify(msg)
    assert out.confidence == 0.0


# ── long messages ──

def test_long_message_blocked_even_with_casual_words():
    """A long message with a casual prefix is NOT casual — fast-path
    is for short utterances only."""
    msg = "alo Wiii, " + ("nhân tiện hôm nay cậu thế nào " * 5)
    assert len(msg) > 80
    out = classify(msg)
    assert out.confidence == 0.0
    assert "too long" in out.reason


# ── unicode / diacritic robustness ──

def test_diacritics_handled_correctly():
    out = classify("không đâu")
    assert out.confidence >= 0.85
    out2 = classify("khong dau")
    assert out2.confidence >= 0.85


# ── matched_token field ──

def test_matched_token_populated_for_greetings():
    out = classify("hi")
    assert out.matched_token == "hi"


def test_matched_token_none_for_blocked_messages():
    out = classify("Giải thích cho tôi")
    assert out.matched_token is None


# ── reason field is informative ──

def test_reason_field_present_for_every_verdict():
    cases = ["", "alo", "wiii", "ok", "What is x?", "tìm", "x" * 100]
    for msg in cases:
        out = classify(msg)
        assert out.reason  # non-empty string for every case
