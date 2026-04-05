"""Custom model helpers for LLMPool."""

from __future__ import annotations


def create_llm_with_model_for_provider_impl(
    *,
    provider_name: str,
    model_name: str,
    tier,
    pool,
    thinking_budgets,
    thinking_tier_cls,
    normalize_provider,
    ensure_provider,
    attach_tracking_callback,
    tag_runtime_metadata,
    logger_obj,
):
    normalized_provider = normalize_provider(provider_name)
    if not normalized_provider:
        return None

    cache_key = f"_custom_{normalized_provider}_{model_name}_{tier.value}"
    if cache_key in pool:
        return pool[cache_key]

    thinking_budget = thinking_budgets.get(tier.value, 4096)
    include_thoughts = tier in (
        thinking_tier_cls.DEEP,
        thinking_tier_cls.MODERATE,
    )

    try:
        provider = ensure_provider(normalized_provider)
        if provider is None or not provider.is_configured():
            return None

        llm = provider.create_instance(
            tier=tier.value,
            thinking_budget=thinking_budget,
            include_thoughts=include_thoughts,
            temperature=0.5,
            model_name=model_name,
        )
        attach_tracking_callback(llm, cache_key)
        llm = tag_runtime_metadata(
            llm,
            provider_name=normalized_provider,
            tier_key=tier.value,
            requested_provider=normalized_provider,
        )
        pool[cache_key] = llm
        logger_obj.info(
            "[LLM_POOL] Created custom model LLM: provider=%s model=%s tier=%s budget=%d",
            normalized_provider,
            model_name,
            tier.value,
            thinking_budget,
        )
        return llm
    except Exception as exc:
        logger_obj.warning(
            "[LLM_POOL] Custom model %s/%s failed: %s",
            normalized_provider,
            model_name,
            exc,
        )
        return None
