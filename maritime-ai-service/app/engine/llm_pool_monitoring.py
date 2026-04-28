"""Monitoring and circuit-breaker helpers for LLMPool."""

from __future__ import annotations

from typing import Any, Optional


def get_request_selectable_providers_impl(
    *,
    providers: dict[str, Any],
    openrouter_legacy_slot: bool,
    get_request_provider_chain,
    ensure_provider,
) -> list[str]:
    """Return providers that should appear in request-level switchers."""
    selectable: list[str] = []

    for name in get_request_provider_chain():
        provider = ensure_provider(name)
        if provider is None or not provider.is_configured():
            continue
        if name == "openai" and openrouter_legacy_slot:
            continue
        if name not in selectable:
            selectable.append(name)

    return selectable


def get_stats_impl(
    *,
    initialized: bool,
    pool: dict[str, Any],
    fallback_pool: dict[str, Any],
    active_provider: Optional[str],
    fallback_provider: Optional[str],
    failover_enabled: bool,
    get_provider_chain,
    providers: dict[str, Any],
    get_request_selectable_providers,
    gemini_cb,
) -> dict[str, Any]:
    """Assemble LLM pool monitoring statistics."""
    stats: dict[str, Any] = {
        "initialized": initialized,
        "instance_count": len(pool),
        "fallback_count": len(fallback_pool),
        "tiers": list(pool.keys()),
        "active_provider": active_provider,
        "fallback_provider": fallback_provider,
        "failover_enabled": failover_enabled,
        "provider_chain": get_provider_chain(),
        "providers_registered": list(providers.keys()),
        "request_selectable_providers": (
            get_request_selectable_providers() if providers else []
        ),
    }

    circuit_breakers: dict[str, Any] = {}
    for name, provider in providers.items():
        cb = provider.get_circuit_breaker() if hasattr(provider, "get_circuit_breaker") else None
        if cb is not None:
            circuit_breakers[name] = cb.get_stats()
    if circuit_breakers:
        stats["circuit_breakers"] = circuit_breakers
    if gemini_cb is not None and "circuit_breakers" not in stats:
        stats["circuit_breaker"] = gemini_cb.get_stats()
    try:
        from app.engine.llm_model_health import get_model_health_snapshot

        model_health = get_model_health_snapshot()
        if model_health:
            stats["model_health"] = model_health
    except Exception:
        pass
    return stats


def is_available_impl(
    *,
    failover_enabled: bool,
    providers: dict[str, Any],
    gemini_cb,
) -> bool:
    """Check if any configured LLM provider is likely available."""
    if failover_enabled and providers:
        return any(provider.is_available() for provider in providers.values())
    if gemini_cb is None:
        return True
    return gemini_cb.is_available()


async def record_provider_success_impl(
    *,
    provider_name: Optional[str],
    active_provider: Optional[str],
    providers: dict[str, Any],
    normalize_provider,
    gemini_cb,
) -> None:
    """Record a successful call for one provider."""
    normalized = normalize_provider(provider_name) or active_provider
    if normalized and normalized in providers:
        provider = providers[normalized]
        if hasattr(provider, "record_success"):
            await provider.record_success()
            return
    if normalized in (None, "google") and gemini_cb is not None:
        await gemini_cb.record_success()


async def record_provider_failure_impl(
    *,
    provider_name: Optional[str],
    active_provider: Optional[str],
    providers: dict[str, Any],
    normalize_provider,
    gemini_cb,
) -> None:
    """Record a failed call for one provider."""
    normalized = normalize_provider(provider_name) or active_provider
    if normalized and normalized in providers:
        provider = providers[normalized]
        if hasattr(provider, "record_failure"):
            await provider.record_failure()
            return
    if normalized in (None, "google") and gemini_cb is not None:
        await gemini_cb.record_failure()


def get_circuit_breaker_for_provider_impl(
    *,
    provider_name: Optional[str],
    active_provider: Optional[str],
    normalize_provider,
    ensure_provider,
    gemini_cb,
):
    """Return the circuit breaker for one provider if present."""
    normalized = normalize_provider(provider_name) or active_provider
    if normalized:
        provider = ensure_provider(normalized)
        if provider is not None and hasattr(provider, "get_circuit_breaker"):
            return provider.get_circuit_breaker()
    if normalized in (None, "google"):
        return gemini_cb
    return None


def reset_pool_state_impl(
    *,
    pool: dict[str, Any],
    fallback_pool: dict[str, Any],
    provider_pools: dict[str, Any],
    providers: dict[str, Any],
) -> None:
    """Clear all shared LLMPool caches."""
    pool.clear()
    fallback_pool.clear()
    provider_pools.clear()
    providers.clear()
