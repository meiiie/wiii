"""
LLM runtime admin helpers.

The admin router keeps the HTTP surface stable while this module owns the
heavier runtime/model-catalog/update logic.
"""

from __future__ import annotations

from app.engine.openai_compatible_credentials import (
    resolve_nvidia_api_key,
    resolve_nvidia_base_url,
    resolve_nvidia_model,
    resolve_nvidia_model_advanced,
    resolve_openrouter_api_key,
    resolve_openrouter_base_url,
    resolve_openrouter_model,
    resolve_openrouter_model_advanced,
)

from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from fastapi import HTTPException

from app.api.v1.admin_llm_runtime_support import (
    build_model_catalog_response_runtime_impl,
    update_llm_runtime_config_runtime_impl,
)


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _provider_recovered_since_probe(audit_state: Mapping[str, Any]) -> bool:
    probe_attempt_at = _parse_iso(audit_state.get("last_live_probe_attempt_at"))
    runtime_observation_at = _parse_iso(audit_state.get("last_runtime_observation_at"))
    runtime_success_at = _parse_iso(audit_state.get("last_runtime_success_at"))
    probe_success_at = _parse_iso(audit_state.get("last_live_probe_success_at"))
    probe_error = str(audit_state.get("last_live_probe_error") or "").strip()
    if runtime_success_at is None or runtime_observation_at is None or probe_attempt_at is None:
        return False
    if runtime_success_at < probe_attempt_at:
        return False
    if runtime_success_at < runtime_observation_at:
        return False
    if probe_success_at is not None and probe_success_at >= runtime_success_at:
        return False
    return bool(probe_error)


def build_provider_runtime_statuses_impl(
    stats: dict,
    *,
    settings_obj,
    get_supported_provider_names_fn,
    create_provider_fn,
    get_provider_display_name_fn,
    get_llm_selectability_snapshot_fn=None,
    provider_runtime_status_cls,
    configurable_providers,
    logger,
) -> list:
    providers_registered = set(stats.get("providers_registered", []))
    request_selectable = set(stats.get("request_selectable_providers", []))
    active_provider = stats.get("active_provider")
    failover_chain = list(getattr(settings_obj, "llm_failover_chain", []))

    provider_names = list(get_supported_provider_names_fn())
    for candidate in providers_registered | request_selectable | set(failover_chain):
        if candidate not in provider_names:
            provider_names.append(candidate)

    statuses: list = []
    selectability_by_provider = {}
    if callable(get_llm_selectability_snapshot_fn):
        try:
            selectability_by_provider = {
                item.provider: item
                for item in get_llm_selectability_snapshot_fn()
            }
        except Exception as exc:
            logger.debug("Could not inspect provider selectability snapshot: %s", exc)
    for provider_name in provider_names:
        configured = False
        available = False
        try:
            provider = create_provider_fn(provider_name)
            configured = bool(provider.is_configured())
            available = bool(provider.is_available())
        except Exception as exc:
            logger.debug(
                "Could not inspect provider runtime status for %s: %s",
                provider_name,
                exc,
            )
        selectability = selectability_by_provider.get(provider_name)

        statuses.append(
            provider_runtime_status_cls(
                provider=provider_name,
                display_name=get_provider_display_name_fn(provider_name),
                configured=configured,
                available=available,
                registered=provider_name in providers_registered,
                request_selectable=provider_name in request_selectable,
                in_failover_chain=provider_name in failover_chain,
                is_default=provider_name == settings_obj.llm_provider,
                is_active=provider_name == active_provider,
                configurable_via_admin=provider_name in configurable_providers,
                reason_code=getattr(selectability, "reason_code", None),
                reason_label=getattr(selectability, "reason_label", None),
            )
        )

    statuses.sort(
        key=lambda item: (
            0 if item.is_default else 1,
            0 if item.request_selectable else 1,
            0 if item.configured else 1,
            item.provider,
        )
    )
    return statuses


def build_provider_catalog_capabilities_impl(
    provider_status: list,
    *,
    providers_out: dict[str, list],
    provider_metadata: dict[str, dict],
    runtime_audit: Mapping[str, Any] | None,
    settings_obj,
    get_runtime_provider_preset_fn,
    provider_catalog_capability_cls,
    google_default_model: str,
    openai_default_model: str,
    openai_default_model_advanced: str,
) -> dict[str, Any]:
    selected_models = {
        "google": settings_obj.google_model or google_default_model,
        "openai": settings_obj.openai_model or openai_default_model,
        "openrouter": resolve_openrouter_model(settings_obj),
        "nvidia": resolve_nvidia_model(settings_obj),
        "zhipu": getattr(settings_obj, "zhipu_model", "glm-5"),
        "ollama": settings_obj.ollama_model,
    }
    selected_advanced_models = {
        "openai": settings_obj.openai_model_advanced or openai_default_model_advanced,
        "openrouter": resolve_openrouter_model_advanced(settings_obj),
        "nvidia": resolve_nvidia_model_advanced(settings_obj),
        "zhipu": getattr(settings_obj, "zhipu_model_advanced", "glm-5"),
    }
    audit_providers = {}
    if isinstance(runtime_audit, Mapping):
        raw_providers = runtime_audit.get("providers", {})
        if isinstance(raw_providers, Mapping):
            audit_providers = raw_providers

    return {
        item.provider: provider_catalog_capability_cls(
            provider=item.provider,
            display_name=item.display_name,
            configured=item.configured,
            available=item.available,
            request_selectable=item.request_selectable,
            configurable_via_admin=item.configurable_via_admin,
            supports_runtime_discovery=provider_metadata.get(item.provider, {}).get(
                "supports_runtime_discovery", True
            ),
            runtime_discovery_enabled=provider_metadata.get(item.provider, {}).get(
                "runtime_discovery_enabled", False
            ),
            runtime_discovery_succeeded=provider_metadata.get(item.provider, {}).get(
                "runtime_discovery_succeeded", False
            ),
            catalog_source=provider_metadata.get(item.provider, {}).get(
                "catalog_source", "static"
            ),
            model_count=provider_metadata.get(item.provider, {}).get(
                "model_count",
                len(providers_out.get(item.provider, [])),
            ),
            discovered_model_count=provider_metadata.get(item.provider, {}).get(
                "discovered_model_count", 0
            ),
            selected_model=selected_models.get(item.provider),
            selected_model_in_catalog=selected_models.get(item.provider)
            in {entry.model_name for entry in providers_out.get(item.provider, [])},
            selected_model_advanced=selected_advanced_models.get(item.provider),
            selected_model_advanced_in_catalog=selected_advanced_models.get(item.provider)
            in {entry.model_name for entry in providers_out.get(item.provider, [])},
            last_discovery_attempt_at=audit_providers.get(item.provider, {}).get(
                "last_discovery_attempt_at"
            ),
            last_discovery_success_at=audit_providers.get(item.provider, {}).get(
                "last_discovery_success_at"
            ),
            last_live_probe_attempt_at=audit_providers.get(item.provider, {}).get(
                "last_live_probe_attempt_at"
            ),
            last_live_probe_success_at=audit_providers.get(item.provider, {}).get(
                "last_live_probe_success_at"
            ),
            last_live_probe_error=audit_providers.get(item.provider, {}).get(
                "last_live_probe_error"
            ),
            live_probe_note=audit_providers.get(item.provider, {}).get("live_probe_note"),
            last_runtime_observation_at=audit_providers.get(item.provider, {}).get(
                "last_runtime_observation_at"
            ),
            last_runtime_success_at=audit_providers.get(item.provider, {}).get(
                "last_runtime_success_at"
            ),
            last_runtime_error=audit_providers.get(item.provider, {}).get(
                "last_runtime_error"
            ),
            last_runtime_note=audit_providers.get(item.provider, {}).get(
                "last_runtime_note"
            ),
            last_runtime_source=audit_providers.get(item.provider, {}).get(
                "last_runtime_source"
            ),
            degraded=bool(audit_providers.get(item.provider, {}).get("degraded", False)),
            degraded_reasons=list(
                audit_providers.get(item.provider, {}).get("degraded_reasons", [])
            ),
            recovered=_provider_recovered_since_probe(
                audit_providers.get(item.provider, {})
            ),
            recovered_reasons=(
                ["Runtime da hoi phuc sau live probe"]
                if _provider_recovered_since_probe(audit_providers.get(item.provider, {}))
                else []
            ),
            tool_calling_supported=audit_providers.get(item.provider, {}).get(
                "tool_calling_supported"
            ),
            tool_calling_source=audit_providers.get(item.provider, {}).get(
                "tool_calling_source"
            ),
            structured_output_supported=audit_providers.get(item.provider, {}).get(
                "structured_output_supported"
            ),
            structured_output_source=audit_providers.get(item.provider, {}).get(
                "structured_output_source"
            ),
            streaming_supported=audit_providers.get(item.provider, {}).get(
                "streaming_supported"
            ),
            streaming_source=audit_providers.get(item.provider, {}).get(
                "streaming_source"
            ),
            context_window_tokens=audit_providers.get(item.provider, {}).get(
                "context_window_tokens"
            ),
            context_window_source=audit_providers.get(item.provider, {}).get(
                "context_window_source"
            ),
            max_output_tokens=audit_providers.get(item.provider, {}).get(
                "max_output_tokens"
            ),
            max_output_source=audit_providers.get(item.provider, {}).get(
                "max_output_source"
            ),
        )
        for item in provider_status
    }


def serialize_llm_runtime_impl(
    warnings: list[str] | None = None,
    *,
    runtime_policy_persisted: bool = False,
    runtime_policy_updated_at: Optional[str] = None,
    settings_obj,
    build_provider_runtime_statuses_fn,
    logger,
    google_default_model: str,
    get_chat_model_metadata_fn,
    get_embedding_model_metadata_fn,
    default_embedding_model: str,
    sanitize_agent_runtime_profiles_fn,
    agent_runtime_profile_config_cls,
    build_timeout_profiles_snapshot_fn,
    llm_timeout_profiles_config_cls,
    loads_timeout_provider_overrides_fn,
    llm_timeout_provider_override_cls,
    llm_runtime_config_response_cls,
    get_embedding_dimensions_fn,
    build_vision_provider_runtime_statuses_fn,
    build_vision_runtime_audit_summary_fn,
    build_embedding_provider_runtime_statuses_fn,
    build_embedding_space_status_fn,
    build_embedding_migration_previews_fn,
) -> Any:
    from app.engine.llm_pool import LLMPool

    stats = LLMPool.get_stats()
    provider = settings_obj.llm_provider
    keep_alive = getattr(settings_obj, "ollama_keep_alive", None)
    if not isinstance(keep_alive, str):
        keep_alive = None
    else:
        keep_alive = keep_alive.strip() or None
    google_model = settings_obj.google_model or google_default_model
    google_metadata = get_chat_model_metadata_fn(google_model)
    if google_metadata and google_metadata.status == "legacy":
        logger.warning(
            "Serializing legacy Google model in admin runtime config: %s",
            google_model,
        )
    embedding_model = getattr(settings_obj, "embedding_model", "") or default_embedding_model
    embedding_metadata = get_embedding_model_metadata_fn(embedding_model)
    provider_status = build_provider_runtime_statuses_fn(stats)
    agent_profiles = {
        name: agent_runtime_profile_config_cls(**profile)
        for name, profile in sanitize_agent_runtime_profiles_fn(
            getattr(settings_obj, "agent_runtime_profiles", "{}")
        ).items()
    }
    timeout_profiles = llm_timeout_profiles_config_cls(
        **build_timeout_profiles_snapshot_fn(settings_obj)
    )
    timeout_provider_overrides = {
        provider_name: llm_timeout_provider_override_cls(**override)
        for provider_name, override in loads_timeout_provider_overrides_fn(
            getattr(settings_obj, "llm_timeout_provider_overrides", "{}")
        ).items()
    }
    vision_audit = build_vision_runtime_audit_summary_fn()
    vision_provider_status = build_vision_provider_runtime_statuses_fn()
    embedding_provider_status = build_embedding_provider_runtime_statuses_fn()
    embedding_space_status = build_embedding_space_status_fn()
    embedding_migration_previews = build_embedding_migration_previews_fn()

    return llm_runtime_config_response_cls(
        provider=provider,
        use_multi_agent=getattr(settings_obj, "use_multi_agent", True),
        google_model=google_model,
        openai_base_url=settings_obj.openai_base_url,
        openai_model=settings_obj.openai_model,
        openai_model_advanced=settings_obj.openai_model_advanced,
        openrouter_base_url=resolve_openrouter_base_url(settings_obj),
        openrouter_model=resolve_openrouter_model(settings_obj),
        openrouter_model_advanced=resolve_openrouter_model_advanced(settings_obj),
        nvidia_base_url=resolve_nvidia_base_url(settings_obj),
        nvidia_model=resolve_nvidia_model(settings_obj),
        nvidia_model_advanced=resolve_nvidia_model_advanced(settings_obj),
        zhipu_base_url=getattr(settings_obj, "zhipu_base_url", None),
        zhipu_model=getattr(settings_obj, "zhipu_model", "glm-5"),
        zhipu_model_advanced=getattr(settings_obj, "zhipu_model_advanced", "glm-5"),
        openrouter_model_fallbacks=list(
            getattr(settings_obj, "openrouter_model_fallbacks", [])
        ),
        openrouter_provider_order=list(
            getattr(settings_obj, "openrouter_provider_order", [])
        ),
        openrouter_allowed_providers=list(
            getattr(settings_obj, "openrouter_allowed_providers", [])
        ),
        openrouter_ignored_providers=list(
            getattr(settings_obj, "openrouter_ignored_providers", [])
        ),
        openrouter_allow_fallbacks=getattr(settings_obj, "openrouter_allow_fallbacks", None),
        openrouter_require_parameters=getattr(
            settings_obj, "openrouter_require_parameters", None
        ),
        openrouter_data_collection=getattr(
            settings_obj, "openrouter_data_collection", None
        ),
        openrouter_zdr=getattr(settings_obj, "openrouter_zdr", None),
        openrouter_provider_sort=getattr(settings_obj, "openrouter_provider_sort", None),
        ollama_base_url=settings_obj.ollama_base_url,
        ollama_model=settings_obj.ollama_model,
        ollama_keep_alive=keep_alive,
        google_api_key_configured=bool(settings_obj.google_api_key),
        openai_api_key_configured=bool(settings_obj.openai_api_key),
        openrouter_api_key_configured=bool(resolve_openrouter_api_key(settings_obj)),
        nvidia_api_key_configured=bool(resolve_nvidia_api_key(settings_obj)),
        zhipu_api_key_configured=bool(getattr(settings_obj, "zhipu_api_key", None)),
        ollama_api_key_configured=bool(getattr(settings_obj, "ollama_api_key", None)),
        enable_llm_failover=settings_obj.enable_llm_failover,
        llm_failover_chain=list(getattr(settings_obj, "llm_failover_chain", [])),
        active_provider=stats.get("active_provider"),
        providers_registered=list(stats.get("providers_registered", [])),
        request_selectable_providers=list(stats.get("request_selectable_providers", [])),
        provider_status=provider_status,
        agent_profiles=agent_profiles,
        timeout_profiles=timeout_profiles,
        timeout_provider_overrides=timeout_provider_overrides,
        vision_provider=getattr(settings_obj, "vision_provider", "auto"),
        vision_describe_provider=getattr(settings_obj, "vision_describe_provider", "auto"),
        vision_describe_model=getattr(settings_obj, "vision_describe_model", None),
        vision_ocr_provider=getattr(settings_obj, "vision_ocr_provider", "auto"),
        vision_ocr_model=getattr(settings_obj, "vision_ocr_model", None),
        vision_grounded_provider=getattr(settings_obj, "vision_grounded_provider", "auto"),
        vision_grounded_model=getattr(settings_obj, "vision_grounded_model", None),
        vision_failover_chain=list(getattr(settings_obj, "vision_failover_chain", [])),
        vision_timeout_seconds=float(getattr(settings_obj, "vision_timeout_seconds", 30.0)),
        vision_provider_status=vision_provider_status,
        vision_audit_updated_at=vision_audit.audit_updated_at,
        vision_last_live_probe_at=vision_audit.last_live_probe_at,
        vision_audit_persisted=vision_audit.audit_persisted,
        vision_audit_warnings=list(vision_audit.audit_warnings),
        embedding_provider=getattr(settings_obj, "embedding_provider", "auto"),
        embedding_failover_chain=list(getattr(settings_obj, "embedding_failover_chain", [])),
        embedding_model=embedding_model,
        embedding_dimensions=get_embedding_dimensions_fn(embedding_model),
        embedding_status=embedding_metadata.status if embedding_metadata else "custom",
        embedding_provider_status=embedding_provider_status,
        embedding_space_status=embedding_space_status,
        embedding_migration_previews=embedding_migration_previews,
        runtime_policy_persisted=runtime_policy_persisted,
        runtime_policy_updated_at=runtime_policy_updated_at,
        warnings=warnings or [],
    )


async def build_model_catalog_response_impl(
    *,
    run_live_probe: bool = False,
    probe_providers: Optional[list[str]] = None,
    settings_obj,
    build_provider_runtime_statuses_fn,
    build_provider_catalog_capabilities_fn,
    model_catalog_entry_cls,
    model_catalog_response_cls,
    resolve_openai_catalog_provider_fn,
    get_supported_provider_names_fn,
) -> Any:
    return await build_model_catalog_response_runtime_impl(
        run_live_probe=run_live_probe,
        probe_providers=probe_providers,
        settings_obj=settings_obj,
        build_provider_runtime_statuses_fn=build_provider_runtime_statuses_fn,
        build_provider_catalog_capabilities_fn=build_provider_catalog_capabilities_fn,
        model_catalog_entry_cls=model_catalog_entry_cls,
        model_catalog_response_cls=model_catalog_response_cls,
        resolve_openai_catalog_provider_fn=resolve_openai_catalog_provider_fn,
        get_supported_provider_names_fn=get_supported_provider_names_fn,
    )


async def update_llm_runtime_config_impl(
    request,
    body,
    auth,
    *,
    can_manage_llm_runtime_fn,
    normalize_provider_name_fn,
    normalize_chain_fn,
    normalize_string_list_fn,
    normalize_optional_choice_fn,
    serialize_llm_runtime_fn,
    build_model_catalog_response_fn,
    settings_obj,
    logger,
    get_runtime_provider_preset_fn,
    is_known_default_provider_chain_fn,
    should_apply_openrouter_defaults_fn,
    dumps_agent_runtime_profiles_fn,
    dumps_timeout_provider_overrides_fn,
    normalize_vision_provider_name_fn,
    normalize_vision_chain_fn,
    normalize_embedding_provider_name_fn,
    normalize_embedding_chain_fn,
    get_default_embedding_model_for_provider_fn,
    get_embedding_dimensions_fn,
    get_embedding_model_metadata_fn,
    resolve_openai_catalog_provider_fn,
) -> Any:
    return await update_llm_runtime_config_runtime_impl(
        request,
        body,
        auth,
        can_manage_llm_runtime_fn=can_manage_llm_runtime_fn,
        normalize_provider_name_fn=normalize_provider_name_fn,
        normalize_chain_fn=normalize_chain_fn,
        normalize_string_list_fn=normalize_string_list_fn,
        normalize_optional_choice_fn=normalize_optional_choice_fn,
        serialize_llm_runtime_fn=serialize_llm_runtime_fn,
        build_model_catalog_response_fn=build_model_catalog_response_fn,
        settings_obj=settings_obj,
        logger=logger,
        get_runtime_provider_preset_fn=get_runtime_provider_preset_fn,
        is_known_default_provider_chain_fn=is_known_default_provider_chain_fn,
        should_apply_openrouter_defaults_fn=should_apply_openrouter_defaults_fn,
        dumps_agent_runtime_profiles_fn=dumps_agent_runtime_profiles_fn,
        dumps_timeout_provider_overrides_fn=dumps_timeout_provider_overrides_fn,
        normalize_vision_provider_name_fn=normalize_vision_provider_name_fn,
        normalize_vision_chain_fn=normalize_vision_chain_fn,
        normalize_embedding_provider_name_fn=normalize_embedding_provider_name_fn,
        normalize_embedding_chain_fn=normalize_embedding_chain_fn,
        get_default_embedding_model_for_provider_fn=get_default_embedding_model_for_provider_fn,
        get_embedding_dimensions_fn=get_embedding_dimensions_fn,
        get_embedding_model_metadata_fn=get_embedding_model_metadata_fn,
        resolve_openai_catalog_provider_fn=resolve_openai_catalog_provider_fn,
    )
