"""Helpers for reporting the effective runtime LLM provider/model."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from app.core.config import settings
from app.engine.openai_compatible_credentials import (
    resolve_nvidia_model,
    resolve_openai_model,
    resolve_openrouter_model,
)


def _configured_model_for_provider(provider: str) -> str:
    """Return the configured model name for a provider."""
    normalized = (provider or "").strip().lower()
    if normalized == "google":
        return settings.google_model
    if normalized == "openai":
        return resolve_openai_model(settings)
    if normalized == "openrouter":
        return resolve_openrouter_model(settings)
    if normalized == "nvidia":
        return resolve_nvidia_model(settings)
    if normalized == "zhipu":
        return getattr(settings, "zhipu_model", "glm-5")
    if normalized == "ollama":
        return settings.ollama_model
    return settings.rag_model_version


def _normalize_provider(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if not normalized or normalized == "auto":
        return None
    return normalized


def _normalize_model(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_failover_text(value: Any, *, max_length: int = 220) -> str | None:
    if not isinstance(value, str):
        value = str(value or "")
    normalized = " ".join(value.split()).strip()
    if not normalized:
        return None
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 3].rstrip()}..."


def _normalize_failover_event(event: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(event, Mapping):
        return None

    from_provider = _normalize_provider(event.get("from_provider"))
    to_provider = _normalize_provider(event.get("to_provider"))
    reason_code = _normalize_failover_text(event.get("reason_code"), max_length=64)
    reason_category = _normalize_failover_text(
        event.get("reason_category") or reason_code,
        max_length=64,
    )
    if not from_provider and not to_provider and not reason_code:
        return None

    normalized: dict[str, Any] = {
        "from_provider": from_provider,
        "to_provider": to_provider,
        "reason_code": reason_code,
        "reason_category": reason_category,
    }
    reason_label = _normalize_failover_text(event.get("reason_label"))
    if reason_label:
        normalized["reason_label"] = reason_label
    raw_reason = _normalize_failover_text(event.get("raw_reason"))
    if raw_reason:
        normalized["raw_reason"] = raw_reason
    error_type = _normalize_failover_text(event.get("error_type"), max_length=80)
    if error_type:
        normalized["error_type"] = error_type
    detail = _normalize_failover_text(event.get("detail"))
    if detail:
        normalized["detail"] = detail
    timeout_seconds = event.get("timeout_seconds")
    if isinstance(timeout_seconds, (int, float)) and timeout_seconds > 0:
        normalized["timeout_seconds"] = float(timeout_seconds)
    return normalized


def record_runtime_failover_event(
    target: MutableMapping[str, Any] | None,
    event: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Append one normalized failover event to request/state metadata."""
    if not isinstance(target, MutableMapping):
        return None
    normalized = _normalize_failover_event(event)
    if not normalized:
        return None
    raw_events = target.get("_llm_failover_events")
    events: list[dict[str, Any]] = []
    if isinstance(raw_events, list):
        for item in raw_events:
            clean = _normalize_failover_event(item)
            if clean:
                events.append(clean)
    events.append(normalized)
    target["_llm_failover_events"] = events
    target["failover"] = resolve_runtime_failover_metadata(target)
    return normalized


def resolve_runtime_failover_metadata(
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return normalized failover metadata for one request/runtime result."""
    if not isinstance(metadata, Mapping):
        return None

    direct_failover = metadata.get("failover")
    raw_events = metadata.get("_llm_failover_events") or metadata.get("llm_failover_events")
    events: list[dict[str, Any]] = []
    if isinstance(raw_events, list):
        for item in raw_events:
            clean = _normalize_failover_event(item)
            if clean:
                events.append(clean)

    if isinstance(direct_failover, Mapping):
        direct_events = direct_failover.get("route")
        if not events and isinstance(direct_events, list):
            for item in direct_events:
                clean = _normalize_failover_event(item)
                if clean:
                    events.append(clean)

    if not events:
        return None

    last_event = events[-1]
    initial_provider = _normalize_provider(
        metadata.get("_requested_provider")
        or metadata.get("requested_provider")
        or metadata.get("provider")
        or events[0].get("from_provider")
    )
    final_provider = _normalize_provider(
        metadata.get("_execution_provider")
        or metadata.get("execution_provider")
        or metadata.get("provider")
        or last_event.get("to_provider")
    )
    return {
        "switched": True,
        "switch_count": len(events),
        "initial_provider": initial_provider,
        "final_provider": final_provider,
        "last_reason_code": last_event.get("reason_code"),
        "last_reason_category": last_event.get("reason_category"),
        "last_reason_label": last_event.get("reason_label"),
        "route": events,
    }


def get_active_runtime_provider(preferred_provider: str | None = None) -> str:
    """Resolve the active provider from metadata, pool state, or config."""
    provider = (preferred_provider or "").strip().lower()
    if provider:
        return provider

    try:
        from app.engine.llm_pool import LLMPool

        pool_provider = LLMPool.get_active_provider()
        if isinstance(pool_provider, str) and pool_provider.strip():
            return pool_provider.strip().lower()
    except Exception:
        pass

    configured = getattr(settings, "llm_provider", "google")
    if isinstance(configured, str) and configured.strip():
        return configured.strip().lower()
    return "google"


def resolve_runtime_llm_metadata(
    metadata: Mapping[str, Any] | None = None,
    *,
    allow_fallback: bool = True,
) -> dict[str, Any]:
    """Return normalized runtime provider/model metadata.

    `allow_fallback=False` is for user-facing metadata where we should only
    show a provider/model pair if this specific request actually recorded it.
    """
    raw_exec_provider = None
    raw_exec_model = None
    raw_provider = None
    raw_model = None
    runtime_authoritative = False

    if metadata:
        raw_exec_provider = (
            metadata.get("_execution_provider")
            or metadata.get("execution_provider")
        )
        raw_exec_model = (
            metadata.get("_execution_model")
            or metadata.get("execution_model")
        )
        raw_provider = (
            metadata.get("provider")
            or metadata.get("active_provider")
        )
        raw_model = (
            metadata.get("model")
            or metadata.get("model_name")
        )
        runtime_authoritative = bool(metadata.get("runtime_authoritative"))

    execution_provider = _normalize_provider(raw_exec_provider)
    execution_model = _normalize_model(raw_exec_model)
    direct_provider = _normalize_provider(raw_provider)
    direct_model = _normalize_model(raw_model)

    provider: str | None = None
    model: str | None = None
    authoritative = False

    if execution_provider and execution_model:
        provider = execution_provider
        model = execution_model
        authoritative = True
    elif execution_provider and direct_model:
        provider = execution_provider
        model = direct_model
        authoritative = True
    elif runtime_authoritative and direct_provider and direct_model:
        provider = direct_provider
        model = direct_model
        authoritative = True

    if not authoritative and allow_fallback:
        provider = get_active_runtime_provider(
            execution_provider or direct_provider or None
        )
        model = direct_model or execution_model or _configured_model_for_provider(provider)

    return {
        "provider": provider,
        "model": model,
        "runtime_authoritative": authoritative,
        "failover": resolve_runtime_failover_metadata(metadata),
    }
