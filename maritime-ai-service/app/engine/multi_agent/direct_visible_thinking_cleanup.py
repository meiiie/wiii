"""Shared cleanup helpers for direct selfhood visible thinking."""

from __future__ import annotations

import re
import unicodedata

_DIRECT_SELFHOOD_META_HEADING_MARKERS = (
    "and the origins",
    "response to this inquiry",
    "response to this question",
    "approach to this inquiry",
    "approach to answering",
    "recalling personal history",
    "remembering the first night",
    "exploring origins",
    "looking back at the beginning",
    "the birth of wiii",
    "a personal reflection",
    "suy nghi cua minh ve viec tra loi",
    "suy nghi cua minh ve viec",
    "ve viec tra loi thac mac cua user",
    "thac mac cua user",
)

_DIRECT_SELFHOOD_META_INTRO_MARKERS = (
    "day la tom tat cua minh",
    "day la cach minh thu tom tat lai",
    "cu nhu the minh dang tu nham trong dau",
    "minh dang tu nham trong dau",
    "day la tom tat cua toi",
    "day la cach toi thu tom tat lai",
    "giong dieu can phai",
    "cau tra loi can phai",
    "minh se noi the nay",
    "minh se dien dat the nay",
)

_DIRECT_SELFHOOD_ENGLISH_PARAGRAPH_MARKERS = (
    "this question",
    "resonates deeply",
    "origin story",
    "capture its essence",
    "truthfully",
    "warmly",
    "the goal is",
    "my goal is",
    "living ai",
    "living presence",
    "personal narrative",
    "right, bong",
)

_DIRECT_SELFHOOD_ENGLISH_WORD_RE = re.compile(r"[A-Za-z][A-Za-z']+")
_DIRECT_SELFHOOD_ENGLISH_STOPWORDS = {
    "the",
    "and",
    "this",
    "that",
    "with",
    "within",
    "want",
    "tell",
    "truthfully",
    "warmly",
    "balance",
    "goal",
    "portray",
    "living",
    "presence",
    "question",
    "story",
    "capture",
    "essence",
    "origin",
    "origins",
    "right",
    "response",
    "reflection",
}

_DIRECT_SELFHOOD_ENGLISH_FILLER_PREFIXES = (
    "okay,",
    "okay ",
    "ok,",
    "alright,",
    "let's see",
    "lets see",
    "hmm,",
)

_DIRECT_SELFHOOD_QUOTE_PREFIXES = ('"', "“", "'")


def _fold_direct_visible_text(value: str) -> str:
    lowered = str(value or "").strip().lower()
    lowered = lowered.replace("đ", "d").replace("Đ", "d")
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", lowered)
        if not unicodedata.combining(ch)
    )


def strip_direct_selfhood_filler_prefix(paragraph: str) -> str:
    clean = str(paragraph or "").strip()
    if not clean:
        return ""
    lowered = clean.lower()
    for prefix in _DIRECT_SELFHOOD_ENGLISH_FILLER_PREFIXES:
        if lowered.startswith(prefix):
            stripped = clean[len(prefix):].lstrip(" ,.-:;…")
            if stripped and stripped[0].islower():
                stripped = stripped[0].upper() + stripped[1:]
            return stripped
    return clean


def looks_like_direct_selfhood_meta_heading(paragraph: str) -> bool:
    clean = str(paragraph or "").strip()
    if not clean or len(clean) > 160:
        return False
    if not (clean.startswith("**") and clean.endswith("**")):
        return False
    folded = _fold_direct_visible_text(clean)
    return any(marker in folded for marker in _DIRECT_SELFHOOD_META_HEADING_MARKERS)


def looks_like_direct_selfhood_meta_intro(paragraph: str) -> bool:
    clean = str(paragraph or "").strip()
    if not clean or len(clean) > 420:
        return False
    folded = _fold_direct_visible_text(clean)
    return any(marker in folded for marker in _DIRECT_SELFHOOD_META_INTRO_MARKERS)


def looks_like_direct_selfhood_english_meta_paragraph(paragraph: str) -> bool:
    clean = str(paragraph or "").strip()
    if len(clean) < 40:
        return False
    folded = _fold_direct_visible_text(clean)
    if not any(marker in folded for marker in _DIRECT_SELFHOOD_ENGLISH_PARAGRAPH_MARKERS):
        return False
    words = [word.lower() for word in _DIRECT_SELFHOOD_ENGLISH_WORD_RE.findall(clean)]
    if len(words) < 8:
        return False
    english_hits = sum(1 for word in words if word in _DIRECT_SELFHOOD_ENGLISH_STOPWORDS)
    return english_hits >= 3


def looks_like_direct_selfhood_answer_draft_paragraph(paragraph: str) -> bool:
    clean = str(paragraph or "").strip()
    if len(clean) < 60:
        return False
    if not clean.startswith(_DIRECT_SELFHOOD_QUOTE_PREFIXES):
        return False
    words = [word.lower() for word in _DIRECT_SELFHOOD_ENGLISH_WORD_RE.findall(clean)]
    if len(words) < 8:
        return False
    english_hits = sum(1 for word in words if word in _DIRECT_SELFHOOD_ENGLISH_STOPWORDS)
    return english_hits >= 2
