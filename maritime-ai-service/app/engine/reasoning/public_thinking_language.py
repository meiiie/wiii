"""Thin language-alignment helpers for visible public thinking."""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, Optional

from app.engine.messages import Message
from app.engine.messages_adapters import to_openai_dict
from app.prompts.prompt_context_utils import (
    detect_message_language,
    normalize_response_language,
)

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z']+", re.IGNORECASE)
_VISIBLE_THINKING_EN_MARKERS = {
    "okay",
    "user",
    "need",
    "anchor",
    "approach",
    "trigger",
    "first",
    "finally",
    "hold",
    "wait",
    "draft",
    "drafting",
    "before",
    "answer",
    "rule",
    "explain",
    "asking",
    "greeting",
    "closing",
    "content",
    "plan",
    "practical",
    "advice",
    "exploring",
    "origins",
    "origin",
    "genesis",
    "remembering",
    "reflecting",
    "response",
    "inquiry",
    "delving",
    "heart",
    "myself",
    "recalling",
    "considering",
    "frame",
    "share",
    "memory",
    "history",
    "tone",
    "casual",
    "recollection",
}
_VISIBLE_THINKING_VI_MARKERS = {
    "minh",
    "nguoi",
    "dung",
    "hoc",
    "can",
    "chot",
    "tach",
    "nham",
    "lech",
    "giai",
    "thich",
    "luot",
    "nay",
    "mau",
}
_ALIGNMENT_FAILURE_MARKERS = (
    "khong thay khoi noi dung",
    "khong thay doan van ban",
    "vui long cung cap",
    "doan visible thinking",
    "i don't see the visible thinking",
    "please provide the text",
    "please provide the visible thinking",
    "you want translated",
)


def _extract_alignment_text(payload: Any) -> str:
    """Extract plain visible text from an LLM alignment response."""
    if payload is None:
        return ""

    if isinstance(payload, str):
        raw = payload.strip()
        if not raw:
            return ""
        try:
            from app.services.output_processor import extract_thinking_from_response

            cleaned, _thinking = extract_thinking_from_response(raw)
            cleaned_text = str(cleaned or "").strip()
            if cleaned_text:
                return cleaned_text
        except Exception:
            pass
        return raw

    if isinstance(payload, dict):
        payload_type = str(payload.get("type", "")).strip().lower()
        if payload_type == "text":
            return str(payload.get("text", "")).strip()
        if payload_type == "thinking":
            return str(payload.get("thinking", "")).strip()
        if payload.get("content") is not None:
            return _extract_alignment_text(payload.get("content"))
        if payload.get("text") is not None:
            return str(payload.get("text", "")).strip()
        if payload.get("thinking") is not None:
            return str(payload.get("thinking", "")).strip()
        return ""

    if isinstance(payload, list):
        text_parts: list[str] = []
        thinking_parts: list[str] = []
        for item in payload:
            if isinstance(item, dict):
                payload_type = str(item.get("type", "")).strip().lower()
                if payload_type == "text":
                    part = str(item.get("text", "")).strip()
                    if part:
                        text_parts.append(part)
                    continue
                if payload_type == "thinking":
                    part = str(item.get("thinking", "")).strip()
                    if part:
                        thinking_parts.append(part)
                    continue
            extracted = _extract_alignment_text(item)
            if extracted:
                text_parts.append(extracted)
        combined = "\n".join(text_parts).strip()
        if combined:
            return combined
        return "\n".join(thinking_parts).strip()

    content = getattr(payload, "content", None)
    if content is not None and content is not payload:
        extracted = _extract_alignment_text(content)
        if extracted:
            return extracted

    text = getattr(payload, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    return str(payload).strip()


def _detect_visible_thinking_language(text: str) -> Optional[str]:
    detected = detect_message_language(text)
    lowered = str(text or "").strip().lower()
    if not lowered:
        return detected

    tokens = {token.lower() for token in _TOKEN_RE.findall(lowered)}
    if not tokens:
        return detected

    en_score = len(tokens & _VISIBLE_THINKING_EN_MARKERS)
    vi_score = len(tokens & _VISIBLE_THINKING_VI_MARKERS)

    if detected == "en":
        en_score += 2
    elif detected == "vi":
        vi_score += 1

    if "i need" in lowered or "let me" in lowered or "the user" in lowered:
        en_score += 2
    if "i'm " in lowered or "im " in lowered:
        en_score += 1
    if (
        "my approach" in lowered
        or "let's see the plan" in lowered
        or "drafting content" in lowered
        or "greeting:" in lowered
        or "closing:" in lowered
        or "core rule" in lowered
        or "exploring origins" in lowered
        or "reflecting on the response" in lowered
        or "reflecting on this response" in lowered
        or "reflecting on the inquiry" in lowered
        or "recalling a genesis" in lowered
        or "recalling personal history" in lowered
        or "into the heart of this question" in lowered
        or "remembering the first night" in lowered
        or "i'm considering how to frame" in lowered
        or "i'll share a memory" in lowered
        or "natural, warm tone" in lowered
        or "casual recollection" in lowered
    ):
        en_score += 3
    if "nguoi dung" in lowered or "minh can" in lowered or "cho de" in lowered:
        vi_score += 2

    if en_score == 0 and vi_score == 0:
        return detected
    if en_score > vi_score:
        return "en"
    if vi_score > en_score:
        return "vi"
    return detected


def _looks_like_alignment_failure(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return True
    lowered = raw.lower()
    folded = "".join(
        ch for ch in unicodedata.normalize("NFKD", lowered)
        if not unicodedata.combining(ch)
    ).replace("đ", "d")
    return any(marker in lowered or marker in folded for marker in _ALIGNMENT_FAILURE_MARKERS)


def should_align_visible_thinking_language(
    text: str | None,
    *,
    target_language: Optional[str],
) -> bool:
    """Return True when a visible thought block is clearly in the wrong language."""
    clean = str(text or "").strip()
    if not clean:
        return False

    target = normalize_response_language(target_language)
    if not target:
        return False

    detected = _detect_visible_thinking_language(clean)
    if not detected:
        return False

    return detected != target


async def align_visible_thinking_language(
    text: str | None,
    *,
    target_language: Optional[str],
    alignment_mode: Optional[str] = None,
    llm: Any = None,
) -> str | None:
    """
    Align a visible thinking block to the resolved turn language.

    This is intentionally thin:
    - preserve ideas and paragraph structure
    - do not add new reasoning
    - do not summarize or explain
    """
    clean = str(text or "").strip()
    if not clean:
        return None

    target = normalize_response_language(target_language)
    if not target or not llm:
        candidate_llms: list[Any] = []
    else:
        candidate_llms = [llm]

    try:
        from app.engine.llm_pool import get_llm_light

        light_llm = get_llm_light()
        if light_llm is not None and all(light_llm is not item for item in candidate_llms):
            candidate_llms.append(light_llm)
    except Exception as exc:
        logger.debug("[PUBLIC_THINKING_LANGUAGE] Light translator unavailable: %s", exc)

    if not target or not candidate_llms:
        return clean

    if not should_align_visible_thinking_language(clean, target_language=target):
        return clean

    if target == "vi":
        system_prompt = (
            "Ban dang lam mot viec duy nhat: chuyen nguyen van mot doan noi tam sang tieng Viet tu nhien, co dau.\n"
            "BAT BUOC:\n"
            "- Giu nguyen y, thu tu, muc do chac/chua chac, va nhip suy nghi.\n"
            "- Giu cau truc doan neu co.\n"
            "- DICH CA heading markdown, cau chen, va nhan ke hoach sang tieng Viet.\n"
            "- KHONG giu lai cum tieng Anh kieu 'My Approach', 'First', 'Let's do this', 'Drafting content', 'Safety first'.\n"
            "- Co the giu nguyen ten rieng va thuat ngu chuyen mon nhu COLREGs, Rule 15, Give-way, Stand-on khi can.\n"
            "- KHONG them y moi.\n"
            "- KHONG bien no thanh cau tra loi cho user.\n"
            "- KHONG giai thich them.\n"
            "- Chi tra ve ban chuyen ngu cua doan van duoc cung cap."
        )
        retry_prompt = (
            "DICH NGUYEN VAN doan van sau sang tieng Viet co dau.\n"
            "Chi tra ve ban dich.\n"
            "Khong giu heading hay cum tu tieng Anh neu co the dich duoc.\n"
            "Khong giu cac nhan ke hoach kieu 'First', 'Drafting content', 'Let's do this'.\n"
            "Khong giai thich.\n"
            "Khong viet them."
        )
        if alignment_mode == "direct_selfhood":
            system_prompt += (
                "\n- Day la visible thinking cua Wiii trong mot turn cham vao chinh ban than minh.\n"
                '- Uu tien ngoi "minh", nhip tu than, am va gan; khong bien no thanh giong doc profile hay tu su san khau hoa.\n'
                '- Tranh van phong formal/dich may nhu "toi dang dao sau", "dieu co ve kha co ban doi voi su ton tai cua toi", "day la mot diem chinh can giai quyet".\n'
                '- Neu co heading, hay giu no tu nhien va song, khong can uy nghi hay khoa truong.\n'
                "- Van phai giu nguyen y va khong duoc them lore moi."
            )
            retry_prompt += (
                '\nUu tien ngoi "minh" va nhac nhe, tu nhien.\n'
                'Tranh giong formal nhu "toi dang dao sau" hay "day la mot diem chinh can giai quyet".'
            )
    else:
        system_prompt = (
            "You are aligning the LANGUAGE of a visible thinking block.\n"
            "Translate it into natural English.\n"
            "REQUIREMENTS:\n"
            "- Preserve ideas, order, confidence/uncertainty, and reasoning flow.\n"
            "- Preserve paragraph structure when possible.\n"
            "- Do not add new ideas.\n"
            "- Do not turn it into a user-facing answer.\n"
            "- Return only the translated thinking block."
        )
        retry_prompt = (
            "Translate the following visible thinking block into natural English.\n"
            "Return only the translation.\n"
            "Do not keep the source language.\n"
            "Do not explain or add anything."
        )

    async def _translate_block(source_text: str) -> str | None:
        best_effort: str | None = None
        for translator in candidate_llms:
            response = await translator.ainvoke(
                [
                    to_openai_dict(Message(role="system", content=system_prompt)),
                    to_openai_dict(Message(role="user", content=f"Doan can chuyen ngu:\n<<<\n{source_text}\n>>>")),
                ]
            )
            translated = _extract_alignment_text(response)
            if translated and not _looks_like_alignment_failure(translated):
                if not should_align_visible_thinking_language(
                    translated,
                    target_language=target,
                ):
                    return translated
                best_effort = best_effort or translated

            retry_response = await translator.ainvoke(
                [
                    to_openai_dict(Message(role="system", content=retry_prompt)),
                    to_openai_dict(Message(role="user", content=f"<<<\n{source_text}\n>>>")),
                ]
            )
            retried = _extract_alignment_text(retry_response)
            if retried and not _looks_like_alignment_failure(retried):
                if not should_align_visible_thinking_language(
                    retried,
                    target_language=target,
                ):
                    return retried
                best_effort = best_effort or retried

        if best_effort and not _looks_like_alignment_failure(best_effort):
            return best_effort
        return None

    async def _realign_mixed_paragraphs(source_text: str) -> str | None:
        parts = [part.strip() for part in re.split(r"\n{2,}", source_text) if part.strip()]
        if len(parts) < 2:
            return None

        aligned_parts: list[str] = []
        changed = False
        for paragraph in parts:
            if should_align_visible_thinking_language(paragraph, target_language=target):
                translated_part = await _translate_block(paragraph)
                if translated_part and not _looks_like_alignment_failure(translated_part):
                    aligned_parts.append(translated_part.strip())
                    changed = changed or translated_part.strip() != paragraph.strip()
                    continue
            aligned_parts.append(paragraph.strip())

        if not changed:
            return None

        candidate = "\n\n".join(part for part in aligned_parts if part).strip()
        if candidate:
            return candidate
        return None

    paragraphs = [part.strip() for part in re.split(r"\n{2,}", clean) if part.strip()]

    try:
        if len(clean) > 900 and len(paragraphs) >= 2:
            aligned_parts: list[str] = []
            changed = False
            for paragraph in paragraphs:
                if should_align_visible_thinking_language(paragraph, target_language=target):
                    translated_part = await _translate_block(paragraph)
                    if translated_part:
                        aligned_parts.append(translated_part.strip())
                        changed = changed or translated_part.strip() != paragraph.strip()
                        continue
                aligned_parts.append(paragraph.strip())

            aligned_text = "\n\n".join(part for part in aligned_parts if part).strip()
            if aligned_text and changed and not should_align_visible_thinking_language(
                aligned_text,
                target_language=target,
            ):
                return aligned_text

        translated_full = await _translate_block(clean)
        if translated_full:
            post_aligned = await _realign_mixed_paragraphs(translated_full)
            return post_aligned or translated_full
    except Exception as exc:
        logger.debug("[PUBLIC_THINKING_LANGUAGE] Alignment skipped after translation error: %s", exc)

    return clean
