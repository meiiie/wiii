"""Pure helper routines extracted from the supervisor shell."""

from __future__ import annotations

from typing import Any, Optional

from app.engine.multi_agent.supervisor_hint_runtime import (
    _looks_visual_followup_request_impl,
    _normalize_router_text_impl,
)


def resolve_house_routing_provider_impl(
    state: Any,
    *,
    settings_obj: Any,
    logger: Any,
) -> Optional[str]:
    """Pick the best currently-runnable provider for house routing."""
    from app.engine.llm_pool import LLMPool

    primary = str(settings_obj.llm_provider or "google").strip().lower()
    try:
        from app.services.llm_selectability_service import choose_best_runtime_provider

        best = choose_best_runtime_provider(
            preferred_provider=primary,
            provider_order=LLMPool._get_request_provider_chain(),
            allow_degraded_fallback=False,
        )
        selected = str(best.provider or "").strip().lower() if best is not None else ""
        if selected:
            if selected != primary:
                logger.info(
                    "[SUPERVISOR] House routing switched from %s to selectable %s",
                    primary,
                    selected,
                )
            return selected
    except Exception as exc:
        logger.debug("[SUPERVISOR] Selectability-aware routing provider skipped: %s", exc)

    provider = LLMPool._providers.get(primary)
    if provider and provider.is_available():
        return primary
    for name in LLMPool._get_provider_chain():
        current = LLMPool._providers.get(name)
        if current and current.is_available():
            logger.info("[SUPERVISOR] Primary %s unavailable, using %s", primary, name)
            return name
    return primary


def get_domain_keywords_impl(
    *,
    domain_config: dict | None,
    context: dict | None = None,
    logger: Any,
    settings_obj: Any,
) -> list[str]:
    """Extract domain routing keywords from config or registry fallback."""
    domain_keywords: list[str] = []
    if domain_config and domain_config.get("routing_keywords"):
        for kw_group in domain_config["routing_keywords"]:
            domain_keywords.extend(
                keyword.strip().lower() for keyword in kw_group.split(",")
            )

    if not domain_keywords:
        try:
            from app.domains.registry import get_domain_registry

            registry = get_domain_registry()
            domain = registry.get(settings_obj.default_domain)
            if domain:
                config = domain.get_config()
                domain_keywords = [
                    keyword.lower() for keyword in (config.routing_keywords or [])
                ]
        except Exception as exc:
            logger.debug("Failed to load domain keywords: %s", exc)

    return domain_keywords


def validate_domain_routing_impl(
    *,
    query: str,
    chosen_agent: str,
    domain_config: dict | None,
    context: dict | None = None,
    rag_agent_name: str,
    tutor_agent_name: str,
    direct_agent_name: str,
    get_domain_keywords_fn: Any,
    logger: Any,
) -> str:
    """Ensure domain-routed turns still show a real domain signal."""
    if chosen_agent not in (rag_agent_name, tutor_agent_name):
        return chosen_agent

    if chosen_agent == tutor_agent_name and _looks_visual_followup_request_impl(query):
        logger.info(
            "[SUPERVISOR] Tutor visual follow-up keep: %s (do not demote short visual continuation to direct)",
            chosen_agent,
        )
        return chosen_agent

    from app.core.config import settings as runtime_settings

    if runtime_settings.enable_org_knowledge:
        from app.core.org_context import get_current_org_id

        if get_current_org_id():
            logger.info(
                "[SUPERVISOR] Org knowledge bypass: keeping %s (org context present, org_knowledge enabled)",
                chosen_agent,
            )
            return chosen_agent

    domain_keywords = get_domain_keywords_fn(domain_config)
    if not domain_keywords:
        return chosen_agent

    normalized_domain_keywords = [
        _normalize_router_text_impl(str(keyword or ""))
        for keyword in domain_keywords
        if str(keyword or "").strip()
    ]
    query_lower = _normalize_router_text_impl(query)
    has_domain = any(keyword in query_lower for keyword in domain_keywords)
    if not has_domain:
        context_parts: list[str] = []
        summary = str((context or {}).get("conversation_summary") or "").strip()
        if summary:
            context_parts.append(_normalize_router_text_impl(summary))

        for message in ((context or {}).get("langchain_messages") or [])[-6:]:
            content = getattr(message, "content", message)
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        text = block.get("text") or block.get("content") or ""
                        if text:
                            context_parts.append(_normalize_router_text_impl(str(text)))
                    elif block:
                        context_parts.append(_normalize_router_text_impl(str(block)))
            elif content:
                context_parts.append(_normalize_router_text_impl(str(content)))

        context_blob = "\n".join(context_parts)
        has_contextual_domain = any(
            keyword and keyword in context_blob for keyword in normalized_domain_keywords
        )
        has_learning_followup = (
            chosen_agent == tutor_agent_name
            and _looks_visual_followup_request_impl(query)
            and any(
                marker in context_blob
                for marker in (
                    "giai thich",
                    "nguoi hoc",
                    "quy tac",
                    "rule ",
                    "colregs",
                    "solas",
                    "marpol",
                    "cat huong",
                    "tranh va",
                    "nhuong duong",
                )
            )
        )
        if has_learning_followup:
            logger.info(
                "[SUPERVISOR] Learning visual follow-up keep: %s (recent learning context carries tutor continuity)",
                chosen_agent,
            )
            return chosen_agent
        if has_contextual_domain:
            logger.info(
                "[SUPERVISOR] Domain continuity keep: %s (recent context carries domain signal)",
                chosen_agent,
            )
            return chosen_agent
        logger.info(
            "[SUPERVISOR] Domain validation override: %s → direct (no domain keywords in query)",
            chosen_agent,
        )
        return direct_agent_name
    return chosen_agent


def is_complex_query_impl(
    *,
    query: str,
    routing_metadata: dict,
    min_length: int,
    mixed_intent_pairs: list[tuple[str, str]] | tuple[tuple[str, str], ...],
) -> bool:
    """Heuristic: does this query benefit from parallel dispatch?"""
    if len(query) < min_length:
        return False

    query_lower = query.lower()
    for lookup_kw, learning_kw in mixed_intent_pairs:
        if lookup_kw in query_lower and learning_kw in query_lower:
            return True

    confidence = routing_metadata.get("confidence", 1.0)
    return confidence < 0.75 and len(query) > 120


def conservative_fast_route_impl(
    *,
    query: str,
    normalize_router_text_fn: Any,
    classify_fast_chatter_turn_fn: Any,
    looks_clear_social_fn: Any,
    direct_agent_name: str,
) -> tuple[str, str, float, str] | None:
    """Route only the most obvious turns without invoking the supervisor LLM."""
    normalized = normalize_router_text_fn(query)

    fast_chatter = classify_fast_chatter_turn_fn(query)
    if fast_chatter is not None:
        intent, chatter_kind = fast_chatter
        reasoning = (
            "obvious social turn"
            if chatter_kind == "social"
            else f"obvious {chatter_kind.replace('_', ' ')} turn"
        )
        return (direct_agent_name, intent, 1.0, reasoning)

    if looks_clear_social_fn(normalized):
        return (direct_agent_name, "social", 1.0, "obvious social turn")

    return None


def rule_based_route_impl(
    *,
    query: str,
    domain_config: dict | None,
    normalize_router_text_fn: Any,
    is_obvious_social_turn_fn: Any,
    needs_code_studio_fn: Any,
    get_domain_keywords_fn: Any,
    looks_clear_learning_turn_fn: Any,
    personal_keywords: list[str] | tuple[str, ...],
    direct_agent_name: str,
    memory_agent_name: str,
    code_studio_agent_name: str,
    rag_agent_name: str,
    tutor_agent_name: str,
) -> str:
    """Minimal rule-based routing guardrail fallback."""
    query_lower = query.lower()
    normalized_query = normalize_router_text_fn(query)

    if is_obvious_social_turn_fn(query):
        return direct_agent_name

    if any(kw in query_lower for kw in personal_keywords):
        return memory_agent_name

    if needs_code_studio_fn(query):
        return code_studio_agent_name

    domain_keywords = get_domain_keywords_fn(domain_config)
    if any(kw in query_lower for kw in domain_keywords):
        return rag_agent_name

    if (
        looks_clear_learning_turn_fn(normalized_query)
        or any(
            marker in normalized_query
            for marker in (
                "phan tich",
                "toan hoc",
                "cong thuc",
                "nguyen ly",
                "co che",
                "ban chat",
                "chung minh",
                "vi sao",
                "tai sao",
            )
        )
    ):
        return tutor_agent_name

    return direct_agent_name
