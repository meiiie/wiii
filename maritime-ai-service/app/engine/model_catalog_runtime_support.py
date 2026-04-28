"""Helper utilities for runtime model catalog discovery."""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Awaitable, Callable

_CATALOG_CACHE_FINGERPRINT_KEY = b"wiii-model-catalog-cache-fingerprint-v1"


def hash_secret(secret: str | None) -> str:
    if not secret:
        return "no-secret"
    digest = hmac.new(
        _CATALOG_CACHE_FINGERPRINT_KEY,
        secret.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:12]


async def run_cached_discovery(
    *,
    provider_cache: dict[str, tuple[float, list]],
    provider_cache_ttl: float,
    cache_key: str,
    fetcher: Callable[[], Awaitable[list]],
    logger,
) -> tuple[list, bool]:
    now = time.time()
    cached = provider_cache.get(cache_key)
    if cached and (now - cached[0]) < provider_cache_ttl:
        return list(cached[1]), True

    try:
        models = await fetcher()
    except Exception as exc:
        logger.debug("Runtime model discovery failed for %s: %s", cache_key, exc)
        if cached:
            return list(cached[1]), False
        return [], False

    provider_cache[cache_key] = (now, list(models))
    return list(models), True


def normalize_google_model_name(raw_name: str) -> str:
    name = raw_name.strip()
    if name.startswith("models/"):
        return name.split("/", 1)[1]
    return name


def normalize_openai_compatible_base_url(
    base_url: str | None,
    default_base_url: str,
) -> str:
    normalized = (base_url or default_base_url).strip().rstrip("/")
    return normalized or default_base_url


def looks_like_chat_model(model_name: str) -> bool:
    lowered = model_name.lower()
    blocked_fragments = (
        "embedding",
        "moderation",
        "audio",
        "speech",
        "transcribe",
        "translation",
        "realtime",
        "image",
        "video",
        "whisper",
        "tts",
        "omni-moderation",
        "computer-use",
    )
    return not any(fragment in lowered for fragment in blocked_fragments)


def coerce_optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        try:
            return int(normalized)
        except ValueError:
            return None
    return None


def coerce_optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return None


def extract_openai_compatible_limits(item: dict[str, Any]) -> tuple[int | None, int | None]:
    context_window = None
    max_output = None
    for key in ("context_length", "context_window", "inputTokenLimit", "input_token_limit"):
        context_window = coerce_optional_int(item.get(key))
        if context_window is not None:
            break
    for key in ("max_output_tokens", "max_completion_tokens", "outputTokenLimit", "output_token_limit"):
        max_output = coerce_optional_int(item.get(key))
        if max_output is not None:
            break
    return context_window, max_output


def extract_openai_compatible_capabilities(
    item: dict[str, Any],
) -> tuple[bool | None, bool | None, bool | None]:
    tool_calling = None
    structured_output = None
    streaming = None
    for key in ("supports_tool_calling", "tool_calling", "function_calling", "supports_functions"):
        tool_calling = coerce_optional_bool(item.get(key))
        if tool_calling is not None:
            break
    for key in ("supports_structured_output", "structured_output", "json_schema", "json_mode"):
        structured_output = coerce_optional_bool(item.get(key))
        if structured_output is not None:
            break
    for key in ("supports_streaming", "streaming"):
        streaming = coerce_optional_bool(item.get(key))
        if streaming is not None:
            break
    return tool_calling, structured_output, streaming


def merge_catalog(static: dict[str, Any], discovered: list[Any]) -> dict[str, Any]:
    merged = dict(static)
    for model in discovered:
        merged[model.model_name] = model
    return merged
