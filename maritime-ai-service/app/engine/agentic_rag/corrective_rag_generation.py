"""
Generation helpers for Corrective RAG.

Keeps the CorrectiveRAG class focused on orchestration while these helpers own
fallback and document-grounded answer generation.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.engine.agentic_rag.corrective_rag_prompts import (
    build_fallback_system_prompt,
    resolve_fallback_domain_name,
)
from app.engine.agentic_rag.corrective_rag_surface import (
    build_house_fallback_reply,
    is_likely_english,
    translate_to_vietnamese,
)

logger = logging.getLogger(__name__)


async def generate_fallback_impl(
    *,
    query: str,
    context: dict[str, Any],
    settings_obj: Any,
) -> str:
    """Generate an answer from model general knowledge when RAG has no docs."""
    try:
        from app.engine.llm_pool import get_llm_light
        from app.prompts.prompt_loader import get_prompt_loader
        from app.services.output_processor import extract_thinking_from_response
        from langchain_core.messages import HumanMessage, SystemMessage

        # Prefer pool directly — the runtime socket may have stale failover chains
        llm = get_llm_light()
        if not llm:
            return ""

        domain_name = resolve_fallback_domain_name(context, settings_obj)

        loader = get_prompt_loader()
        identity = loader.get_identity().get("identity", {})
        personality = identity.get("personality", {}).get("summary", "")
        emoji_usage = identity.get("voice", {}).get("emoji_usage", "")
        user_name = context.get("user_name", "")
        name_hint = f"User tên {user_name}. " if user_name else ""
        avoid_rules = identity.get("response_style", {}).get("avoid", [])
        avoid_text = " ".join(f"Tránh: {rule}." for rule in avoid_rules) if avoid_rules else ""

        natural_enabled = getattr(settings_obj, "enable_natural_conversation", False) is True
        sys_content = build_fallback_system_prompt(
            settings_obj=settings_obj,
            personality=personality,
            emoji_usage=emoji_usage,
            name_hint=name_hint,
            avoid_text=avoid_text,
            domain_name=domain_name,
            natural_enabled=natural_enabled,
        )

        messages = [
            SystemMessage(content=sys_content),
            HumanMessage(content=query),
        ]
        response = await llm.ainvoke(messages)
        text, native_thinking = extract_thinking_from_response(response.content)
        text = text.strip()

        if native_thinking:
            logger.info("[CRAG] Fallback native thinking: %d chars", len(native_thinking))

        if text and is_likely_english(text):
            logger.info("[CRAG] Fallback response is English, translating to Vietnamese...")
            text = await translate_to_vietnamese(text)

        return (text or build_house_fallback_reply(), native_thinking)
    except Exception as exc:
        logger.warning("[CRAG] Fallback generation failed: %s", exc)
        return build_house_fallback_reply()


async def generate_answer_impl(
    *,
    rag_agent: Any,
    query: str,
    documents: list[dict[str, Any]],
    context: dict[str, Any],
    generate_fallback,
) -> tuple[str, list[dict[str, Any]], Optional[str]]:
    """Generate an answer from already-retrieved documents."""
    if not rag_agent:
        return "Hmm, mình chưa sẵn sàng xử lý lúc này nè~ Bạn thử lại sau nhé? (˶˃ ᵕ ˂˶)", documents, None

    if not documents:
        fallback_text, fallback_thinking = await generate_fallback(query, context)
        return fallback_text, [], fallback_thinking

    try:
        history = context.get("conversation_history", "")
        response = await rag_agent.generate_from_documents(
            question=query,
            documents=documents,
            conversation_history=history,
            user_role=context.get("user_role", "student"),
            user_name=context.get("user_name"),
            is_follow_up=context.get("is_follow_up", bool(history)),
            entity_context=context.get("entity_context", ""),
            response_language=context.get("response_language"),
            host_context_prompt=context.get("host_context_prompt", ""),
            living_context_prompt=context.get("living_context_prompt", ""),
            skill_context=context.get("skill_context", ""),
            capability_context=context.get("capability_context", ""),
            _skill_prompts=context.get("_skill_prompts"),
        )
        native_thinking = response.native_thinking
        if native_thinking:
            logger.info("[CRAG] Native thinking from Gemini: %d chars", len(native_thinking))
        return response.content, documents, native_thinking
    except Exception as exc:
        logger.error("[CRAG] Generation failed: %s", exc)
        return "Hmm, mình gặp chút trục trặc khi soạn câu trả lời nè~ Bạn thử lại giúp mình nhé? ≽^•⩊•^≼", documents, None
