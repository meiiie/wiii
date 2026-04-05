"""Legacy creation helpers extracted from llm_pool.py."""

from __future__ import annotations

from typing import Any


def attach_tracking_callback_impl(
    *,
    llm: Any,
    tier_key: str,
    logger_obj: Any,
) -> None:
    """Attach token tracking callback to an LLM instance."""
    try:
        from app.core.token_tracker import TokenTrackingCallback

        callback = TokenTrackingCallback(tier=tier_key)
        if hasattr(llm, "callbacks") and llm.callbacks is not None:
            llm.callbacks.append(callback)
        else:
            llm.callbacks = [callback]
    except Exception as exc:
        logger_obj.debug("[LLM_POOL] Token tracking callback not attached: %s", exc)


def create_instance_legacy_impl(
    *,
    cls_ref,
    tier_key: str,
    thinking_budget: int,
    include_thoughts: bool,
    settings_obj: Any,
    create_provider_fn,
    logger_obj: Any,
    attach_tracking_callback_fn,
):
    """Legacy single-provider creation path for Google."""
    if getattr(settings_obj, "enable_unified_providers", False):
        provider = create_provider_fn("google")
        try:
            llm = provider.create_instance(
                tier=tier_key,
                thinking_budget=thinking_budget,
                include_thoughts=include_thoughts,
                temperature=0.5,
            )
            attach_tracking_callback_fn(llm, tier_key)
            llm = cls_ref._tag_runtime_metadata(
                llm,
                provider_name="google",
                tier_key=tier_key,
            )
            cls_ref._pool[tier_key] = llm
            cls_ref._provider_pools.setdefault("google", {})[tier_key] = llm
            cls_ref._active_provider = "google"
            logger_obj.info(
                "[LLM_POOL] Created %s instance [unified] (budget=%d, thoughts=%s)",
                tier_key.upper(),
                thinking_budget,
                include_thoughts,
            )
            return llm
        except Exception as exc:
            logger_obj.error(
                "[LLM_POOL] Failed to create %s instance [unified]: %s",
                tier_key,
                exc,
            )
            raise

    from langchain_google_genai import ChatGoogleGenerativeAI

    llm_kwargs = {
        "model": settings_obj.google_model,
        "google_api_key": settings_obj.google_api_key,
        "temperature": 0.5,
    }

    if settings_obj.thinking_enabled and thinking_budget > 0:
        llm_kwargs["thinking_budget"] = thinking_budget
        if include_thoughts:
            llm_kwargs["include_thoughts"] = True

    try:
        llm = ChatGoogleGenerativeAI(**llm_kwargs)
        attach_tracking_callback_fn(llm, tier_key)
        llm = cls_ref._tag_runtime_metadata(
            llm,
            provider_name="google",
            tier_key=tier_key,
        )
        cls_ref._pool[tier_key] = llm
        cls_ref._provider_pools.setdefault("google", {})[tier_key] = llm
        cls_ref._active_provider = "google"
        logger_obj.info(
            "[LLM_POOL] Created %s instance [legacy] (budget=%d, thoughts=%s)",
            tier_key.upper(),
            thinking_budget,
            include_thoughts,
        )
        return llm
    except Exception as exc:
        logger_obj.error("[LLM_POOL] Failed to create %s instance: %s", tier_key, exc)
        raise
