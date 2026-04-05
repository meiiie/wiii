"""
Helpers for persisted LLM timeout policy.

This module keeps timeout policy serialization/sanitization in one place so
admin/runtime policy, LLMPool resolution, and UI contracts stay aligned.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Mapping

from app.engine.llm_provider_registry import get_supported_provider_names

logger = logging.getLogger(__name__)

TIMEOUT_PROFILE_SETTINGS: dict[str, str] = {
    "light_seconds": "llm_primary_timeout_light_seconds",
    "moderate_seconds": "llm_primary_timeout_moderate_seconds",
    "deep_seconds": "llm_primary_timeout_deep_seconds",
    "structured_seconds": "llm_primary_timeout_structured_seconds",
    "background_seconds": "llm_primary_timeout_background_seconds",
}

STREAM_TIMEOUT_SETTINGS: dict[str, str] = {
    "stream_keepalive_interval_seconds": "llm_stream_keepalive_interval_seconds",
    "stream_idle_timeout_seconds": "llm_stream_idle_timeout_seconds",
}

TIMEOUT_PROFILE_BY_NAME: dict[str, str] = {
    "light": "light_seconds",
    "moderate": "moderate_seconds",
    "deep": "deep_seconds",
    "structured": "structured_seconds",
    "background": "background_seconds",
}

TIMEOUT_SETTING_LIMITS: dict[str, tuple[float, float]] = {
    "llm_primary_timeout_light_seconds": (0.0, 600.0),
    "llm_primary_timeout_moderate_seconds": (0.0, 900.0),
    "llm_primary_timeout_deep_seconds": (0.0, 1800.0),
    "llm_primary_timeout_structured_seconds": (0.0, 1800.0),
    "llm_primary_timeout_background_seconds": (0.0, 3600.0),
    "llm_stream_keepalive_interval_seconds": (1.0, 300.0),
    "llm_stream_idle_timeout_seconds": (0.0, 3600.0),
}


def _coerce_float(
    value: Any,
    *,
    field_name: str,
) -> float | None:
    bounds = TIMEOUT_SETTING_LIMITS[field_name]
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric < bounds[0] or numeric > bounds[1]:
        logger.warning(
            "Ignoring out-of-range timeout policy value for %s: %r",
            field_name,
            value,
        )
        return None
    return numeric


def build_timeout_profiles_snapshot(source: Any) -> dict[str, float]:
    """Read global timeout profile values from settings-like objects."""
    snapshot: dict[str, float] = {}
    for public_name, attr_name in TIMEOUT_PROFILE_SETTINGS.items():
        snapshot[public_name] = float(getattr(source, attr_name))
    for public_name, attr_name in STREAM_TIMEOUT_SETTINGS.items():
        snapshot[public_name] = float(getattr(source, attr_name))
    return snapshot


def sanitize_timeout_provider_overrides(
    value: Any,
) -> dict[str, dict[str, float]]:
    """Keep only supported provider timeout overrides."""
    payload = value
    if isinstance(payload, str):
        raw = payload.strip()
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Ignoring invalid llm_timeout_provider_overrides JSON")
            return {}

    if not isinstance(payload, Mapping):
        return {}

    supported_providers = set(get_supported_provider_names())
    clean: dict[str, dict[str, float]] = {}
    for provider_name, provider_overrides in payload.items():
        if not isinstance(provider_name, str):
            continue
        normalized_provider = provider_name.strip().lower()
        if normalized_provider not in supported_providers:
            logger.warning(
                "Ignoring unsupported provider in timeout overrides: %s",
                provider_name,
            )
            continue
        if not isinstance(provider_overrides, Mapping):
            continue

        normalized_overrides: dict[str, float] = {}
        for public_name, raw_value in provider_overrides.items():
            if public_name not in TIMEOUT_PROFILE_SETTINGS:
                continue
            numeric = _coerce_float(
                raw_value,
                field_name=TIMEOUT_PROFILE_SETTINGS[public_name],
            )
            if numeric is None:
                continue
            normalized_overrides[public_name] = numeric

        if normalized_overrides:
            clean[normalized_provider] = normalized_overrides

    return clean


def dumps_timeout_provider_overrides(value: Any) -> str:
    return json.dumps(
        sanitize_timeout_provider_overrides(value),
        ensure_ascii=True,
        sort_keys=True,
    )


def loads_timeout_provider_overrides(value: Any) -> dict[str, dict[str, float]]:
    return sanitize_timeout_provider_overrides(value)
