"""Heuristic casual-intent classifier — no LLM call needed.

Phase 33b of the runtime migration epic (issue #207). Today every chat
turn pays the multi-agent tax (guardian → supervisor → direct →
synthesizer). For long educational queries that's appropriate.
For casual greetings ("alo", "hihi", "ok"), each LLM call adds 2-5s of
latency that the user can FEEL. Big orgs avoid this by routing casual
turns through a fast lane.

The detector here is **deliberately conservative** — when unsure it
returns ``None``, and the caller falls back to the full multi-agent
flow. The cost of a false-positive (treating a real question as
casual) is high (Wiii answers wrong). The cost of a false-negative
(running the full pipeline on "alo") is low (just slower than ideal).

**No LLM call.** Pure-Python pattern match + length heuristics. Sub-ms.

Confidence is a 0-1 float so callers can pick their own threshold.
Recommended:
- ``>= 0.85`` — strong casual signal, fast-path is safe.
- ``>= 0.70`` — soft signal; consider fast-path only if no tools needed.
- ``< 0.70`` — let the full multi-agent decide.

Out of scope:
- Multilingual signals beyond Vietnamese + a few English greetings.
- Sentiment analysis (Sprint 210d already runs that).
- Tool-call intent detection (different problem).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# Vietnamese + English greeting / acknowledgment / filler markers.
# All lowercase; matched against word-boundary or full-message regex.
_GREETING_TOKENS = frozenset(
    {
        # Vietnamese
        "chào", "chao", "hí", "hi", "hello", "hey", "alo", "yo",
        "xin chào", "xin chao",
        # Address-only ("Wiii ơi", "Wiii à") — checked separately
    }
)
_ACK_TOKENS = frozenset(
    {
        # Yes / acknowledgment
        "ok", "oke", "okay", "uhm", "ừm", "ừ", "ờ", "à", "vâng", "dạ",
        "yes", "ya", "yep", "đúng", "đúng rồi", "ừ ha", "à ừ",
        # No / rejection
        "không", "khong", "no", "nope", "không đâu", "khong dau",
        "thôi", "thoi",
        # Mild surprise / filler
        "hmm", "huhu", "hihi", "haha", "hehe", "kk", "lol", "wow",
        "uầy", "ơ", "ồ",
        "tốt", "tot", "ngon", "ổn", "on",
    }
)
# Pure address (user calls Wiii's name without follow-up).
_ADDRESS_TOKENS = frozenset({"wiii", "wiii ơi", "wiii à", "wiii oi", "wiii a"})

# Markers that BLOCK the fast-path even when the rest of the heuristic
# would say "casual". Anything that smells like a real question, a
# tool intent, or a knowledge query routes through the full pipeline.
_HARD_QUESTION_MARKERS = (
    re.compile(r"\?$"),
    re.compile(r"\b(làm sao|làm thế nào|how do|how to|why|tại sao|sao lại)\b", re.IGNORECASE),
    re.compile(r"\b(giải thích|explain|tóm tắt|summary|so sánh|compare)\b", re.IGNORECASE),
    re.compile(r"\b(rule|quy tắc|colregs|solas|marpol|điều)\b", re.IGNORECASE),
    re.compile(r"\b(tìm|search|tra cứu|lookup|fetch)\b", re.IGNORECASE),
    re.compile(r"\b(code|lập trình|python|javascript|sql)\b", re.IGNORECASE),
)


@dataclass(slots=True, frozen=True)
class CasualIntent:
    """Verdict + reason from the heuristic classifier."""

    confidence: float
    reason: str
    matched_token: Optional[str] = None


def _normalize(message: str) -> str:
    return (message or "").strip().lower()


def classify(message: str) -> CasualIntent:
    """Return a confidence score that ``message`` is casual social chat.

    ``confidence == 0.0`` means "definitely not casual — treat as a
    knowledge / tool request". Higher values mean the message looks
    like a greeting, acknowledgment, or short filler. The caller
    decides the threshold.
    """
    if not message or not message.strip():
        return CasualIntent(confidence=0.0, reason="empty")

    norm = _normalize(message)

    # Hard blockers — anything that smells like a real question or
    # knowledge / tool request kills the fast-path immediately.
    for pattern in _HARD_QUESTION_MARKERS:
        if pattern.search(message):
            return CasualIntent(
                confidence=0.0,
                reason=f"blocked by question/knowledge marker: {pattern.pattern}",
            )

    # Length-based prior — very short messages are more likely casual.
    length = len(norm)
    if length > 80:
        return CasualIntent(
            confidence=0.0, reason=f"too long ({length} chars > 80)"
        )

    # Pure address: "Wiii ơi", "Wiii à" — strong casual signal.
    if norm in _ADDRESS_TOKENS:
        return CasualIntent(
            confidence=0.95,
            reason="pure address",
            matched_token=norm,
        )

    # Greeting-only (with optional address).
    for token in _GREETING_TOKENS:
        if norm == token or norm.startswith(token + " ") or norm == f"{token} wiii":
            return CasualIntent(
                confidence=0.92,
                reason="greeting-only",
                matched_token=token,
            )

    # Acknowledgment / single-word filler.
    if norm in _ACK_TOKENS:
        return CasualIntent(
            confidence=0.90,
            reason="single-word acknowledgment",
            matched_token=norm,
        )

    # Multi-word but short and contains a casual marker.
    if length <= 30:
        words = set(norm.split())
        ack_overlap = words & _ACK_TOKENS
        greet_overlap = words & _GREETING_TOKENS
        if ack_overlap or greet_overlap:
            matched = next(iter(ack_overlap | greet_overlap))
            return CasualIntent(
                confidence=0.78,
                reason="short utterance contains casual token",
                matched_token=matched,
            )

    # Length 30-80 with NO casual markers and NO question markers —
    # ambiguous, let the full pipeline handle it.
    return CasualIntent(
        confidence=0.0,
        reason="no casual markers found",
    )


__all__ = ["CasualIntent", "classify"]
