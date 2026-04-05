"""Utilities for recognizing simple name-memory turns."""

from __future__ import annotations

import re
import unicodedata

_MEMORY_NAME_INTRO_MARKERS = (
    "minh ten",
    "toi ten",
    "em ten",
    "tao ten",
    "to ten",
    "ten minh",
    "nho giup minh",
    "nho giup toi",
    "hay nho ten minh",
)

_MEMORY_NAME_RECALL_MARKERS = (
    "minh ten gi",
    "toi ten gi",
    "em ten gi",
    "ten minh la gi",
    "ten toi la gi",
    "ten em la gi",
    "minh ten gi nhi",
    "toi ten gi nhi",
    "ban nho ten minh khong",
    "co nho ten minh khong",
)

_MEMORY_INTERROGATIVE_NAME_TOKENS = {
    "gi",
    "nao",
    "sao",
    "ai",
    "chi",
}


def _normalize_memory_query(query: str) -> str:
    raw = (query or "").strip().lower()
    folded = unicodedata.normalize("NFKD", raw)
    return "".join(ch for ch in folded if not unicodedata.combining(ch)).replace("đ", "d").replace("Đ", "D")


def _normalize_memory_token(text: str) -> str:
    return " ".join(_normalize_memory_query(text).split())


def extract_declared_name(query: str) -> str | None:
    text = (query or "").strip()
    if not text:
        return None

    patterns = (
        r"\b(?:mình|minh|toi|tôi|em|tao|tớ|to)\s+tên\s+là\s+([A-Za-zÀ-ỹ][\wÀ-ỹ-]{0,31})",
        r"\b(?:mình|minh|toi|tôi|em|tao|tớ|to)\s+tên\s+([A-Za-zÀ-ỹ][\wÀ-ỹ-]{0,31})",
        r"\btên\s+mình\s+là\s+([A-Za-zÀ-ỹ][\wÀ-ỹ-]{0,31})",
        r"\bten\s+minh\s+la\s+([A-Za-zÀ-ỹ][\wÀ-ỹ-]{0,31})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        candidate = match.group(1).strip(" ,.!?:;")
        normalized_candidate = _normalize_memory_token(candidate)
        if normalized_candidate in _MEMORY_INTERROGATIVE_NAME_TOKENS:
            return None
        return candidate
    return None


def classify_memory_name_turn(query: str) -> str:
    normalized = _normalize_memory_query(query)
    if any(marker in normalized for marker in _MEMORY_NAME_RECALL_MARKERS):
        return "recall"
    if extract_declared_name(query):
        return "introduction"
    if any(marker in normalized for marker in _MEMORY_NAME_INTRO_MARKERS):
        return "introduction"
    return "other"


def looks_like_name_introduction(query: str) -> bool:
    return classify_memory_name_turn(query) == "introduction"
