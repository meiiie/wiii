"""Utilities for keeping tutor-visible thinking readable and non-answerish."""

from __future__ import annotations

import re
import unicodedata

from .reasoning_narrator import sanitize_visible_reasoning_text

_TUTOR_PRIVATE_REASONING_MARKERS = (
    "here's my interpretation",
    "before i answer",
    "my first draft",
    "system prompt",
    "prompt stack",
    "routing_metadata",
    "tool_call",
    "tool_result",
    "json payload",
    "langgraph",
    "pipeline",
    "now for the answer",
    "gio thi den phan cau tra loi",
    "bay gio den phan cau tra loi",
    "muc tieu cua toi la tra loi",
    "toi rat vui duoc giup",
    "rat vui duoc giup ban",
    "voi tu cach la wiii tutor",
    "duy tri phong cach wiii tutor",
    "them mot hoac hai bieu tuong cam xuc",
    "dieu chinh tong giong",
    "cau tra loi hoan hao",
    "cau tra loi nay",
    "phan hoi nay",
    "co so du lieu cua minh",
    "minh da san sang",
    "hinh tuong wiii tutor",
    "that than thien",
    "den luc tao ra cau tra loi",
    "ban tom tat ro rang",
)

_TUTOR_ANSWERISH_OPENERS = (
    "rule ",
    "colregs",
    "solas",
    "đây là",
    "day la",
    "quy tắc",
    "quy tac",
    "quy định",
    "quy dinh",
    "nội dung",
    "noi dung",
    "khi hai",
)

_TUTOR_REASONING_HINTS = (
    "mình ",
    "minh ",
    "người dùng",
    "nguoi dung",
    "người học",
    "nguoi hoc",
    "i need",
    "i should",
    "let me",
    "okay",
    "hold on",
    "wait",
    "if i",
    "thay vì",
    "thay vi",
    "nếu ",
    "neu ",
    "điểm dễ",
    "diem de",
    "mấu chốt",
    "mau chot",
    "phải nhấn",
    "phai nhan",
)

_TUTOR_USER_OPENING_MARKERS = (
    "nguoi dung",
    "nguoi hoc",
    "cau hoi nay",
    "yeu cau nay",
    "yeu cau tiep theo",
    "luot nay",
)

_TUTOR_GENERIC_OPENING_MARKERS = (
    "diem mau chot",
    "nut that",
    "thay vi",
    "de giai thich",
    "minh se",
    "dieu quan trong luc nay",
    "moc chac nhat",
)

_TUTOR_DECORATIVE_ASIDE_RE = re.compile(r"\((?:[^)\w\s]{2,}|[˶≽≼•⩊^_~><⊙◕ω☆♥]+[^)]*)\)")
_TUTOR_TOKEN_RE = re.compile(r"[a-z0-9]{3,}", re.IGNORECASE)
_THINKING_TAG_RE = re.compile(r"</?thinking>", re.IGNORECASE)
_MAX_TUTOR_PUBLIC_PARAGRAPHS = 5


def _normalize_tutor_text(text: str) -> str:
    raw = (text or "").strip().lower()
    folded = unicodedata.normalize("NFKD", raw)
    return "".join(ch for ch in folded if not unicodedata.combining(ch)).replace("đ", "d").replace("Đ", "D")


def _tutor_tokens(text: str) -> set[str]:
    return {token.lower() for token in _TUTOR_TOKEN_RE.findall(_normalize_tutor_text(text))}


def _is_headingish_paragraph(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    if stripped.startswith("**") and stripped.endswith("**"):
        return True
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if len(lines) != 1:
        return False
    tokens = _tutor_tokens(stripped)
    return 0 < len(tokens) <= 6 and len(stripped) <= 80


def _paragraphs_are_duplicateish(left: str, right: str) -> bool:
    left_norm = " ".join(_normalize_tutor_text(left).split())
    right_norm = " ".join(_normalize_tutor_text(right).split())
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm:
        return True

    left_tokens = _tutor_tokens(left)
    right_tokens = _tutor_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    if _is_headingish_paragraph(left) != _is_headingish_paragraph(right):
        return False

    overlap = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    containment = overlap / max(1, min(len(left_tokens), len(right_tokens)))
    jaccard = overlap / max(1, union)
    long_form_pair = len(left_tokens) >= 10 and len(right_tokens) >= 10
    left_prefix = " ".join(left_norm.split()[:4])
    right_prefix = " ".join(right_norm.split()[:4])
    same_prefix_family = left_prefix and right_prefix and left_prefix == right_prefix
    both_user_openers = any(left_norm.startswith(prefix) for prefix in _TUTOR_USER_OPENING_MARKERS) and any(
        right_norm.startswith(prefix) for prefix in _TUTOR_USER_OPENING_MARKERS
    )
    if both_user_openers and (containment >= 0.45 or jaccard >= 0.25):
        return True
    if same_prefix_family and (containment >= 0.42 or jaccard >= 0.24):
        return True
    if long_form_pair:
        return containment >= 0.78 or jaccard >= 0.58
    return containment >= 0.60 or jaccard >= 0.42


def _is_tutor_user_opening_paragraph(text: str) -> bool:
    normalized = _normalize_tutor_text(text)
    return any(normalized.startswith(prefix) for prefix in _TUTOR_USER_OPENING_MARKERS)


def sanitize_public_tutor_thinking(content: str | None) -> str | None:
    clean = sanitize_visible_reasoning_text(str(content or "")).strip()
    clean = _THINKING_TAG_RE.sub("", clean).strip()
    clean = _TUTOR_DECORATIVE_ASIDE_RE.sub("", clean).strip()
    if len(clean) < 24:
        return None

    paragraphs = [part.strip() for part in re.split(r"\n{2,}", clean) if part.strip()]
    if not paragraphs:
        return None

    if len(paragraphs) >= 2:
        first_norm = _normalize_tutor_text(paragraphs[0])
        if any(first_norm.startswith(prefix) for prefix in _TUTOR_GENERIC_OPENING_MARKERS):
            for idx, para in enumerate(paragraphs[1:], start=1):
                para_norm = _normalize_tutor_text(para)
                if any(para_norm.startswith(prefix) for prefix in _TUTOR_USER_OPENING_MARKERS):
                    promoted = paragraphs.pop(idx)
                    paragraphs.insert(0, promoted)
                    break

    deduped: list[str] = []
    has_user_opening = False
    for para in paragraphs:
        para_norm = _normalize_tutor_text(para)
        if not para_norm or len(para_norm) < 12:
            continue
        if any(marker in para_norm for marker in _TUTOR_PRIVATE_REASONING_MARKERS):
            continue
        if any(para_norm.startswith(prefix) for prefix in _TUTOR_ANSWERISH_OPENERS) and not any(
            hint in para_norm for hint in _TUTOR_REASONING_HINTS
        ):
            continue
        if _is_tutor_user_opening_paragraph(para):
            if has_user_opening and any(
                _is_tutor_user_opening_paragraph(existing)
                and _paragraphs_are_duplicateish(para, existing)
                for existing in deduped
            ):
                continue
            has_user_opening = True
        if any(_paragraphs_are_duplicateish(para, existing) for existing in deduped):
            continue
        deduped.append(para)
        if len(deduped) >= _MAX_TUTOR_PUBLIC_PARAGRAPHS:
            break

    if not deduped:
        return None

    sanitized = "\n\n".join(deduped).strip()
    if not sanitized:
        return None

    if len(deduped) == 1:
        first_sentence = _normalize_tutor_text(deduped[0]).split(".")[0].strip()
        if any(first_sentence.startswith(prefix) for prefix in _TUTOR_ANSWERISH_OPENERS) and not any(
            hint in first_sentence for hint in _TUTOR_REASONING_HINTS
        ):
            return None

    return sanitized
