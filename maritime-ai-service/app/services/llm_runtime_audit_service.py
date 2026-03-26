"""
Persisted runtime discovery + live capability audit for admin LLM policy.

This layer keeps operational facts separate from the runtime policy itself:
  - discovery timestamps and success/failure
  - live capability probe results
  - degraded provider annotations for admin UX
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from pydantic import BaseModel

from app.core.config import settings
from app.engine.llm_provider_registry import create_provider, get_supported_provider_names
from app.engine.llm_providers.ollama_provider import (
    check_ollama_host_reachable,
    reset_ollama_availability_cache,
)
from app.engine.model_catalog import (
    ChatModelMetadata,
    GOOGLE_DEFAULT_MODEL,
    ModelCatalogService,
    OPENAI_DEFAULT_MODEL,
    OPENAI_DEFAULT_MODEL_ADVANCED,
    ZHIPU_DEFAULT_MODEL,
    ZHIPU_DEFAULT_MODEL_ADVANCED,
    get_provider_chat_model_metadata,
    resolve_openai_catalog_provider,
)
from app.repositories.admin_runtime_settings_repository import (
    get_admin_runtime_settings_repository,
)

logger = logging.getLogger(__name__)

LLM_RUNTIME_AUDIT_KEY = "llm_runtime_audit"
LLM_RUNTIME_AUDIT_DESCRIPTION = "Persisted LLM runtime discovery and capability audit"
LLM_RUNTIME_AUDIT_SCHEMA_VERSION = 1
LIVE_PROBE_TIMEOUT_SECONDS = 10.0

_PROVIDER_EXPECTED_CAPABILITIES: dict[str, dict[str, bool]] = {
    "google": {
        "tool_calling": True,
        "structured_output": True,
        "streaming": True,
    },
    "openai": {
        "tool_calling": True,
        "structured_output": True,
        "streaming": True,
    },
    "openrouter": {
        "streaming": True,
    },
    "zhipu": {
        "tool_calling": True,
        "structured_output": True,
        "streaming": True,
    },
    "ollama": {
        "streaming": True,
    },
}

_PROVIDER_STR_FIELDS = frozenset(
    {
        "provider",
        "selected_model",
        "selected_model_advanced",
        "probe_model",
        "catalog_source",
        "last_discovery_attempt_at",
        "last_discovery_success_at",
        "last_discovery_error",
        "last_live_probe_attempt_at",
        "last_live_probe_success_at",
        "last_live_probe_error",
        "live_probe_note",
        "tool_calling_source",
        "structured_output_source",
        "streaming_source",
        "context_window_source",
        "max_output_source",
    }
)
_PROVIDER_BOOL_FIELDS = frozenset(
    {
        "runtime_discovery_enabled",
        "runtime_discovery_succeeded",
        "selected_model_in_catalog",
        "selected_model_advanced_in_catalog",
        "degraded",
    }
)
_PROVIDER_OPTIONAL_BOOL_FIELDS = frozenset(
    {
        "tool_calling_supported",
        "structured_output_supported",
        "streaming_supported",
    }
)
_PROVIDER_INT_FIELDS = frozenset(
    {
        "model_count",
        "discovered_model_count",
        "context_window_tokens",
        "max_output_tokens",
    }
)


@dataclass(frozen=True)
class LlmRuntimeAuditRecord:
    payload: dict[str, Any]
    updated_at: Optional[datetime]
    persisted: bool = False
    warnings: tuple[str, ...] = ()


class _StructuredProbeResult(BaseModel):
    status: str
    detail: str


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat()


def _default_provider_state(provider: str) -> dict[str, Any]:
    return {
        "provider": provider,
        "selected_model": None,
        "selected_model_advanced": None,
        "selected_model_in_catalog": False,
        "selected_model_advanced_in_catalog": False,
        "probe_model": None,
        "catalog_source": "static",
        "runtime_discovery_enabled": False,
        "runtime_discovery_succeeded": False,
        "model_count": 0,
        "discovered_model_count": 0,
        "last_discovery_attempt_at": None,
        "last_discovery_success_at": None,
        "last_discovery_error": None,
        "last_live_probe_attempt_at": None,
        "last_live_probe_success_at": None,
        "last_live_probe_error": None,
        "live_probe_note": None,
        "degraded": False,
        "degraded_reasons": [],
        "tool_calling_supported": None,
        "tool_calling_source": None,
        "structured_output_supported": None,
        "structured_output_source": None,
        "streaming_supported": None,
        "streaming_source": None,
        "context_window_tokens": None,
        "context_window_source": None,
        "max_output_tokens": None,
        "max_output_source": None,
    }


def _default_audit_payload() -> dict[str, Any]:
    return {
        "schema_version": LLM_RUNTIME_AUDIT_SCHEMA_VERSION,
        "audit_updated_at": None,
        "last_live_probe_at": None,
        "providers": {
            provider: _default_provider_state(provider)
            for provider in get_supported_provider_names()
        },
    }


def sanitize_llm_runtime_audit_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    clean = _default_audit_payload()
    if not isinstance(payload, Mapping):
        return clean

    audit_updated_at = payload.get("audit_updated_at")
    if isinstance(audit_updated_at, str) and audit_updated_at.strip():
        clean["audit_updated_at"] = audit_updated_at.strip()
    last_live_probe_at = payload.get("last_live_probe_at")
    if isinstance(last_live_probe_at, str) and last_live_probe_at.strip():
        clean["last_live_probe_at"] = last_live_probe_at.strip()

    raw_providers = payload.get("providers")
    if not isinstance(raw_providers, Mapping):
        return clean

    for provider in get_supported_provider_names():
        raw_state = raw_providers.get(provider)
        if not isinstance(raw_state, Mapping):
            continue
        state = clean["providers"][provider]

        for field_name in _PROVIDER_STR_FIELDS:
            value = raw_state.get(field_name)
            if isinstance(value, str):
                state[field_name] = value.strip() or None

        for field_name in _PROVIDER_BOOL_FIELDS:
            value = raw_state.get(field_name)
            if isinstance(value, bool):
                state[field_name] = value

        for field_name in _PROVIDER_OPTIONAL_BOOL_FIELDS:
            value = raw_state.get(field_name)
            if value is None or isinstance(value, bool):
                state[field_name] = value

        for field_name in _PROVIDER_INT_FIELDS:
            value = raw_state.get(field_name)
            if isinstance(value, int):
                state[field_name] = value

        degraded_reasons = raw_state.get("degraded_reasons")
        if isinstance(degraded_reasons, list):
            state["degraded_reasons"] = [
                str(reason).strip()
                for reason in degraded_reasons
                if str(reason).strip()
            ]

    return clean


def get_persisted_llm_runtime_audit() -> Optional[LlmRuntimeAuditRecord]:
    repo = get_admin_runtime_settings_repository()
    record = repo.get_settings(LLM_RUNTIME_AUDIT_KEY)
    if record is None:
        return None
    return LlmRuntimeAuditRecord(
        payload=sanitize_llm_runtime_audit_payload(record.settings),
        updated_at=record.updated_at,
        persisted=True,
    )


def persist_llm_runtime_audit_snapshot(snapshot: Mapping[str, Any]) -> Optional[LlmRuntimeAuditRecord]:
    repo = get_admin_runtime_settings_repository()
    clean = sanitize_llm_runtime_audit_payload(snapshot)
    record = repo.upsert_settings(
        LLM_RUNTIME_AUDIT_KEY,
        clean,
        description=LLM_RUNTIME_AUDIT_DESCRIPTION,
    )
    if record is None:
        return LlmRuntimeAuditRecord(
            payload=clean,
            updated_at=_utcnow(),
            persisted=False,
            warnings=(
                "Could not persist LLM runtime audit to admin_runtime_settings. "
                "Run the admin runtime settings migration to enable durable audit history.",
            ),
        )
    return LlmRuntimeAuditRecord(
        payload=sanitize_llm_runtime_audit_payload(record.settings),
        updated_at=record.updated_at,
        persisted=True,
    )


def _get_current_audit_payload() -> dict[str, Any]:
    existing = get_persisted_llm_runtime_audit()
    if existing and existing.payload:
        return copy.deepcopy(existing.payload)
    return _default_audit_payload()


def _get_selected_models() -> dict[str, dict[str, str | None]]:
    openai_catalog_provider = resolve_openai_catalog_provider(
        active_provider=settings.llm_provider,
        openai_base_url=settings.openai_base_url,
    )
    openai_model = settings.openai_model or OPENAI_DEFAULT_MODEL
    openai_model_advanced = settings.openai_model_advanced or OPENAI_DEFAULT_MODEL_ADVANCED
    return {
        "google": {
            "model": settings.google_model or GOOGLE_DEFAULT_MODEL,
            "advanced": None,
        },
        "openai": {
            "model": openai_model,
            "advanced": openai_model_advanced,
        },
        "openrouter": {
            "model": openai_model,
            "advanced": openai_model_advanced,
        },
        "zhipu": {
            "model": getattr(settings, "zhipu_model", ZHIPU_DEFAULT_MODEL),
            "advanced": getattr(settings, "zhipu_model_advanced", ZHIPU_DEFAULT_MODEL_ADVANCED),
        },
        "ollama": {
            "model": settings.ollama_model,
            "advanced": None,
        },
        "_shared_openai_slot": {
            "model": openai_catalog_provider,
            "advanced": None,
        },
    }


def _lookup_selected_model_metadata(
    catalog: Mapping[str, Any],
    provider: str,
    model_name: str | None,
) -> ChatModelMetadata | None:
    providers = catalog.get("providers")
    if isinstance(providers, Mapping):
        provider_models = providers.get(provider)
        if isinstance(provider_models, Mapping) and model_name:
            metadata = provider_models.get(model_name)
            if isinstance(metadata, ChatModelMetadata):
                return metadata
    return get_provider_chat_model_metadata(provider, model_name)


def _apply_metadata_hints(
    state: dict[str, Any],
    metadata: ChatModelMetadata | None,
) -> None:
    if metadata is None:
        return

    capability_source = metadata.capability_source or "static"
    if (
        state.get("tool_calling_source") != "live_probe"
        and metadata.supports_tool_calling is not None
    ):
        state["tool_calling_supported"] = metadata.supports_tool_calling
        state["tool_calling_source"] = capability_source
    if (
        state.get("structured_output_source") != "live_probe"
        and metadata.supports_structured_output is not None
    ):
        state["structured_output_supported"] = metadata.supports_structured_output
        state["structured_output_source"] = capability_source
    if (
        state.get("streaming_source") != "live_probe"
        and metadata.supports_streaming is not None
    ):
        state["streaming_supported"] = metadata.supports_streaming
        state["streaming_source"] = capability_source
    if (
        state.get("context_window_source") != "live_probe"
        and metadata.context_window_tokens is not None
    ):
        state["context_window_tokens"] = metadata.context_window_tokens
        state["context_window_source"] = capability_source
    if (
        state.get("max_output_source") != "live_probe"
        and metadata.max_output_tokens is not None
    ):
        state["max_output_tokens"] = metadata.max_output_tokens
        state["max_output_source"] = capability_source


def _refresh_degraded_state(provider: str, state: dict[str, Any]) -> None:
    reasons: list[str] = []
    if state.get("runtime_discovery_enabled") and not state.get("runtime_discovery_succeeded"):
        reasons.append("Runtime discovery that current provider slot failed.")
    if state.get("last_live_probe_error"):
        reasons.append("Live capability probe failed.")

    expected = _PROVIDER_EXPECTED_CAPABILITIES.get(provider, {})
    if state.get("last_live_probe_attempt_at"):
        if expected.get("tool_calling") and state.get("tool_calling_source") == "live_probe" and state.get("tool_calling_supported") is False:
            reasons.append("Tool calling probe returned false.")
        if expected.get("structured_output") and state.get("structured_output_source") == "live_probe" and state.get("structured_output_supported") is False:
            reasons.append("Structured output probe returned false.")
        if expected.get("streaming") and state.get("streaming_source") == "live_probe" and state.get("streaming_supported") is False:
            reasons.append("Streaming probe returned false.")

    deduped: list[str] = []
    for reason in reasons:
        if reason not in deduped:
            deduped.append(reason)
    state["degraded"] = bool(deduped)
    state["degraded_reasons"] = deduped


def record_runtime_discovery_snapshot(catalog: Mapping[str, Any]) -> Optional[LlmRuntimeAuditRecord]:
    payload = _get_current_audit_payload()
    selected_models = _get_selected_models()
    provider_metadata = catalog.get("provider_metadata", {})
    now_iso = _iso(_utcnow())

    for provider in get_supported_provider_names():
        state = payload["providers"].setdefault(provider, _default_provider_state(provider))
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
                selected.get("advanced") and selected.get("advanced") in provider_catalog
            )
        else:
            state["selected_model_in_catalog"] = False
            state["selected_model_advanced_in_catalog"] = False

        meta = provider_metadata.get(provider, {}) if isinstance(provider_metadata, Mapping) else {}
        state["catalog_source"] = str(meta.get("catalog_source") or state.get("catalog_source") or "static")
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
        state["runtime_discovery_enabled"] = bool(meta.get("runtime_discovery_enabled", False))
        state["runtime_discovery_succeeded"] = bool(meta.get("runtime_discovery_succeeded", False))

        if state["runtime_discovery_enabled"]:
            state["last_discovery_attempt_at"] = now_iso
            if state["runtime_discovery_succeeded"]:
                state["last_discovery_success_at"] = now_iso
                state["last_discovery_error"] = None
            else:
                state["last_discovery_error"] = "Runtime discovery failed for the current credentials or endpoint."

        metadata = _lookup_selected_model_metadata(
            catalog,
            provider,
            selected.get("model"),
        )
        _apply_metadata_hints(state, metadata)
        _refresh_degraded_state(provider, state)

    payload["audit_updated_at"] = now_iso
    return persist_llm_runtime_audit_snapshot(payload)


async def _close_async_iterator(iterator: Any) -> None:
    aclose = getattr(iterator, "aclose", None)
    if callable(aclose):
        try:
            await aclose()
        except Exception:
            return


async def _probe_streaming(llm: Any) -> bool:
    iterator = llm.astream("Chi tra loi duy nhat mot tu: OK").__aiter__()
    try:
        await asyncio.wait_for(iterator.__anext__(), timeout=LIVE_PROBE_TIMEOUT_SECONDS)
        return True
    except StopAsyncIteration:
        return False
    finally:
        await _close_async_iterator(iterator)


async def _probe_tool_calling(provider: str, llm: Any) -> bool:
    from langchain_core.tools import tool

    @tool("runtime_capability_probe")
    def runtime_capability_probe(note: str) -> str:
        """Return a deterministic string for live tool-calling probes."""
        return f"probe:{note}"

    tool_choice = "any" if provider == "google" else "required"
    prompt = (
        "Hay goi tool runtime_capability_probe voi note='ok'. "
        "Khong tra loi tu nhien va khong mo ta them."
    )

    try:
        llm_with_tools = llm.bind_tools([runtime_capability_probe], tool_choice=tool_choice)
    except Exception:
        llm_with_tools = llm.bind_tools([runtime_capability_probe])

    response = await asyncio.wait_for(
        llm_with_tools.ainvoke(prompt),
        timeout=LIVE_PROBE_TIMEOUT_SECONDS,
    )
    tool_calls = getattr(response, "tool_calls", None)
    if isinstance(tool_calls, list) and tool_calls:
        return True
    additional_kwargs = getattr(response, "additional_kwargs", {})
    if isinstance(additional_kwargs, Mapping):
        extra_calls = additional_kwargs.get("tool_calls")
        if isinstance(extra_calls, list) and extra_calls:
            return True
    return False


def _resolve_openai_compatible_probe_config(
    provider: str,
    model_name: str | None,
) -> tuple[str | None, str | None, dict[str, str]]:
    if provider == "zhipu":
        return (
            getattr(settings, "zhipu_base_url", "https://open.bigmodel.cn/api/paas/v4"),
            getattr(settings, "zhipu_api_key", None),
            {},
        )
    if provider == "openai":
        return (
            settings.openai_base_url or "https://api.openai.com/v1",
            settings.openai_api_key,
            {},
        )
    if provider == "openrouter":
        return (
            settings.openai_base_url or "https://openrouter.ai/api/v1",
            settings.openai_api_key,
            {},
        )
    return (None, None, {})


async def _probe_openai_compatible_structured_output(
    provider: str,
    model_name: str | None,
) -> bool:
    base_url, api_key, extra_headers = _resolve_openai_compatible_probe_config(
        provider,
        model_name,
    )
    if not base_url or not api_key or not model_name:
        raise ValueError("OpenAI-compatible structured probe is missing endpoint credentials or model.")

    import httpx

    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        **extra_headers,
    }
    payload = {
        "model": model_name,
        "temperature": 0,
        "max_tokens": 256,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You must reply with valid JSON only. "
                    'Return a JSON object with status="ok" and detail="probe".'
                ),
            },
            {
                "role": "user",
                "content": "Return the JSON object now.",
            },
        ],
    }

    async with httpx.AsyncClient(timeout=LIVE_PROBE_TIMEOUT_SECONDS) as client:
        response = await client.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return False
    message = choices[0].get("message", {})
    if not isinstance(message, Mapping):
        return False
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        return False
    parsed = json.loads(content)
    if not isinstance(parsed, Mapping):
        return False
    if parsed.get("status") != "ok":
        return False
    detail = parsed.get("detail")
    return detail in (None, "probe")


async def _probe_google_runtime_health(model_name: str | None) -> None:
    if not settings.google_api_key or not model_name:
        raise ValueError("Google runtime probe is missing API credentials or model.")

    def _run_probe() -> None:
        from google import genai

        client = genai.Client(api_key=settings.google_api_key)
        response = client.models.generate_content(
            model=model_name,
            contents="Tra loi DUY NHAT mot tu: OK",
        )
        if not getattr(response, "text", "").strip():
            raise RuntimeError("Google runtime probe returned empty content.")

    await asyncio.wait_for(
        asyncio.to_thread(_run_probe),
        timeout=LIVE_PROBE_TIMEOUT_SECONDS,
    )


async def _probe_structured_output(
    provider: str,
    llm: Any,
    model_name: str | None,
) -> bool:
    if provider in {"zhipu", "openai", "openrouter"}:
        return await _probe_openai_compatible_structured_output(provider, model_name)

    structured_llm = llm.with_structured_output(_StructuredProbeResult)
    result = await asyncio.wait_for(
        structured_llm.ainvoke("Tra ve status='ok' va detail='probe' theo schema."),
        timeout=LIVE_PROBE_TIMEOUT_SECONDS,
    )
    return isinstance(result, _StructuredProbeResult)


async def _probe_ollama_context_window(model_name: str | None) -> tuple[int | None, str | None]:
    if not model_name or not settings.ollama_base_url:
        return None, None

    import httpx

    base_url = settings.ollama_base_url.rstrip("/")
    if base_url.endswith("/api"):
        base_url = base_url[:-4]
    headers: dict[str, str] = {}
    if getattr(settings, "ollama_api_key", None):
        headers["Authorization"] = f"Bearer {settings.ollama_api_key}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{base_url}/api/show",
                json={"model": model_name},
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
    except Exception:
        return None, None

    def _extract_mapping_limit(mapping: Any) -> int | None:
        if not isinstance(mapping, Mapping):
            return None
        for key in (
            "context_length",
            "context_window",
            "num_ctx",
            "general.context_length",
            "llama.context_length",
            "qwen2.context_length",
        ):
            value = mapping.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.strip().isdigit():
                return int(value.strip())
        return None

    for candidate in (data, data.get("details"), data.get("model_info"), data.get("parameters")):
        limit = _extract_mapping_limit(candidate)
        if limit is not None:
            return limit, "runtime"
    return None, None


def _can_probe_provider(provider: str) -> tuple[bool, str | None]:
    if provider in {"openai", "openrouter"}:
        active_slot = resolve_openai_catalog_provider(
            active_provider=settings.llm_provider,
            openai_base_url=settings.openai_base_url,
        )
        if provider != active_slot:
            return (
                False,
                f"Shared OpenAI-compatible slot is currently targeting {active_slot}, not {provider}.",
            )

    try:
        provider_obj = create_provider(provider)
    except Exception as exc:
        return False, _summarize_probe_error("provider init", exc)
    if not provider_obj.is_configured():
        return False, "Provider is not configured."
    if provider == "ollama":
        reset_ollama_availability_cache()
        if not check_ollama_host_reachable(force_refresh=True):
            base_url = getattr(settings, "ollama_base_url", None) or "http://localhost:11434"
            return False, f"Ollama host unreachable at {base_url}."
    return True, None


def _summarize_probe_error(label: str, exc: Exception) -> str:
    detail = str(exc).strip()
    class_name = exc.__class__.__name__
    lowered = detail.lower()

    if isinstance(exc, asyncio.TimeoutError):
        return f"{label}: timeout"
    if class_name == "ResourceExhausted" or "429" in lowered:
        return f"{label}: quota_or_rate_limited (429)"
    if isinstance(exc, ImportError):
        return f"{label}: dependency_missing ({detail})"
    if "not configured" in lowered:
        return f"{label}: provider_not_configured"
    if detail:
        return f"{label}: {class_name}: {detail}"
    return f"{label}: {class_name}"


async def _probe_provider_capabilities(provider: str) -> dict[str, Any]:
    selected_models = _get_selected_models()
    model_name = selected_models.get(provider, {}).get("model")

    if provider == "google":
        await _probe_google_runtime_health(model_name)
        return {
            "probe_model": model_name,
            "live_probe_note": "Live health probe passed. Capability flags are sourced from the runtime catalog.",
            "last_live_probe_error": None,
        }

    try:
        provider_obj = create_provider(provider)
        llm = provider_obj.create_instance("light", temperature=0.0)
    except Exception as exc:
        raise RuntimeError(_summarize_probe_error("provider bootstrap", exc)) from exc

    result: dict[str, Any] = {
        "probe_model": model_name,
        "live_probe_note": "Live probe passed.",
        "last_live_probe_error": None,
    }
    errors: list[str] = []

    try:
        tool_calling_supported = await _probe_tool_calling(provider, llm)
        result["tool_calling_supported"] = tool_calling_supported
        result["tool_calling_source"] = "live_probe"
    except Exception as exc:
        result["tool_calling_supported"] = None
        result["tool_calling_source"] = "probe_failed"
        errors.append(_summarize_probe_error("tool calling", exc))

    try:
        structured_output_supported = await _probe_structured_output(provider, llm, model_name)
        result["structured_output_supported"] = structured_output_supported
        result["structured_output_source"] = "live_probe"
    except Exception as exc:
        result["structured_output_supported"] = None
        result["structured_output_source"] = "probe_failed"
        errors.append(_summarize_probe_error("structured output", exc))

    try:
        streaming_supported = await _probe_streaming(llm)
        result["streaming_supported"] = streaming_supported
        result["streaming_source"] = "live_probe"
    except Exception as exc:
        result["streaming_supported"] = None
        result["streaming_source"] = "probe_failed"
        errors.append(_summarize_probe_error("streaming", exc))

    context_window_tokens = None
    context_window_source = None
    if provider == "ollama":
        context_window_tokens, context_window_source = await _probe_ollama_context_window(model_name)
    if context_window_tokens is not None:
        result["context_window_tokens"] = context_window_tokens
        result["context_window_source"] = context_window_source

    if errors:
        result["last_live_probe_error"] = "; ".join(errors)
        result["live_probe_note"] = "Live probe completed with partial failures."
    return result


async def run_live_capability_probes(
    catalog: Mapping[str, Any],
    providers: list[str] | None = None,
) -> Optional[LlmRuntimeAuditRecord]:
    payload = _get_current_audit_payload()
    selected_models = _get_selected_models()
    now_iso = _iso(_utcnow())

    targets = providers or list(get_supported_provider_names())
    for provider in targets:
        if provider not in payload["providers"]:
            continue

        state = payload["providers"][provider]
        selected = selected_models.get(provider, {})
        state["selected_model"] = selected.get("model")
        state["selected_model_advanced"] = selected.get("advanced")
        state["probe_model"] = selected.get("model")
        state["last_live_probe_attempt_at"] = now_iso
        state["last_live_probe_error"] = None
        state["live_probe_note"] = None

        metadata = _lookup_selected_model_metadata(catalog, provider, selected.get("model"))
        _apply_metadata_hints(state, metadata)

        can_probe, note = _can_probe_provider(provider)
        if not can_probe:
            state["live_probe_note"] = note
            lowered_note = (note or "").lower()
            if note and any(
                marker in lowered_note
                for marker in ("unreachable", "dependency_missing", "connecterror", "timeout")
            ):
                state["last_live_probe_error"] = note
            _refresh_degraded_state(provider, state)
            continue

        try:
            state.update(await _probe_provider_capabilities(provider))
            state["last_live_probe_success_at"] = now_iso
        except Exception as exc:
            state["last_live_probe_error"] = _summarize_probe_error("provider probe", exc)
            state["live_probe_note"] = "Live probe failed."

        _refresh_degraded_state(provider, state)

    payload["audit_updated_at"] = now_iso
    payload["last_live_probe_at"] = now_iso
    return persist_llm_runtime_audit_snapshot(payload)


def build_runtime_audit_summary(
    audit_record: LlmRuntimeAuditRecord | None,
) -> dict[str, Any]:
    if audit_record is None:
        return {
            "audit_updated_at": None,
            "last_live_probe_at": None,
            "degraded_providers": [],
            "audit_persisted": False,
            "audit_warnings": [],
        }

    payload = sanitize_llm_runtime_audit_payload(audit_record.payload)
    degraded = [
        provider
        for provider, state in payload.get("providers", {}).items()
        if isinstance(state, Mapping) and state.get("degraded")
    ]
    return {
        "audit_updated_at": payload.get("audit_updated_at"),
        "last_live_probe_at": payload.get("last_live_probe_at"),
        "degraded_providers": degraded,
        "audit_persisted": bool(getattr(audit_record, "persisted", False)),
        "audit_warnings": list(getattr(audit_record, "warnings", ()) or ()),
    }


async def refresh_request_selectable_runtime_audit(
    *,
    run_live_probe: bool = True,
    providers: list[str] | None = None,
) -> Optional[LlmRuntimeAuditRecord]:
    """Refresh persisted runtime discovery/live probe for chat-selectable providers."""
    from app.engine.llm_pool import LLMPool

    catalog = await ModelCatalogService.get_full_catalog(
        ollama_base_url=settings.ollama_base_url if settings.ollama_base_url else None,
        active_provider=settings.llm_provider,
        google_api_key=settings.google_api_key,
        openai_base_url=settings.openai_base_url,
        openai_api_key=settings.openai_api_key,
        zhipu_base_url=getattr(settings, "zhipu_base_url", None),
        zhipu_api_key=getattr(settings, "zhipu_api_key", None),
    )
    discovery_record = record_runtime_discovery_snapshot(catalog)
    targets = providers or LLMPool.get_request_selectable_providers()
    audit_record = discovery_record
    if run_live_probe and targets:
        audit_record = await run_live_capability_probes(
            catalog,
            providers=targets,
        ) or discovery_record

    try:
        from app.services.llm_selectability_service import invalidate_llm_selectability_cache

        invalidate_llm_selectability_cache()
    except Exception:
        logger.debug("Could not invalidate LLM selectability cache after audit refresh")

    return audit_record


async def background_refresh_request_selectable_runtime_audit(
    run_live_probe: bool = True,
) -> None:
    """Best-effort background audit refresh triggered on startup."""
    try:
        await refresh_request_selectable_runtime_audit(run_live_probe=run_live_probe)
    except Exception as exc:
        logger.warning("Background LLM runtime audit refresh failed: %s", exc)
