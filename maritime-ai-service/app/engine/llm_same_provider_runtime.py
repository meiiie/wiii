"""Same-provider model fallback helpers for LLMPool."""

from __future__ import annotations

from typing import Any, Optional


def extract_runtime_model_name_impl(llm: Any) -> str | None:
    """Best-effort model name extraction from provider/chat model wrappers."""
    for attr in ("_wiii_model_name", "model_name", "model"):
        value = getattr(llm, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def resolve_same_provider_model_fallback_impl(
    *,
    provider_name: Optional[str],
    tier_key: str,
    current_model_name: Optional[str],
    settings_obj,
    thinking_tier_cls,
    normalize_provider,
) -> dict[str, str] | None:
    """Resolve a lower-latency same-provider model fallback plan.

    V1 keeps this intentionally conservative:
    - only applies to `deep` turns
    - only when provider exposes distinct `advanced` and base models
    - returns a moderate-tier fallback to bias for lower latency
    """
    provider = normalize_provider(provider_name)
    if not provider or tier_key != thinking_tier_cls.DEEP.value:
        return None

    if provider == "google":
        advanced = getattr(settings_obj, "google_model_advanced", None)
        base = getattr(settings_obj, "google_model", None)
    elif provider in {"openai", "openrouter"}:
        advanced = getattr(settings_obj, "openai_model_advanced", None)
        base = getattr(settings_obj, "openai_model", None)
    elif provider == "zhipu":
        advanced = getattr(settings_obj, "zhipu_model_advanced", None)
        base = getattr(settings_obj, "zhipu_model", None)
    else:
        return None

    advanced = str(advanced or "").strip() or None
    base = str(base or "").strip() or None
    current = str(current_model_name or "").strip() or None

    if not advanced or not base or advanced == base:
        return None
    if current == base:
        return None
    if current is not None and current != advanced:
        return None

    return {
        "provider": provider,
        "from_model": advanced,
        "to_model": base,
        "from_tier": thinking_tier_cls.DEEP.value,
        "to_tier": thinking_tier_cls.MODERATE.value,
    }
