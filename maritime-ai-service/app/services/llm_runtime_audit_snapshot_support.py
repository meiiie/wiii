"""Snapshot shaping helpers for persisted LLM runtime audit state."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from app.engine.openai_compatible_credentials import (
    resolve_nvidia_model,
    resolve_nvidia_model_advanced,
    resolve_openrouter_model,
    resolve_openrouter_model_advanced,
)


def get_selected_models_impl(
    *,
    settings_obj: Any,
    resolve_openai_catalog_provider_fn: Callable[..., str],
    google_default_model: str,
    openai_default_model: str,
    openai_default_model_advanced: str,
    zhipu_default_model: str,
    zhipu_default_model_advanced: str,
) -> dict[str, dict[str, str | None]]:
    openai_catalog_provider = resolve_openai_catalog_provider_fn(
        active_provider=settings_obj.llm_provider,
        openai_base_url=settings_obj.openai_base_url,
    )
    openai_model = settings_obj.openai_model or openai_default_model
    openai_model_advanced = (
        settings_obj.openai_model_advanced or openai_default_model_advanced
    )
    return {
        "google": {
            "model": settings_obj.google_model or google_default_model,
            "advanced": None,
        },
        "openai": {
            "model": openai_model,
            "advanced": openai_model_advanced,
        },
        "openrouter": {
            "model": resolve_openrouter_model(settings_obj),
            "advanced": resolve_openrouter_model_advanced(settings_obj),
        },
        "nvidia": {
            "model": resolve_nvidia_model(settings_obj),
            "advanced": resolve_nvidia_model_advanced(settings_obj),
        },
        "zhipu": {
            "model": getattr(settings_obj, "zhipu_model", zhipu_default_model),
            "advanced": getattr(
                settings_obj,
                "zhipu_model_advanced",
                zhipu_default_model_advanced,
            ),
        },
        "ollama": {
            "model": settings_obj.ollama_model,
            "advanced": None,
        },
        "_shared_openai_slot": {
            "model": openai_catalog_provider,
            "advanced": None,
        },
    }


def lookup_selected_model_metadata_impl(
    *,
    catalog: Mapping[str, Any],
    provider: str,
    model_name: str | None,
    get_provider_chat_model_metadata_fn: Callable[[str, str | None], Any],
) -> Any:
    providers = catalog.get("providers")
    if isinstance(providers, Mapping):
        provider_models = providers.get(provider)
        if isinstance(provider_models, Mapping) and model_name:
            metadata = provider_models.get(model_name)
            if metadata is not None:
                return metadata
    return get_provider_chat_model_metadata_fn(provider, model_name)


def apply_metadata_hints_impl(
    *,
    state: dict[str, Any],
    metadata: Any,
) -> None:
    if metadata is None:
        return

    capability_source = getattr(metadata, "capability_source", None) or "static"
    if (
        state.get("tool_calling_source") != "live_probe"
        and getattr(metadata, "supports_tool_calling", None) is not None
    ):
        state["tool_calling_supported"] = metadata.supports_tool_calling
        state["tool_calling_source"] = capability_source
    if (
        state.get("structured_output_source") != "live_probe"
        and getattr(metadata, "supports_structured_output", None) is not None
    ):
        state["structured_output_supported"] = metadata.supports_structured_output
        state["structured_output_source"] = capability_source
    if (
        state.get("streaming_source") != "live_probe"
        and getattr(metadata, "supports_streaming", None) is not None
    ):
        state["streaming_supported"] = metadata.supports_streaming
        state["streaming_source"] = capability_source
    if (
        state.get("context_window_source") != "live_probe"
        and getattr(metadata, "context_window_tokens", None) is not None
    ):
        state["context_window_tokens"] = metadata.context_window_tokens
        state["context_window_source"] = capability_source
    if (
        state.get("max_output_source") != "live_probe"
        and getattr(metadata, "max_output_tokens", None) is not None
    ):
        state["max_output_tokens"] = metadata.max_output_tokens
        state["max_output_source"] = capability_source


def refresh_degraded_state_impl(
    *,
    provider: str,
    state: dict[str, Any],
    expected_capabilities: Mapping[str, dict[str, bool]],
) -> None:
    reasons: list[str] = []
    if state.get("runtime_discovery_enabled") and not state.get(
        "runtime_discovery_succeeded"
    ):
        reasons.append("Runtime discovery that current provider slot failed.")
    if state.get("last_live_probe_error"):
        reasons.append("Live capability probe failed.")

    expected = expected_capabilities.get(provider, {})
    if state.get("last_live_probe_attempt_at"):
        if (
            expected.get("tool_calling")
            and state.get("tool_calling_source") == "live_probe"
            and state.get("tool_calling_supported") is False
        ):
            reasons.append("Tool calling probe returned false.")
        if (
            expected.get("structured_output")
            and state.get("structured_output_source") == "live_probe"
            and state.get("structured_output_supported") is False
        ):
            reasons.append("Structured output probe returned false.")
        if (
            expected.get("streaming")
            and state.get("streaming_source") == "live_probe"
            and state.get("streaming_supported") is False
        ):
            reasons.append("Streaming probe returned false.")

    deduped: list[str] = []
    for reason in reasons:
        if reason not in deduped:
            deduped.append(reason)
    state["degraded"] = bool(deduped)
    state["degraded_reasons"] = deduped


def record_runtime_discovery_snapshot_impl(
    *,
    catalog: Mapping[str, Any],
    get_current_audit_payload_fn: Callable[[], dict[str, Any]],
    get_selected_models_fn: Callable[[], dict[str, dict[str, str | None]]],
    supported_provider_names: list[str],
    default_provider_state_fn: Callable[[str], dict[str, Any]],
    lookup_selected_model_metadata_fn: Callable[[Mapping[str, Any], str, str | None], Any],
    apply_metadata_hints_fn: Callable[[dict[str, Any], Any], None],
    refresh_degraded_state_fn: Callable[[str, dict[str, Any]], None],
    iso_fn: Callable[[Any], str | None],
    utcnow_fn: Callable[[], Any],
    persist_snapshot_fn: Callable[[Mapping[str, Any]], Any],
) -> Any:
    payload = get_current_audit_payload_fn()
    selected_models = get_selected_models_fn()
    provider_metadata = catalog.get("provider_metadata", {})
    now_iso = iso_fn(utcnow_fn())

    for provider in supported_provider_names:
        state = payload["providers"].setdefault(
            provider,
            default_provider_state_fn(provider),
        )
        selected = selected_models.get(provider, {})
        state["selected_model"] = selected.get("model")
        state["selected_model_advanced"] = selected.get("advanced")
        state["probe_model"] = selected.get("model")

        provider_catalog = catalog.get("providers", {}).get(provider, {})
        if isinstance(provider_catalog, Mapping):
            state["selected_model_in_catalog"] = bool(
                selected.get("model") and selected.get("model") in provider_catalog
            )
            state["selected_model_advanced_in_catalog"] = bool(
                selected.get("advanced")
                and selected.get("advanced") in provider_catalog
            )
        else:
            state["selected_model_in_catalog"] = False
            state["selected_model_advanced_in_catalog"] = False

        meta = (
            provider_metadata.get(provider, {})
            if isinstance(provider_metadata, Mapping)
            else {}
        )
        state["catalog_source"] = str(
            meta.get("catalog_source") or state.get("catalog_source") or "static"
        )
        state["model_count"] = (
            int(meta.get("model_count"))
            if isinstance(meta, Mapping) and "model_count" in meta
            else int(state.get("model_count") or 0)
        )
        state["discovered_model_count"] = (
            int(meta.get("discovered_model_count"))
            if isinstance(meta, Mapping) and "discovered_model_count" in meta
            else int(state.get("discovered_model_count") or 0)
        )
        state["runtime_discovery_enabled"] = bool(
            meta.get("runtime_discovery_enabled", False)
        )
        state["runtime_discovery_succeeded"] = bool(
            meta.get("runtime_discovery_succeeded", False)
        )

        if state["runtime_discovery_enabled"]:
            state["last_discovery_attempt_at"] = now_iso
            if state["runtime_discovery_succeeded"]:
                state["last_discovery_success_at"] = now_iso
                state["last_discovery_error"] = None
            else:
                state["last_discovery_error"] = (
                    "Runtime discovery failed for the current credentials or endpoint."
                )

        metadata = lookup_selected_model_metadata_fn(
            catalog,
            provider,
            selected.get("model"),
        )
        apply_metadata_hints_fn(state, metadata)
        refresh_degraded_state_fn(provider, state)

    payload["audit_updated_at"] = now_iso
    return persist_snapshot_fn(payload)
