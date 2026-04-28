"""Runtime discovery helpers for the model catalog service shell."""

from __future__ import annotations

import asyncio
import time
from dataclasses import replace
from typing import Any

from app.engine.model_catalog_runtime_support import merge_catalog


async def fetch_google_models_impl(
    *,
    api_key: str,
    httpx_module: Any,
    normalize_google_model_name_fn: Any,
    google_chat_models: dict[str, Any],
    chat_model_metadata_cls: Any,
    coerce_optional_int_fn: Any,
) -> list[Any]:
    async with httpx_module.AsyncClient(timeout=5.0) as client:
        response = await client.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": api_key},
        )
        response.raise_for_status()
        data = response.json()

    seen: set[str] = set()
    models: list[Any] = []
    for item in data.get("models", []):
        raw_name = item.get("name")
        if not isinstance(raw_name, str):
            continue
        model_name = normalize_google_model_name_fn(raw_name)
        if not model_name.startswith("gemini-"):
            continue

        generation_methods = item.get("supportedGenerationMethods", [])
        if "generateContent" not in generation_methods:
            continue
        if any(fragment in model_name for fragment in ("embedding", "image-generation")):
            continue
        if model_name in seen:
            continue
        seen.add(model_name)

        metadata = google_chat_models.get(model_name)
        input_limit = coerce_optional_int_fn(item.get("inputTokenLimit"))
        output_limit = coerce_optional_int_fn(item.get("outputTokenLimit"))
        if metadata is not None:
            models.append(
                replace(
                    metadata,
                    context_window_tokens=(
                        input_limit if input_limit is not None else metadata.context_window_tokens
                    ),
                    max_output_tokens=(
                        output_limit if output_limit is not None else metadata.max_output_tokens
                    ),
                    capability_source=(
                        "runtime"
                        if input_limit is not None or output_limit is not None
                        else metadata.capability_source
                    ),
                )
            )
        else:
            models.append(
                chat_model_metadata_cls(
                    provider="google",
                    model_name=model_name,
                    display_name=str(item.get("displayName") or model_name),
                    status="available",
                    context_window_tokens=input_limit,
                    max_output_tokens=output_limit,
                    capability_source=(
                        "runtime"
                        if input_limit is not None or output_limit is not None
                        else None
                    ),
                )
            )
    return models


async def discover_google_models_impl(
    *,
    cls: Any,
    api_key: str,
    hash_secret_fn: Any,
    run_cached_discovery_fn: Any,
    logger: Any,
) -> list[Any]:
    cache_key = f"google::{hash_secret_fn(api_key)}"
    models, _ = await run_cached_discovery_fn(
        provider_cache=cls._provider_cache,
        provider_cache_ttl=cls._provider_cache_ttl,
        cache_key=cache_key,
        fetcher=lambda: cls._fetch_google_models(api_key),
        logger=logger,
    )
    return models


async def fetch_openai_compatible_models_impl(
    *,
    provider: str,
    base_url: str,
    api_key: str,
    httpx_module: Any,
    normalize_openai_compatible_base_url_fn: Any,
    default_base_url: str,
    get_all_static_chat_models_fn: Any,
    looks_like_chat_model_fn: Any,
    extract_openai_compatible_limits_fn: Any,
    extract_openai_compatible_capabilities_fn: Any,
    chat_model_metadata_cls: Any,
) -> list[Any]:
    normalized_base_url = normalize_openai_compatible_base_url_fn(
        base_url,
        default_base_url,
    )
    async with httpx_module.AsyncClient(timeout=5.0) as client:
        response = await client.get(
            f"{normalized_base_url}/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        response.raise_for_status()
        data = response.json()

    static_catalog = get_all_static_chat_models_fn().get(provider, {})
    seen: set[str] = set()
    models: list[Any] = []
    for item in data.get("data", []):
        model_name = item.get("id")
        if not isinstance(model_name, str):
            continue
        model_name = model_name.strip()
        if not model_name or model_name in seen or not looks_like_chat_model_fn(model_name):
            continue
        seen.add(model_name)

        metadata = static_catalog.get(model_name)
        context_window, max_output = extract_openai_compatible_limits_fn(item)
        (
            supports_tool_calling,
            supports_structured_output,
            supports_streaming,
        ) = extract_openai_compatible_capabilities_fn(item)
        if metadata is not None:
            models.append(
                replace(
                    metadata,
                    supports_tool_calling=(
                        supports_tool_calling
                        if supports_tool_calling is not None
                        else metadata.supports_tool_calling
                    ),
                    supports_structured_output=(
                        supports_structured_output
                        if supports_structured_output is not None
                        else metadata.supports_structured_output
                    ),
                    supports_streaming=(
                        supports_streaming
                        if supports_streaming is not None
                        else metadata.supports_streaming
                    ),
                    context_window_tokens=(
                        context_window
                        if context_window is not None
                        else metadata.context_window_tokens
                    ),
                    max_output_tokens=(
                        max_output
                        if max_output is not None
                        else metadata.max_output_tokens
                    ),
                    capability_source=(
                        "runtime"
                        if any(
                            value is not None
                            for value in (
                                supports_tool_calling,
                                supports_structured_output,
                                supports_streaming,
                                context_window,
                                max_output,
                            )
                        )
                        else metadata.capability_source
                    ),
                )
            )
        else:
            models.append(
                chat_model_metadata_cls(
                    provider=provider,
                    model_name=model_name,
                    display_name=model_name,
                    status="available",
                    supports_tool_calling=supports_tool_calling,
                    supports_structured_output=supports_structured_output,
                    supports_streaming=supports_streaming,
                    context_window_tokens=context_window,
                    max_output_tokens=max_output,
                    capability_source=(
                        "runtime"
                        if any(
                            value is not None
                            for value in (
                                supports_tool_calling,
                                supports_structured_output,
                                supports_streaming,
                                context_window,
                                max_output,
                            )
                        )
                        else None
                    ),
                )
            )
    return models


async def discover_openai_compatible_models_impl(
    *,
    cls: Any,
    provider: str,
    base_url: str,
    api_key: str,
    normalize_openai_compatible_base_url_fn: Any,
    default_base_url: str,
    hash_secret_fn: Any,
    run_cached_discovery_fn: Any,
    logger: Any,
) -> list[Any]:
    normalized_base_url = normalize_openai_compatible_base_url_fn(
        base_url,
        default_base_url,
    )
    cache_key = f"{provider}::{normalized_base_url}::{hash_secret_fn(api_key)}"
    models, _ = await run_cached_discovery_fn(
        provider_cache=cls._provider_cache,
        provider_cache_ttl=cls._provider_cache_ttl,
        cache_key=cache_key,
        fetcher=lambda: cls._fetch_openai_compatible_models(
            provider=provider,
            base_url=normalized_base_url,
            api_key=api_key,
        ),
        logger=logger,
    )
    return models


async def discover_ollama_models_result_impl(
    *,
    cls: Any,
    base_url: str,
    httpx_module: Any,
    chat_model_metadata_cls: Any,
    logger: Any,
) -> tuple[list[Any], bool]:
    now = time.time()
    if cls._ollama_cache and (now - cls._ollama_cache_ts) < cls._ollama_cache_ttl:
        return list(cls._ollama_cache), True

    url = base_url.rstrip("/")
    if url.endswith("/api"):
        url = url[:-4]

    try:
        async with httpx_module.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{url}/api/tags")
            response.raise_for_status()
            data = response.json()

        models: list[Any] = []
        for item in data.get("models", []):
            name = item.get("name", "")
            if not name:
                continue
            models.append(
                chat_model_metadata_cls(
                    provider="ollama",
                    model_name=name,
                    display_name=name,
                    status="available",
                )
            )

        cls._ollama_cache = models
        cls._ollama_cache_ts = now
        return list(models), True
    except Exception as exc:
        logger.debug("Ollama discovery failed: %s", exc)
        return list(cls._ollama_cache), False


async def discover_ollama_models_impl(
    *,
    cls: Any,
    base_url: str,
) -> list[Any]:
    models, _ = await cls._discover_ollama_models_result(base_url)
    return models


async def get_full_catalog_impl(
    *,
    cls: Any,
    ollama_base_url: str | None,
    active_provider: str | None,
    google_api_key: str | None,
    openai_base_url: str | None,
    openai_api_key: str | None,
    openrouter_base_url: str | None,
    openrouter_api_key: str | None,
    nvidia_base_url: str | None,
    nvidia_api_key: str | None,
    zhipu_base_url: str | None,
    zhipu_api_key: str | None,
    get_all_static_chat_models_fn: Any,
    hash_secret_fn: Any,
    run_cached_discovery_fn: Any,
    resolve_openai_catalog_provider_fn: Any,
    normalize_openai_compatible_base_url_fn: Any,
    openai_default_base_url: str,
    openrouter_default_base_url: str,
    nvidia_default_base_url: str,
    zhipu_default_base_url: str,
    embedding_models: dict[str, Any],
    logger: Any,
) -> dict[str, Any]:
    from datetime import datetime, timezone

    catalog = get_all_static_chat_models_fn()
    provider_metadata: dict[str, dict[str, Any]] = {
        provider: {
            "catalog_source": "static",
            "supports_runtime_discovery": True,
            "runtime_discovery_enabled": False,
            "runtime_discovery_succeeded": False,
            "discovered_model_count": 0,
            "model_count": len(models),
        }
        for provider, models in catalog.items()
    }

    tasks: dict[str, asyncio.Task[tuple[list[Any], bool]]] = {}
    if google_api_key:
        tasks["google"] = asyncio.create_task(
            run_cached_discovery_fn(
                provider_cache=cls._provider_cache,
                provider_cache_ttl=cls._provider_cache_ttl,
                cache_key=f"google::{hash_secret_fn(google_api_key)}",
                fetcher=lambda: cls._fetch_google_models(google_api_key),
                logger=logger,
            )
        )

    if openai_api_key:
        openai_catalog_provider = resolve_openai_catalog_provider_fn(
            active_provider=active_provider,
            openai_base_url=openai_base_url,
        )
        normalized_openai_base = normalize_openai_compatible_base_url_fn(
            openai_base_url,
            openrouter_default_base_url
            if openai_catalog_provider == "openrouter"
            else openai_default_base_url,
        )
        tasks[openai_catalog_provider] = asyncio.create_task(
            run_cached_discovery_fn(
                provider_cache=cls._provider_cache,
                provider_cache_ttl=cls._provider_cache_ttl,
                cache_key=f"{openai_catalog_provider}::{normalized_openai_base}::{hash_secret_fn(openai_api_key)}",
                fetcher=lambda provider=openai_catalog_provider, base=normalized_openai_base: cls._fetch_openai_compatible_models(
                    provider=provider,
                    base_url=base,
                    api_key=openai_api_key,
                ),
                logger=logger,
            )
        )

    if openrouter_api_key and "openrouter" not in tasks:
        normalized_openrouter_base = normalize_openai_compatible_base_url_fn(
            openrouter_base_url,
            openrouter_default_base_url,
        )
        tasks["openrouter"] = asyncio.create_task(
            run_cached_discovery_fn(
                provider_cache=cls._provider_cache,
                provider_cache_ttl=cls._provider_cache_ttl,
                cache_key=f"openrouter::{normalized_openrouter_base}::{hash_secret_fn(openrouter_api_key)}",
                fetcher=lambda base=normalized_openrouter_base: cls._fetch_openai_compatible_models(
                    provider="openrouter",
                    base_url=base,
                    api_key=openrouter_api_key,
                ),
                logger=logger,
            )
        )

    if nvidia_api_key:
        normalized_nvidia_base = normalize_openai_compatible_base_url_fn(
            nvidia_base_url,
            nvidia_default_base_url,
        )
        tasks["nvidia"] = asyncio.create_task(
            run_cached_discovery_fn(
                provider_cache=cls._provider_cache,
                provider_cache_ttl=cls._provider_cache_ttl,
                cache_key=f"nvidia::{normalized_nvidia_base}::{hash_secret_fn(nvidia_api_key)}",
                fetcher=lambda: cls._fetch_openai_compatible_models(
                    provider="nvidia",
                    base_url=normalized_nvidia_base,
                    api_key=nvidia_api_key,
                ),
                logger=logger,
            )
        )

    if zhipu_api_key:
        normalized_zhipu_base = normalize_openai_compatible_base_url_fn(
            zhipu_base_url,
            zhipu_default_base_url,
        )
        tasks["zhipu"] = asyncio.create_task(
            run_cached_discovery_fn(
                provider_cache=cls._provider_cache,
                provider_cache_ttl=cls._provider_cache_ttl,
                cache_key=f"zhipu::{normalized_zhipu_base}::{hash_secret_fn(zhipu_api_key)}",
                fetcher=lambda: cls._fetch_openai_compatible_models(
                    provider="zhipu",
                    base_url=normalized_zhipu_base,
                    api_key=zhipu_api_key,
                ),
                logger=logger,
            )
        )

    if ollama_base_url:
        tasks["ollama"] = asyncio.create_task(cls._discover_ollama_models_result(ollama_base_url))

    discovery_results: dict[str, tuple[list[Any], bool]] = {}
    if tasks:
        resolved = await asyncio.gather(*tasks.values())
        discovery_results = dict(zip(tasks.keys(), resolved))

    for provider, (discovered_models, succeeded) in discovery_results.items():
        metadata = provider_metadata.setdefault(
            provider,
            {
                "catalog_source": "static",
                "supports_runtime_discovery": True,
                "runtime_discovery_enabled": False,
                "runtime_discovery_succeeded": False,
                "discovered_model_count": 0,
                "model_count": len(catalog.get(provider, {})),
            },
        )
        metadata["runtime_discovery_enabled"] = True
        metadata["runtime_discovery_succeeded"] = succeeded
        metadata["discovered_model_count"] = len(discovered_models)

        catalog[provider] = merge_catalog(catalog.get(provider, {}), discovered_models)
        metadata["model_count"] = len(catalog[provider])
        if discovered_models:
            metadata["catalog_source"] = (
                "mixed"
                if len(catalog.get(provider, {})) > len(discovered_models)
                else "runtime"
            )

    ollama_discovered = bool(discovery_results.get("ollama", ([], False))[0])

    return {
        "providers": catalog,
        "provider_metadata": provider_metadata,
        "embedding_models": dict(embedding_models),
        "ollama_discovered": ollama_discovered,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def reset_cache_impl(*, cls: Any) -> None:
    """Clear discovery caches (for testing)."""
    cls._ollama_cache = []
    cls._ollama_cache_ts = 0.0
    cls._provider_cache = {}
