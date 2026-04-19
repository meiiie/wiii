"""Tutor response helpers extracted from tutor_node.py."""

import logging
import re
import unicodedata
from unittest.mock import Mock
from typing import Any, Optional

from app.engine.multi_agent.graph_runtime_helpers import _copy_runtime_metadata
from app.services.output_processor import extract_thinking_from_response

_MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+", re.MULTILINE)
_PAREN_BLOCK_RE = re.compile(r"\(([^()]*)\)")
_TUTOR_TOOL_PAYLOAD_MARKERS = (
    "<arg_key>",
    "<arg_value>",
    "figure_group_id",
    "renderer_kind",
    "visual_session_id",
    "tool_generate_visual",
    "\"renderer_contract\"",
    "\"visual_session_id\"",
    "<svg",
)


def build_tutor_fallback_response(query: str) -> str:
    """Fallback when the tutor LLM is unavailable."""
    return f"""Tôi sẽ giúp bạn với: "{query}"

Để học hiệu quả, bạn nên:
1. Đọc tài liệu gốc liên quan
2. Xem các ví dụ thực tế
3. Làm bài tập thực hành

Bạn muốn tôi giải thích khái niệm nào cụ thể?"""


def _ascii_key(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    normalized = normalized.replace("đ", "d").replace("Đ", "D")
    flattened = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(flattened.lower().split())


def _normalize_tutor_whitespace(text: str) -> str:
    clean = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    clean = _MARKDOWN_HEADING_RE.sub("", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean.strip()


def _strip_decorative_parentheticals(text: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        inner = match.group(1)
        key = _ascii_key(inner)
        alnum = re.sub(r"[^a-z0-9]+", "", key)
        compact = re.sub(r"\s+", "", inner)
        if not alnum and compact and len(compact) <= 24:
            return ""
        return match.group(0)

    cleaned = _PAREN_BLOCK_RE.sub(_replace, str(text or ""))
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _extract_tutor_chunk_text(content: Any) -> str:
    """Extract plain text from streamed tutor chunks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return str(content) if content else ""


def _read_first_sentence(text: str) -> str:
    stripped = str(text or "").lstrip()
    if not stripped:
        return ""
    match = re.match(r".+?(?:[.!?:](?=\s|$)|$)", stripped, re.S)
    return match.group(0).strip() if match else stripped


def _drop_first_sentence(text: str) -> str:
    stripped = str(text or "").lstrip()
    if not stripped:
        return ""
    match = re.match(r".+?(?:[.!?:](?=\s|$)|$)", stripped, re.S)
    if not match:
        return ""
    return stripped[match.end():].lstrip()


def _is_decorative_sentence(sentence: str) -> bool:
    key = _ascii_key(sentence)
    alnum = re.sub(r"[^a-z0-9]+", "", key)
    if alnum:
        return False
    compact = re.sub(r"\s+", "", str(sentence or ""))
    return bool(compact) and len(compact) <= 12


def _looks_like_soft_learning_opener(sentence: str) -> bool:
    key = _ascii_key(sentence)
    key = re.sub(r"^[^a-z0-9]+", "", key)
    if not key:
        return False

    if key.startswith(("chao ", "xin chao", "hello", "hi ")):
        return True
    if re.match(r"^[a-z0-9_]+ oi\b", key):
        return True
    if key.startswith(("de minh", "de wiii", "de toi", "de chung ta")) and any(
        phrase in key
        for phrase in ("giup", "lam ro", "phan biet", "giai thich", "tom tat", "di qua")
    ):
        return True
    if key.startswith(("minh vua tra cuu", "wiii vua tra cuu", "minh da tra cuu", "wiii da tra cuu")):
        return True
    if key.startswith(("minh hieu la", "wiii hieu la", "toi hieu la")):
        return True
    if key.startswith(("hinh nhu ban vua hoi lai", "ban vua hoi lai")):
        return True
    if key.startswith(("khong sao ca", "khong sao dau", "khong sao het")):
        return True
    if key.startswith("minh cung") and any(
        phrase in key for phrase in ("nhin", "di qua", "xem", "doi chieu")
    ):
        return True
    if key.startswith(("rat vui duoc gap", "rat vui duoc gap lai", "rat vui khi")):
        return True
    if key.startswith("hy vong cach giai thich") or key.startswith("neu can"):
        return True
    if key.startswith(("de minh", "de wiii", "de toi")) and any(
        phrase in key for phrase in ("chot lai", "nhac lai", "noi gon", "di lai")
    ):
        return True
    if key.startswith("viec ") and any(
        phrase in key
        for phrase in ("nen tang", "rat quan trong", "cuc ky quan trong", "de dam bao")
    ):
        return True
    return False


def _strip_learning_openers(text: str) -> str:
    remaining = text
    for _ in range(5):
        first_sentence = _read_first_sentence(remaining)
        if _is_decorative_sentence(first_sentence):
            remaining = _drop_first_sentence(remaining)
            continue
        if not _looks_like_soft_learning_opener(first_sentence):
            break
        remaining = _drop_first_sentence(remaining)
    return remaining or text


def _looks_like_comparison_query(query: str) -> bool:
    key = _ascii_key(query)
    if not key:
        return False
    markers = (
        "khac gi",
        "so sanh",
        "phan biet",
        "khac nhau",
        "rule 13",
        "rule 15",
        " versus ",
        " vs ",
    )
    return any(marker in key for marker in markers)


def _opens_with_structured_teaching_block(text: str) -> bool:
    for line in str(text or "").splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        key = _ascii_key(candidate.lstrip("*- "))
        if re.match(r"^\d+[.)]\s", candidate):
            return True
        if key.startswith(("rule ", "quy tac ", "diem khac biet", "diem mau chot")):
            return True
        return candidate.startswith(("**", "* ", "- "))
    return False


def _ensure_thesis_first_compare(text: str, *, query: str) -> str:
    if not _looks_like_comparison_query(query):
        return text

    first_sentence = _read_first_sentence(text)
    first_key = _ascii_key(first_sentence)
    if any(
        marker in first_key
        for marker in ("khac biet cot loi", "diem khac biet", "diem mau chot", "nam o")
    ):
        return text

    if not _opens_with_structured_teaching_block(text):
        return text

    thesis = (
        "Khác biệt cốt lõi nằm ở tiêu chí nhận diện và điều kiện áp dụng của từng vế; "
        "chốt được điểm neo này trước thì phần còn lại sẽ dễ đối chiếu hơn."
    )
    return f"{thesis}\n\n{text.lstrip()}"


def normalize_tutor_answer_shape(text: str, *, query: str = "") -> str:
    """Keep tutor answers thesis-first without sanding off Wiii's warmth."""
    clean = _normalize_tutor_whitespace(text)
    clean = _strip_decorative_parentheticals(clean)
    if not clean:
        return ""

    stripped = _strip_learning_openers(clean)
    if stripped != clean:
        clean = _ensure_thesis_first_compare(stripped, query=query)
    else:
        clean = stripped
    return _normalize_tutor_whitespace(clean)


def looks_like_tutor_placeholder_answer(text: str) -> bool:
    key = _ascii_key(text)
    if not key:
        return True
    raw_text = str(text or "")
    lowered_raw = raw_text.lower()
    if any(marker in lowered_raw for marker in _TUTOR_TOOL_PAYLOAD_MARKERS):
        return True
    stripped_raw = raw_text.lstrip()
    if stripped_raw.startswith("{") and (
        "\"id\"" in lowered_raw
        or "\"type\"" in lowered_raw
        or "\"renderer_kind\"" in lowered_raw
    ):
        return True
    if any(
        phrase in key
        for phrase in (
            "xin loi",
            "chua xu ly duoc yeu cau",
            "co gi do truc trac",
            "thu hoi lai",
            "thu hoi lai minh",
        )
    ):
        return True
    return len(key) < 80 and (
        key.startswith("xin loi")
        or key.startswith("hmm")
        or "nha" in key
    )


def recover_tutor_answer_from_messages(messages: list[Any], *, query: str = "") -> str:
    """Recover a substantive tutor answer from the last tool observation."""
    for message in reversed(messages):
        if getattr(message, "type", "") != "tool":
            continue
        raw_content = _normalize_tutor_whitespace(getattr(message, "content", ""))
        if not raw_content or raw_content.lower().startswith("error:"):
            continue
        if looks_like_tutor_placeholder_answer(raw_content):
            continue
        raw_content = re.sub(
            r"\s*<!--\s*confidence:[\s\S]*?-->",
            "",
            raw_content,
            flags=re.I,
        ).strip()
        candidate = normalize_tutor_answer_shape(raw_content, query=query)
        candidate = _ensure_thesis_first_compare(candidate, query=query)
        if candidate and not looks_like_tutor_placeholder_answer(candidate):
            return candidate
    return ""


async def collect_tutor_model_message(
    llm: Any,
    messages: list[Any],
    *,
    logger: logging.Logger,
    on_stream_reasoning_delta: Any = None,
) -> tuple[Any, str, bool]:
    """Collect a tutor model response with stream-first parity, fallback to ainvoke."""

    stream_fn = getattr(llm, "astream", None)
    if stream_fn is not None and not isinstance(stream_fn, Mock):
        try:
            stream_iter = stream_fn(messages)
            if hasattr(stream_iter, "__aiter__"):
                final_msg = None
                streamed_text_parts: list[str] = []
                async for chunk in stream_iter:
                    if final_msg is None:
                        final_msg = chunk
                    else:
                        final_msg = final_msg + chunk
                    text = _extract_tutor_chunk_text(getattr(chunk, "content", ""))
                    if text:
                        streamed_text_parts.append(text)
                    # Propagate reasoning deltas if callback provided
                    if on_stream_reasoning_delta is not None:
                        reasoning = getattr(chunk, "reasoning_content", None) or getattr(
                            getattr(chunk, "additional_kwargs", {}), "reasoning_content", None
                        )
                        if reasoning:
                            try:
                                await on_stream_reasoning_delta(reasoning)
                            except Exception:
                                pass
                if final_msg is not None:
                    _copy_runtime_metadata(llm, final_msg)
                    return final_msg, "".join(streamed_text_parts), True
        except Exception as exc:
            logger.debug("[TUTOR] astream collection failed, falling back to ainvoke: %s", exc)

    response = await llm.ainvoke(messages)
    _copy_runtime_metadata(llm, response)
    return response, "", False


async def collect_tutor_model_message_with_failover(
    llm: Any,
    messages: list[Any],
    *,
    logger: logging.Logger,
    tier: str = "moderate",
    provider: str | None = None,
) -> tuple[Any, str, bool]:
    """Collect tutor model response with failover to alternate provider.

    Tries the primary LLM first. On failure, attempts to construct a
    rescue LLM from the configured failover chain and retry.
    """
    # Try primary
    try:
        result, text, streamed = await collect_tutor_model_message(llm, messages, logger=logger)
        if result is not None:
            return result, text, streamed
    except Exception as exc:
        logger.warning("[TUTOR] Primary LLM failed in failover path: %s", exc)

    # Failover: try to get a rescue LLM
    try:
        from app.engine.llm_pool import get_llm_moderate, get_llm_light
        rescue_llm = get_llm_moderate() if tier == "moderate" else get_llm_light()
        if rescue_llm is not None:
            logger.info("[TUTOR] Attempting failover with tier=%s", tier)
            result, text, streamed = await collect_tutor_model_message(rescue_llm, messages, logger=logger)
            if result is not None:
                return result, text, streamed
    except Exception as exc:
        logger.warning("[TUTOR] Failover LLM also failed: %s", exc)

    return None, "", False


def extract_tutor_content_with_thinking(
    content,
    *,
    logger: logging.Logger,
    extractor=extract_thinking_from_response,
    query: str = "",
) -> tuple[str, Optional[str]]:
    """
    Extract text AND thinking from LLM response content.

    Sprint 64 fix: if text is empty but thinking is substantial, recover
    the thinking as response text instead of dropping the whole answer.
    """
    text, thinking = extractor(content)
    clean_text = normalize_tutor_answer_shape(text, query=query) if text else ""

    if thinking:
        logger.info("[TUTOR] Native thinking extracted: %d chars", len(thinking))

    if not clean_text and thinking and len(thinking) > 50:
        logger.warning(
            "[TUTOR] Response empty but thinking has content (%d chars), "
            "recovering thinking as response text",
            len(thinking),
        )
        return thinking.strip(), None

    return clean_text, thinking


def build_tutor_rescue_response(
    query: str,
    *,
    note_internal_gap: bool = False,
) -> str:
    """Build a rescue response when the tutor LLM fails or returns empty.

    Provides a structured fallback that acknowledges the gap and offers
    to help the user explore further.
    """
    gap_note = ""
    if note_internal_gap:
        gap_note = (
            "\n\nMình đã kiểm tra kho nội bộ nhưng chưa tìm thấy tài liệu khớp "
            "với câu hỏi này, nên phần trả lời dưới đây dựa trên kiến thức chung."
        )
    return (
        f"Mình sẽ giúp bạn hiểu về: **{query}**\n"
        f"{gap_note}\n\n"
        "Để mình giải thích theo cách dễ hiểu nhất nhé. "
        "Nếu bạn cần đi sâu hơn hay có câu hỏi phụ, cứ hỏi nhé!"
    )


def apply_quiz_socratic_guardrail(
    response: str,
    *,
    context: Any = None,
) -> str:
    """Socratic guardrail for quiz/test pages — avoid revealing answers directly.

    When LMS page context indicates the user is on a quiz page, this function
    redacts direct answers and replaces them with Socratic hints.
    """
    if not response or not context:
        return response

    # Check if we're on a quiz/test page via LMS page context
    page_context = None
    if isinstance(context, dict):
        page_context = context.get("page_context") or context.get("host_context")
    if not page_context:
        return response

    page_type = ""
    if isinstance(page_context, dict):
        page_type = str(page_context.get("page_type", "")).lower()

    # Only apply on quiz/test pages
    if page_type not in ("quiz", "test", "exam", "assessment"):
        return response

    # Socratic transformation markers — simple heuristic
    direct_answer_patterns = [
        (r"Đáp án (đúng|chính xác)\s*(?:là|:)\s*(.+?)\."),
        r"đáp án đúng là",
        r"đáp án chính xác là",
    ]
    import re as _re
    for pattern in direct_answer_patterns:
        if isinstance(pattern, tuple):
            if _re.search(pattern[0], response, _re.IGNORECASE):
                response = _re.sub(
                    pattern[0],
                    r"Mình thấy bạn đang làm bài kiểm tra — mình sẽ gợi ý thay vì đưa đáp án trực tiếp. Hãy suy nghĩ về: \2.",
                    response,
                    flags=_re.IGNORECASE,
                )
        elif _re.search(pattern, response, _re.IGNORECASE):
            response = _re.sub(
                pattern,
                "Mình thấy bạn đang làm bài kiểm tra — mình sẽ gợi ý thay vì đưa đáp án trực tiếp. "
                "Hãy xem lại tài liệu và thử xác định đáp án nhé!",
                response,
                flags=_re.IGNORECASE,
            )

    return response
