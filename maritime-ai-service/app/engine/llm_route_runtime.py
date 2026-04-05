"""Request-scoped route helpers for LLMPool."""

from __future__ import annotations

import logging
from typing import Optional


logger = logging.getLogger(__name__)


def get_fallback_for_provider_impl(
    *,
    provider_name: Optional[str],
    tier,
    failover_mode: str,
    prefer_selectable_only: bool,
    allowed_fallback_providers: set[str] | None,
    auto_mode: str,
    pinned_mode: str,
    fallback_provider: Optional[str],
    active_provider: Optional[str],
    thinking_tier,
    normalize_failover_mode,
    normalize_tier_key,
    normalize_provider,
    get_request_provider_chain,
    get_selectable_provider_names,
    get_provider_instance,
):
    """Return the next available provider/LLM for one request route."""
    if normalize_failover_mode(failover_mode) == pinned_mode:
        return None, None
    tier_key = normalize_tier_key(tier or thinking_tier.MODERATE)
    primary = normalize_provider(provider_name) or active_provider
    chain = get_request_provider_chain(primary)
    selectable_now = get_selectable_provider_names() if prefer_selectable_only else None

    seen_primary = primary is None
    for candidate in chain:
        normalized_candidate = normalize_provider(candidate)
        if not seen_primary:
            if candidate == primary:
                seen_primary = True
            continue
        if candidate == primary:
            continue
        if (
            allowed_fallback_providers is not None
            and normalized_candidate not in allowed_fallback_providers
        ):
            continue
        if selectable_now is not None and normalized_candidate not in selectable_now:
            continue
        fallback_llm = get_provider_instance(candidate, tier_key, allow_unavailable=False)
        if fallback_llm is not None:
            return candidate, fallback_llm

    if (
        provider_name is None
        and fallback_provider
        and (
            allowed_fallback_providers is None
            or normalize_provider(fallback_provider) in allowed_fallback_providers
        )
        and (selectable_now is None or normalize_provider(fallback_provider) in selectable_now)
    ):
        fallback_llm = get_provider_instance(fallback_provider, tier_key, allow_unavailable=False)
        if fallback_llm is not None:
            return fallback_provider, fallback_llm

    return None, None


def resolve_runtime_route_impl(
    *,
    provider_name: Optional[str],
    tier,
    failover_mode: str,
    prefer_selectable_fallback: bool,
    allowed_fallback_providers: set[str] | None,
    auto_mode: str,
    resolved_route_cls,
    provider_unavailable_error_cls,
    active_provider: Optional[str],
    normalize_tier_key,
    normalize_provider,
    normalize_failover_mode,
    get_provider_instance,
    get_fallback_for_provider,
    get_circuit_breaker_for_provider,
    resolve_auto_primary_provider,
    get_selectable_provider_names,
    get_default_llm,
    logger_obj=None,
):
    """Resolve a request-scoped primary/fallback route for failover helpers."""
    logger_ref = logger_obj or logger
    tier_key = normalize_tier_key(tier)
    primary = normalize_provider(provider_name)
    normalized_mode = normalize_failover_mode(failover_mode)

    if primary:
        primary_llm = get_provider_instance(
            primary,
            tier_key,
            allow_unavailable=True,
            requested_provider=primary,
        )
        if primary_llm is None:
            if normalized_mode == "pinned":
                raise provider_unavailable_error_cls(
                    provider=primary,
                    reason_code="busy",
                    message="Provider duoc chon hien khong san sang de xu ly yeu cau nay.",
                )
            logger_ref.warning(
                "[LLM_POOL] Requested provider %s unavailable, falling back to auto route",
                primary,
            )
            return resolve_runtime_route_impl(
                provider_name=None,
                tier=tier_key,
                failover_mode=auto_mode,
                prefer_selectable_fallback=prefer_selectable_fallback,
                auto_mode=auto_mode,
                resolved_route_cls=resolved_route_cls,
                provider_unavailable_error_cls=provider_unavailable_error_cls,
                active_provider=active_provider,
                normalize_tier_key=normalize_tier_key,
                normalize_provider=normalize_provider,
                normalize_failover_mode=normalize_failover_mode,
                get_provider_instance=get_provider_instance,
                get_fallback_for_provider=get_fallback_for_provider,
                get_circuit_breaker_for_provider=get_circuit_breaker_for_provider,
                resolve_auto_primary_provider=resolve_auto_primary_provider,
                get_selectable_provider_names=get_selectable_provider_names,
                get_default_llm=get_default_llm,
                allowed_fallback_providers=allowed_fallback_providers,
                logger_obj=logger_ref,
            )
        fallback_provider, fallback_llm = get_fallback_for_provider(
            primary,
            tier_key,
            failover_mode=normalized_mode,
            prefer_selectable_only=prefer_selectable_fallback,
            allowed_fallback_providers=allowed_fallback_providers,
        )
        return resolved_route_cls(
            provider=primary,
            llm=primary_llm,
            circuit_breaker=get_circuit_breaker_for_provider(primary),
            fallback_provider=fallback_provider,
            fallback_llm=fallback_llm,
        )

    auto_primary = resolve_auto_primary_provider()
    if auto_primary:
        auto_llm = get_provider_instance(
            auto_primary,
            tier_key,
            allow_unavailable=False,
        )
        if auto_llm is not None:
            fallback_provider, fallback_llm = get_fallback_for_provider(
                auto_primary,
                tier_key,
                failover_mode=normalized_mode,
                prefer_selectable_only=True,
                allowed_fallback_providers=allowed_fallback_providers,
            )
            return resolved_route_cls(
                provider=auto_primary,
                llm=auto_llm,
                circuit_breaker=get_circuit_breaker_for_provider(auto_primary),
                fallback_provider=fallback_provider,
                fallback_llm=fallback_llm,
            )

    selectable_names = get_selectable_provider_names()
    if selectable_names is not None:
        raise provider_unavailable_error_cls(
            provider="auto",
            reason_code="busy",
            message="Hien khong co provider nao dang san sang cho che do Tu dong.",
        )

    llm = get_default_llm(tier_key)
    resolved_active_provider = getattr(llm, "_wiii_provider_name", None) or active_provider
    fallback_provider, fallback_llm = get_fallback_for_provider(
        resolved_active_provider,
        tier_key,
        failover_mode=normalized_mode,
        allowed_fallback_providers=allowed_fallback_providers,
    )
    return resolved_route_cls(
        provider=resolved_active_provider,
        llm=llm,
        circuit_breaker=get_circuit_breaker_for_provider(resolved_active_provider),
        fallback_provider=fallback_provider,
        fallback_llm=fallback_llm,
    )
