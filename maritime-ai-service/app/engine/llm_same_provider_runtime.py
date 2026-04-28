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
    is_model_degraded_fn=None,
) -> dict[str, str] | None:
    """Resolve a safe same-provider model fallback plan."""
    provider = normalize_provider(provider_name)
    if not provider:
        return None

    if provider == "google":
        if tier_key != thinking_tier_cls.DEEP.value:
            return None
        advanced = getattr(settings_obj, "google_model_advanced", None)
        base = getattr(settings_obj, "google_model", None)
    elif provider == "openai":
        if tier_key != thinking_tier_cls.DEEP.value:
            return None
        advanced = getattr(settings_obj, "openai_model_advanced", None)
        base = getattr(settings_obj, "openai_model", None)
    elif provider == "openrouter":
        if tier_key != thinking_tier_cls.DEEP.value:
            return None
        advanced = getattr(settings_obj, "openrouter_model_advanced", None)
        base = getattr(settings_obj, "openrouter_model", None)
    elif provider == "nvidia":
        advanced = getattr(settings_obj, "nvidia_model_advanced", None)
        base = getattr(settings_obj, "nvidia_model", None)
    elif provider == "zhipu":
        if tier_key != thinking_tier_cls.DEEP.value:
            return None
        advanced = getattr(settings_obj, "zhipu_model_advanced", None)
        base = getattr(settings_obj, "zhipu_model", None)
    else:
        return None

    advanced = str(advanced or "").strip() or None
    base = str(base or "").strip() or None
    current = str(current_model_name or "").strip() or None

    if not advanced or not base or advanced == base:
        return None

    if provider == "nvidia":
        if current == base or (current is None and tier_key != thinking_tier_cls.DEEP.value):
            from_model = base
            to_model = advanced
            from_tier = tier_key
            to_tier = thinking_tier_cls.DEEP.value
        elif current == advanced or (current is None and tier_key == thinking_tier_cls.DEEP.value):
            from_model = advanced
            to_model = base
            from_tier = thinking_tier_cls.DEEP.value
            to_tier = thinking_tier_cls.MODERATE.value
        else:
            return None
    else:
        if current == base:
            return None
        if current is not None and current != advanced:
            return None
        from_model = advanced
        to_model = base
        from_tier = thinking_tier_cls.DEEP.value
        to_tier = thinking_tier_cls.MODERATE.value

    if is_model_degraded_fn is not None and is_model_degraded_fn(provider, to_model):
        return None

    return {
        "provider": provider,
        "from_model": from_model,
        "to_model": to_model,
        "from_tier": from_tier,
        "to_tier": to_tier,
    }
