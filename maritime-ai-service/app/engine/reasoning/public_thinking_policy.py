"""Lane-aware policy selection for curated public thinking."""

from __future__ import annotations

from .public_thinking_contracts import ThinkingToneMode


def resolve_public_thinking_mode(*, lane: str, query: str = "", intent: str = "") -> ThinkingToneMode:
    lane_key = (lane or "").strip().lower()
    intent_key = (intent or "").strip().lower()
    query_key = (query or "").strip().lower()

    if lane_key == "memory":
        return ThinkingToneMode.RELATIONAL_COMPANION
    if lane_key == "tutor":
        return ThinkingToneMode.INSTRUCTIONAL_COMPANION
    if lane_key == "rag":
        return ThinkingToneMode.TECHNICAL_RESTRAINED
    if lane_key == "direct":
        if any(token in query_key for token in ("phân tích", "phan tich", "analysis")):
            return ThinkingToneMode.ANALYTICAL_COMPANION
        return ThinkingToneMode.RELATIONAL_COMPANION
    if intent_key in {"personal", "social"}:
        return ThinkingToneMode.RELATIONAL_COMPANION
    if intent_key in {"learning", "lookup"}:
        return ThinkingToneMode.INSTRUCTIONAL_COMPANION
    return ThinkingToneMode.ANALYTICAL_COMPANION
