"""Public convenience API for the shared LLM pool.

This keeps the heavyweight pool implementation focused on provider lifecycle
and routing internals while preserving the old import surface for callers.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from langchain_core.language_models import BaseChatModel

_PRIMARY_TIMEOUT: float = 12.0

TIMEOUT_PROFILE_STRUCTURED = "structured"
TIMEOUT_PROFILE_BACKGROUND = "background"


def _effort_to_tier(effort: Optional[str], default_tier):
    from app.engine import llm_pool as pool_mod

    mapping = {
        "low": pool_mod.ThinkingTier.LIGHT,
        "medium": pool_mod.ThinkingTier.MODERATE,
        "high": pool_mod.ThinkingTier.DEEP,
        "max": pool_mod.ThinkingTier.DEEP,
    }
    return mapping.get(effort or "", default_tier)


def get_llm_deep() -> BaseChatModel:
    from app.engine.llm_pool import LLMPool, ThinkingTier

    return LLMPool.get(ThinkingTier.DEEP)


def get_llm_moderate() -> BaseChatModel:
    from app.engine.llm_pool import LLMPool, ThinkingTier

    return LLMPool.get(ThinkingTier.MODERATE)


def get_llm_light() -> BaseChatModel:
    from app.engine.llm_pool import LLMPool, ThinkingTier

    return LLMPool.get(ThinkingTier.LIGHT)


def get_llm_for_effort(effort: Optional[str], default_tier=None) -> BaseChatModel:
    from app.engine.llm_pool import LLMPool, ThinkingTier

    resolved_default = default_tier or ThinkingTier.MODERATE
    if not effort:
        return LLMPool.get(resolved_default)
    return LLMPool.get(_effort_to_tier(effort, resolved_default))


def get_llm_for_provider(
    provider: Optional[str],
    effort: Optional[str] = None,
    default_tier=None,
    *,
    strict_pin: bool = False,
) -> BaseChatModel:
    from app.engine.llm_pool import (
        FAILOVER_MODE_AUTO,
        FAILOVER_MODE_PINNED,
        LLMPool,
        ThinkingTier,
    )

    resolved_default = default_tier or ThinkingTier.MODERATE
    tier = _effort_to_tier(effort, resolved_default) if effort else resolved_default

    normalized_provider = LLMPool._normalize_provider(provider)
    if normalized_provider and not strict_pin:
        provider_llm = LLMPool.get_provider_instance(
            normalized_provider,
            tier,
            allow_unavailable=True,
            requested_provider=None,
        )
        if provider_llm is not None:
            return provider_llm

    route = LLMPool.resolve_runtime_route(
        provider,
        tier,
        failover_mode=FAILOVER_MODE_PINNED if strict_pin else FAILOVER_MODE_AUTO,
    )
    return route.llm


def get_llm_fallback(tier: Optional[str] = "moderate") -> Optional[BaseChatModel]:
    from app.engine.llm_pool import LLMPool

    return LLMPool.get_fallback(tier)


def is_rate_limit_error(error: Exception) -> bool:
    from app.engine import llm_pool as pool_mod

    return pool_mod.is_rate_limit_error_impl(error)


def resolve_primary_timeout_seconds(
    *,
    tier: str = "moderate",
    timeout_profile: Optional[str] = None,
    provider: Optional[str] = None,
) -> float | None:
    from app.engine import llm_pool as pool_mod

    return pool_mod.resolve_primary_timeout_seconds_impl(
        tier=tier,
        timeout_profile=timeout_profile,
        provider=provider,
        settings_obj=pool_mod.settings,
        timeout_profile_by_name=pool_mod.TIMEOUT_PROFILE_BY_NAME,
        timeout_profile_settings=pool_mod.TIMEOUT_PROFILE_SETTINGS,
        loads_timeout_provider_overrides_fn=pool_mod.loads_timeout_provider_overrides,
        primary_timeout_default=_PRIMARY_TIMEOUT,
        pool_cls=pool_mod.LLMPool,
        timeout_profile_structured=TIMEOUT_PROFILE_STRUCTURED,
        timeout_profile_background=TIMEOUT_PROFILE_BACKGROUND,
    )


async def ainvoke_with_failover(
    llm,
    messages,
    *,
    tier: str = "moderate",
    provider: Optional[str] = None,
    failover_mode: str = "auto",
    prefer_selectable_fallback: bool = False,
    on_primary: Optional[Callable[[BaseChatModel], BaseChatModel]] = None,
    on_fallback: Optional[Callable[[BaseChatModel], BaseChatModel]] = None,
    on_switch: Optional[Callable[[str, str, str], Any]] = None,
    on_failover: Optional[Callable[[dict[str, Any]], Any]] = None,
    primary_timeout: Optional[float] = None,
    timeout_profile: Optional[str] = None,
):
    from app.engine import llm_pool as pool_mod

    return await pool_mod.ainvoke_with_failover_impl(
        llm,
        messages,
        tier=tier,
        provider=provider,
        failover_mode=failover_mode,
        prefer_selectable_fallback=prefer_selectable_fallback,
        on_primary=on_primary,
        on_fallback=on_fallback,
        on_switch=on_switch,
        on_failover=on_failover,
        primary_timeout=primary_timeout,
        timeout_profile=timeout_profile,
        pool_cls=pool_mod.LLMPool,
        resolve_primary_timeout_seconds_fn=resolve_primary_timeout_seconds,
        is_rate_limit_error_fn=is_rate_limit_error,
        is_failover_eligible_error_fn=pool_mod.is_failover_eligible_error_impl,
        logger_obj=pool_mod.logger,
        failover_mode_pinned=pool_mod.FAILOVER_MODE_PINNED,
        provider_unavailable_error_cls=pool_mod.ProviderUnavailableError,
    )
