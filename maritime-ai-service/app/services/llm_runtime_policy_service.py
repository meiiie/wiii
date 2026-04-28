"""
Persisted LLM runtime policy service.

This keeps admin runtime policy durable across backend restarts while still
preserving the existing architecture:
  env defaults -> persisted DB overrides -> runtime refresh/reset.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional

from app.core.config import settings
from app.engine.multi_agent.agent_runtime_profiles import (
    dumps_agent_runtime_profiles,
    sanitize_agent_runtime_profiles,
)
from app.engine.llm_timeout_policy import (
    dumps_timeout_provider_overrides,
    sanitize_timeout_provider_overrides,
)
from app.engine.llm_provider_registry import get_supported_provider_names, is_supported_provider
from app.repositories.admin_runtime_settings_repository import (
    get_admin_runtime_settings_repository,
)

logger = logging.getLogger(__name__)

LLM_RUNTIME_POLICY_KEY = "llm_runtime"
LLM_RUNTIME_POLICY_DESCRIPTION = "Persisted system-wide LLM runtime policy"
LLM_RUNTIME_POLICY_SCHEMA_VERSION = 6

_STRING_FIELDS = frozenset(
    {
        "embedding_model",
        "google_model",
        "openai_model",
        "openai_model_advanced",
        "openrouter_model",
        "openrouter_model_advanced",
        "nvidia_model",
        "nvidia_model_advanced",
        "zhipu_model",
        "zhipu_model_advanced",
        "ollama_model",
        "ollama_keep_alive",
        "openrouter_data_collection",
        "openrouter_provider_sort",
        "vision_describe_provider",
        "vision_ocr_provider",
        "vision_grounded_provider",
    }
)
_OPTIONAL_STRING_FIELDS = frozenset(
    {
        "google_api_key",
        "openai_api_key",
        "openrouter_api_key",
        "openai_base_url",
        "openrouter_base_url",
        "nvidia_api_key",
        "nvidia_base_url",
        "zhipu_api_key",
        "zhipu_base_url",
        "ollama_api_key",
        "ollama_base_url",
        "vision_describe_model",
        "vision_ocr_model",
        "vision_grounded_model",
    }
)
_LIST_FIELDS = frozenset(
    {
        "embedding_failover_chain",
        "vision_failover_chain",
        "openrouter_model_fallbacks",
        "openrouter_provider_order",
        "openrouter_allowed_providers",
        "openrouter_ignored_providers",
        "llm_failover_chain",
    }
)
_BOOL_FIELDS = frozenset({"use_multi_agent", "enable_llm_failover"})
_FLOAT_FIELDS = frozenset(
    {
        "vision_timeout_seconds",
        "llm_primary_timeout_light_seconds",
        "llm_primary_timeout_moderate_seconds",
        "llm_primary_timeout_deep_seconds",
        "llm_primary_timeout_structured_seconds",
        "llm_primary_timeout_background_seconds",
        "llm_stream_keepalive_interval_seconds",
        "llm_stream_idle_timeout_seconds",
    }
)
_INT_FIELDS = frozenset({"embedding_dimensions"})
_FLOAT_FIELD_LIMITS: dict[str, tuple[float, float]] = {
    "vision_timeout_seconds": (5.0, 120.0),
    "llm_primary_timeout_light_seconds": (0.0, 600.0),
    "llm_primary_timeout_moderate_seconds": (0.0, 900.0),
    "llm_primary_timeout_deep_seconds": (0.0, 1800.0),
    "llm_primary_timeout_structured_seconds": (0.0, 1800.0),
    "llm_primary_timeout_background_seconds": (0.0, 3600.0),
    "llm_stream_keepalive_interval_seconds": (1.0, 300.0),
    "llm_stream_idle_timeout_seconds": (0.0, 3600.0),
}
_INT_FIELD_LIMITS: dict[str, tuple[int, int]] = {
    "embedding_dimensions": (128, 4096),
}
_OPTIONAL_BOOL_FIELDS = frozenset(
    {
        "openrouter_allow_fallbacks",
        "openrouter_require_parameters",
        "openrouter_zdr",
    }
)
_ALL_POLICY_FIELDS = (
    "llm_provider",
    "embedding_provider",
    "vision_provider",
    "vision_describe_provider",
    "vision_describe_model",
    "vision_ocr_provider",
    "vision_ocr_model",
    "vision_grounded_provider",
    "vision_grounded_model",
    "use_multi_agent",
    "google_api_key",
    "google_model",
    "openai_api_key",
    "openrouter_api_key",
    "openai_base_url",
    "openrouter_base_url",
    "openai_model",
    "openai_model_advanced",
    "openrouter_model",
    "openrouter_model_advanced",
    "nvidia_api_key",
    "nvidia_base_url",
    "nvidia_model",
    "nvidia_model_advanced",
    "zhipu_api_key",
    "zhipu_base_url",
    "zhipu_model",
    "zhipu_model_advanced",
    "openrouter_model_fallbacks",
    "openrouter_provider_order",
    "openrouter_allowed_providers",
    "openrouter_ignored_providers",
    "openrouter_allow_fallbacks",
    "openrouter_require_parameters",
    "openrouter_data_collection",
    "openrouter_zdr",
    "openrouter_provider_sort",
    "ollama_api_key",
    "ollama_base_url",
    "ollama_model",
    "ollama_keep_alive",
    "embedding_model",
    "embedding_dimensions",
    "embedding_failover_chain",
    "vision_failover_chain",
    "vision_timeout_seconds",
    "llm_failover_chain",
    "enable_llm_failover",
    "llm_primary_timeout_light_seconds",
    "llm_primary_timeout_moderate_seconds",
    "llm_primary_timeout_deep_seconds",
    "llm_primary_timeout_structured_seconds",
    "llm_primary_timeout_background_seconds",
    "llm_stream_keepalive_interval_seconds",
    "llm_stream_idle_timeout_seconds",
)
_SECRET_FIELDS = frozenset(
    {
        "google_api_key",
        "openai_api_key",
        "openrouter_api_key",
        "nvidia_api_key",
        "zhipu_api_key",
        "ollama_api_key",
    }
)
_OPENROUTER_DATA_COLLECTION_VALUES = frozenset({"allow", "deny"})
_OPENROUTER_PROVIDER_SORT_VALUES = frozenset({"price", "latency", "throughput"})
_VISION_PROVIDER_FIELDS = frozenset(
    {
        "vision_describe_provider",
        "vision_ocr_provider",
        "vision_grounded_provider",
    }
)


@dataclass(frozen=True)
class LlmRuntimePolicyRecord:
    payload: dict[str, Any]
    updated_at: Optional[datetime]


def snapshot_current_llm_runtime_policy() -> dict[str, Any]:
    """Capture the current effective runtime policy from settings."""
    snapshot = {
        "schema_version": LLM_RUNTIME_POLICY_SCHEMA_VERSION,
    }
    for field_name in _ALL_POLICY_FIELDS:
        snapshot[field_name] = copy.deepcopy(getattr(settings, field_name))
    snapshot["agent_profiles"] = sanitize_agent_runtime_profiles(
        getattr(settings, "agent_runtime_profiles", "{}")
    )
    snapshot["timeout_provider_overrides"] = sanitize_timeout_provider_overrides(
        getattr(settings, "llm_timeout_provider_overrides", "{}")
    )
    return snapshot


def redact_llm_runtime_policy_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Return a safe audit-friendly view of a runtime policy snapshot."""
    redacted: dict[str, Any] = {}
    for key, value in snapshot.items():
        if key in _SECRET_FIELDS:
            redacted[key] = bool(value)
        else:
            redacted[key] = copy.deepcopy(value)
    return redacted


def _normalize_string_list(value: Any, *, provider_list: bool = False) -> Optional[list[str]]:
    if value is None:
        return None
    if not isinstance(value, list):
        return None

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            return None
        clean = item.strip()
        if not clean:
            continue
        if provider_list:
            clean = clean.lower()
            if not is_supported_provider(clean):
                logger.warning("Ignoring unsupported provider '%s' in persisted runtime policy", clean)
                continue
        if clean in seen:
            continue
        seen.add(clean)
        normalized.append(clean)
    return normalized


def sanitize_llm_runtime_policy_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """
    Keep only valid persisted runtime policy fields.

    Bad or stale DB values are ignored field-by-field so startup stays resilient.
    """
    clean: dict[str, Any] = {}
    if not isinstance(payload, Mapping):
        return clean

    provider_names = set(get_supported_provider_names())
    provider = payload.get("llm_provider")
    if isinstance(provider, str):
        provider = provider.strip().lower()
        if provider in provider_names:
            clean["llm_provider"] = provider
        elif provider:
            logger.warning("Ignoring unsupported persisted llm_provider '%s'", provider)

    embedding_provider = payload.get("embedding_provider")
    if isinstance(embedding_provider, str):
        embedding_provider = embedding_provider.strip().lower()
        if embedding_provider == "auto" or embedding_provider in provider_names:
            clean["embedding_provider"] = embedding_provider
        elif embedding_provider:
            logger.warning(
                "Ignoring unsupported persisted embedding_provider '%s'",
                embedding_provider,
            )

    vision_provider = payload.get("vision_provider")
    if isinstance(vision_provider, str):
        vision_provider = vision_provider.strip().lower()
        if vision_provider == "auto" or vision_provider in provider_names:
            clean["vision_provider"] = vision_provider
        elif vision_provider:
            logger.warning(
                "Ignoring unsupported persisted vision_provider '%s'",
                vision_provider,
            )

    for field_name in _STRING_FIELDS:
        if field_name not in payload:
            continue
        value = payload.get(field_name)
        if not isinstance(value, str):
            continue
        normalized = value.strip()
        if not normalized:
            continue
        if (
            field_name == "openrouter_data_collection"
            and normalized.lower() not in _OPENROUTER_DATA_COLLECTION_VALUES
        ):
            logger.warning("Ignoring invalid openrouter_data_collection '%s'", normalized)
            continue
        if (
            field_name == "openrouter_provider_sort"
            and normalized.lower() not in _OPENROUTER_PROVIDER_SORT_VALUES
        ):
            logger.warning("Ignoring invalid openrouter_provider_sort '%s'", normalized)
            continue
        if field_name in _VISION_PROVIDER_FIELDS:
            lowered = normalized.lower()
            if lowered != "auto" and lowered not in provider_names:
                logger.warning("Ignoring unsupported persisted %s '%s'", field_name, normalized)
                continue
            clean[field_name] = lowered
            continue
        clean[field_name] = normalized.lower() if field_name in {"openrouter_data_collection", "openrouter_provider_sort"} else normalized

    for field_name in _OPTIONAL_STRING_FIELDS:
        if field_name not in payload:
            continue
        value = payload.get(field_name)
        if value is None:
            clean[field_name] = None
            continue
        if not isinstance(value, str):
            continue
        normalized = value.strip()
        clean[field_name] = normalized or None

    for field_name in _LIST_FIELDS:
        if field_name not in payload:
            continue
        normalized = _normalize_string_list(
            payload.get(field_name),
            provider_list=field_name
            in {"llm_failover_chain", "embedding_failover_chain", "vision_failover_chain"},
        )
        if normalized is None:
            continue
        if field_name in {"llm_failover_chain", "embedding_failover_chain", "vision_failover_chain"} and not normalized:
            logger.warning("Ignoring empty persisted %s", field_name)
            continue
        clean[field_name] = normalized

    for field_name in _BOOL_FIELDS:
        if field_name in payload and isinstance(payload.get(field_name), bool):
            clean[field_name] = payload.get(field_name)

    for field_name in _FLOAT_FIELDS:
        if field_name not in payload:
            continue
        value = payload.get(field_name)
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        bounds = _FLOAT_FIELD_LIMITS[field_name]
        if numeric < bounds[0] or numeric > bounds[1]:
            logger.warning("Ignoring invalid persisted %s=%r", field_name, value)
            continue
        clean[field_name] = numeric

    for field_name in _INT_FIELDS:
        if field_name not in payload:
            continue
        value = payload.get(field_name)
        if isinstance(value, bool):
            continue
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            continue
        if numeric != value and not (
            isinstance(value, float) and value.is_integer()
        ):
            continue
        bounds = _INT_FIELD_LIMITS[field_name]
        if numeric < bounds[0] or numeric > bounds[1]:
            logger.warning("Ignoring invalid persisted %s=%r", field_name, value)
            continue
        clean[field_name] = numeric

    for field_name in _OPTIONAL_BOOL_FIELDS:
        if field_name not in payload:
            continue
        value = payload.get(field_name)
        if value is None or isinstance(value, bool):
            clean[field_name] = value

    if "agent_profiles" in payload:
        clean["agent_profiles"] = sanitize_agent_runtime_profiles(payload.get("agent_profiles"))
    if "timeout_provider_overrides" in payload:
        clean["timeout_provider_overrides"] = sanitize_timeout_provider_overrides(
            payload.get("timeout_provider_overrides")
        )

    return clean


def apply_llm_runtime_policy_snapshot(
    snapshot: Mapping[str, Any],
    *,
    preserve_existing_secrets: bool = False,
) -> dict[str, Any]:
    """Apply a sanitized runtime policy snapshot to the live settings object."""
    clean = sanitize_llm_runtime_policy_payload(snapshot)
    if not clean:
        return {}

    applied: dict[str, Any] = {}
    for field_name, value in clean.items():
        if preserve_existing_secrets and field_name in _SECRET_FIELDS:
            current_value = getattr(settings, field_name, None)
            if current_value:
                logger.info(
                    "Preserving existing runtime secret for %s during persisted restore",
                    field_name,
                )
                continue
        if field_name == "agent_profiles":
            settings.agent_runtime_profiles = dumps_agent_runtime_profiles(value)
            applied[field_name] = copy.deepcopy(value)
            continue
        if field_name == "timeout_provider_overrides":
            settings.llm_timeout_provider_overrides = dumps_timeout_provider_overrides(value)
            applied[field_name] = copy.deepcopy(value)
            continue
        setattr(settings, field_name, copy.deepcopy(value))
        applied[field_name] = copy.deepcopy(value)
    settings.refresh_nested_views()
    return applied


def get_persisted_llm_runtime_policy() -> Optional[LlmRuntimePolicyRecord]:
    repo = get_admin_runtime_settings_repository()
    record = repo.get_settings(LLM_RUNTIME_POLICY_KEY)
    if record is None:
        return None

    clean = sanitize_llm_runtime_policy_payload(record.settings)
    return LlmRuntimePolicyRecord(payload=clean, updated_at=record.updated_at)


def persist_current_llm_runtime_policy() -> Optional[LlmRuntimePolicyRecord]:
    repo = get_admin_runtime_settings_repository()
    record = repo.upsert_settings(
        LLM_RUNTIME_POLICY_KEY,
        snapshot_current_llm_runtime_policy(),
        description=LLM_RUNTIME_POLICY_DESCRIPTION,
    )
    if record is None:
        return None
    clean = sanitize_llm_runtime_policy_payload(record.settings)
    return LlmRuntimePolicyRecord(payload=clean, updated_at=record.updated_at)


def delete_persisted_llm_runtime_policy() -> bool:
    repo = get_admin_runtime_settings_repository()
    return repo.delete_settings(LLM_RUNTIME_POLICY_KEY)


def apply_persisted_llm_runtime_policy() -> Optional[LlmRuntimePolicyRecord]:
    record = get_persisted_llm_runtime_policy()
    if record is None or not record.payload:
        return record

    applied = apply_llm_runtime_policy_snapshot(
        record.payload,
        preserve_existing_secrets=True,
    )
    if applied:
        logger.info(
            "Applied persisted LLM runtime policy (%d field(s))",
            len(applied),
        )
    return record
