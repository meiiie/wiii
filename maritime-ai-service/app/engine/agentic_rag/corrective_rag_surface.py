"""Surface and translation helpers for Corrective RAG."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def normalize_visible_text(text: object) -> str:
    """Collapse whitespace so surface text stays compact."""
    return " ".join(str(text or "").split()).strip()


def is_no_doc_retrieval_text(text: object) -> bool:
    normalized = normalize_visible_text(text).lower()
    return any(
        marker in normalized
        for marker in (
            "0 tài liệu",
            "không tìm thấy tài liệu",
            "khong tim thay tai lieu",
            "0 documents",
            "no documents",
        )
    )


def build_retrieval_surface_text(doc_count: int) -> str:
    if doc_count <= 0:
        return "Mình chưa thấy nguồn nào thật sự khớp, nên mình chuyển sang cách đáp trực tiếp."
    if doc_count == 1:
        return "Mình đã tìm được một nguồn phù hợp, đang kiểm tra lại cho chắc."
    return "Mình đã kéo được vài nguồn phù hợp, đang rà lại để chốt câu trả lời."


def build_house_fallback_reply() -> str:
    return "Mình chưa thấy nguồn nội bộ thật sự khớp, nên mình chuyển sang cách đáp trực tiếp nhé."


def is_likely_english(text: str) -> bool:
    """Detect if text is primarily English (lacks Vietnamese diacritics)."""
    if not text or len(text) < 30:
        return False
    vn_diacritics = set(
        "àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợ"
        "ùúủũụưứừửữựỳýỷỹỵđÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆ"
        "ÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ"
    )
    vn_count = sum(1 for c in text if c in vn_diacritics)
    return vn_count / max(len(text), 1) < 0.01


async def translate_to_vietnamese(text: str) -> str:
    """Translate English text to Vietnamese using LLM light."""
    try:
        from app.engine.agentic_rag.runtime_llm_socket import (
            ainvoke_agentic_rag_llm,
            resolve_agentic_rag_llm,
        )
        from app.engine.llm_factory import ThinkingTier
        from app.engine.llm_pool import get_llm_light
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = resolve_agentic_rag_llm(
            tier=ThinkingTier.LIGHT,
            fallback_factory=get_llm_light,
            component="CorrectiveRAGTranslate",
        )
        if not llm:
            return text

        messages = [
            SystemMessage(content=(
                "Dịch đoạn văn sau sang tiếng Việt tự nhiên, chính xác. "
                "Giữ nguyên thuật ngữ chuyên ngành hàng hải/giao thông bằng tiếng Anh "
                "nếu cần (ví dụ: COLREGs, SOLAS, starboard). "
                "CHỈ trả lời bản dịch tiếng Việt, KHÔNG thêm giải thích hay ghi chú. "
                "KHÔNG bao gồm quá trình suy nghĩ."
            )),
            HumanMessage(content=text),
        ]
        response = await ainvoke_agentic_rag_llm(
            llm=llm,
            messages=messages,
            tier=ThinkingTier.LIGHT,
            component="CorrectiveRAGTranslate",
        )

        from app.services.output_processor import extract_thinking_from_response

        translated, _ = extract_thinking_from_response(response.content)
        result = translated.strip()
        if result and len(result) > 20:
            logger.info("[CRAG] Translated fallback to Vietnamese: %d chars", len(result))
            return result
        return text
    except Exception as exc:
        logger.warning("[CRAG] Translation failed, using original: %s", exc)
        return text
