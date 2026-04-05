"""Helpers for OpenRouter-specific request routing options.

These helpers keep OpenRouter request shaping in one place so LangChain-based
and direct ChatOpenAI call sites stay consistent.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from app.engine.openai_compatible_credentials import (
    is_openrouter_legacy_slot_configured,
    openrouter_credentials_available,
)

_OPENROUTER_HOST_MARKER = "openrouter.ai"


def is_openrouter_base_url(base_url: Optional[str]) -> bool:
    """Return True when the configured OpenAI-compatible URL points to OpenRouter."""
    if not base_url:
        return False
    return _OPENROUTER_HOST_MARKER in base_url.lower()


def _dedupe_items(items: Iterable[str], *, primary: Optional[str] = None) -> list[str]:
    """Normalize list values while preserving order."""
    normalized: list[str] = []
    seen = {primary} if primary else set()

    for item in items:
        value = item.strip()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)

    return normalized


def build_openrouter_extra_body(settings: Any, *, primary_model: Optional[str] = None) -> dict[str, Any]:
    """Build the OpenRouter-only request body extensions for ChatOpenAI.

    Uses the documented OpenRouter request fields:
    - ``models`` for model fallback order
    - ``provider`` for provider selection and routing preferences
    """
    if not (
        openrouter_credentials_available(settings)
        or is_openrouter_legacy_slot_configured(settings)
        or str(getattr(settings, "llm_provider", "") or "").strip().lower() == "openrouter"
    ):
        return {}

    extra_body: dict[str, Any] = {}

    models = _dedupe_items(
        getattr(settings, "openrouter_model_fallbacks", []),
        primary=primary_model,
    )
    if models:
        extra_body["models"] = models

    provider: dict[str, Any] = {}

    order = _dedupe_items(getattr(settings, "openrouter_provider_order", []))
    if order:
        provider["order"] = order

    allowed = _dedupe_items(getattr(settings, "openrouter_allowed_providers", []))
    if allowed:
        provider["only"] = allowed

    ignored = _dedupe_items(getattr(settings, "openrouter_ignored_providers", []))
    if ignored:
        provider["ignore"] = ignored

    allow_fallbacks = getattr(settings, "openrouter_allow_fallbacks", None)
    if allow_fallbacks is not None:
        provider["allow_fallbacks"] = bool(allow_fallbacks)

    require_parameters = getattr(settings, "openrouter_require_parameters", None)
    if require_parameters is not None:
        provider["require_parameters"] = bool(require_parameters)

    data_collection = getattr(settings, "openrouter_data_collection", None)
    if data_collection:
        provider["data_collection"] = data_collection

    zdr = getattr(settings, "openrouter_zdr", None)
    if zdr is not None:
        provider["zdr"] = bool(zdr)

    sort = getattr(settings, "openrouter_provider_sort", None)
    if sort:
        provider["sort"] = sort

    if provider:
        extra_body["provider"] = provider

    return extra_body
