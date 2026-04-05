"""Helpers for deduplicating public direct-lane thinking blocks."""

from __future__ import annotations

from typing import Any


def _normalize_direct_public_chunk(text: Any) -> str:
    return " ".join(str(text or "").lower().split())


def remember_direct_public_thinking_chunks(state: dict | None, chunks: list[str]) -> None:
    """Persist the latest direct-lane public thinking chunks for dedupe checks."""
    if not isinstance(state, dict):
        return
    cleaned = [str(chunk or "").strip() for chunk in chunks if str(chunk or "").strip()]
    if not cleaned:
        return
    state["_direct_last_public_thinking_chunks"] = cleaned[-8:]


def should_emit_direct_public_thinking_chunks(state: dict | None, chunks: list[str]) -> bool:
    """Return True when the next direct thinking block differs from the previous one."""
    cleaned = [str(chunk or "").strip() for chunk in chunks if str(chunk or "").strip()]
    if not cleaned:
        return False
    if not isinstance(state, dict):
        return True

    previous = [
        str(chunk or "").strip()
        for chunk in (state.get("_direct_last_public_thinking_chunks") or [])
        if str(chunk or "").strip()
    ]
    if not previous:
        return True

    return [_normalize_direct_public_chunk(chunk) for chunk in previous] != [
        _normalize_direct_public_chunk(chunk) for chunk in cleaned
    ]
