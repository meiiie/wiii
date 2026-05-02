"""Live-probe helpers for LLM runtime audit."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Mapping, Optional

from app.engine.openai_compatible_credentials import (
    is_openrouter_legacy_slot_configured,
    resolve_nvidia_api_key,
    resolve_nvidia_base_url,
    resolve_openai_api_key,
    resolve_openai_base_url,
    resolve_openrouter_api_key,
    resolve_openrouter_base_url,
)


async def close_async_iterator_impl(iterator: Any) -> None:
    aclose = getattr(iterator, "aclose", None)
    if callable(aclose):
        try:
            await aclose()
        except Exception:
            return


async def probe_streaming_impl(
    *,
    llm: Any,
    timeout_seconds: float,
    close_async_iterator_fn: Any,
) -> bool:
    iterator = llm.astream("Chi tra loi duy nhat mot tu: OK").__aiter__()
    try:
        await asyncio.wait_for(iterator.__anext__(), timeout=timeout_seconds)
        return True
    except StopAsyncIteration:
        return False
    finally:
        await close_async_iterator_fn(iterator)


async def probe_tool_calling_impl(
    *,
    provider: str,
    llm: Any,
    timeout_seconds: float,
) -> bool:
    from app.engine.tools.native_tool import tool

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
        timeout=timeout_seconds,
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


def resolve_openai_compatible_probe_config_impl(
    *,
    provider: str,
    settings_obj: Any,
) -> tuple[str | None, str | None, dict[str, str]]:
    if provider == "zhipu":
        return (
            getattr(settings_obj, "zhipu_base_url", "https://open.bigmodel.cn/api/paas/v4"),
            getattr(settings_obj, "zhipu_api_key", None),
            {},
        )
    if provider == "openai":
        return (
            resolve_openai_base_url(settings_obj),
            resolve_openai_api_key(settings_obj),
            {},
        )
    if provider == "openrouter":
        return (
            resolve_openrouter_base_url(settings_obj),
            resolve_openrouter_api_key(settings_obj),
            {},
        )
    if provider == "nvidia":
        return (
            resolve_nvidia_base_url(settings_obj),
            resolve_nvidia_api_key(settings_obj),
            {},
        )
    return (None, None, {})


async def probe_openai_compatible_structured_output_impl(
    *,
    provider: str,
    model_name: str | None,
    timeout_seconds: float,
    resolve_probe_config_fn: Any,
) -> bool:
    base_url, api_key, extra_headers = resolve_probe_config_fn(provider, model_name)
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

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
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


async def probe_google_runtime_health_impl(
    *,
    model_name: str | None,
    google_api_key: str | None,
    timeout_seconds: float,
) -> None:
    if not google_api_key or not model_name:
        raise ValueError("Google runtime probe is missing API credentials or model.")

    def _run_probe() -> None:
        from google import genai

        client = genai.Client(api_key=google_api_key)
        response = client.models.generate_content(
            model=model_name,
            contents="Tra loi DUY NHAT mot tu: OK",
        )
        if not getattr(response, "text", "").strip():
            raise RuntimeError("Google runtime probe returned empty content.")

    await asyncio.wait_for(
        asyncio.to_thread(_run_probe),
        timeout=timeout_seconds,
    )


async def probe_structured_output_impl(
    *,
    provider: str,
    llm: Any,
    model_name: str | None,
    timeout_seconds: float,
    structured_result_cls: Any,
    probe_openai_structured_output_fn: Any,
) -> bool:
    if provider in {"zhipu", "openai", "openrouter", "nvidia"}:
        return await probe_openai_structured_output_fn(provider, model_name)

    structured_llm = llm.with_structured_output(structured_result_cls)
    result = await asyncio.wait_for(
        structured_llm.ainvoke("Tra ve status='ok' va detail='probe' theo schema."),
        timeout=timeout_seconds,
    )
    return isinstance(result, structured_result_cls)


async def probe_ollama_context_window_impl(
    *,
    model_name: str | None,
    ollama_base_url: str | None,
    ollama_api_key: str | None,
) -> tuple[int | None, str | None]:
    if not model_name or not ollama_base_url:
        return None, None

    import httpx

    base_url = ollama_base_url.rstrip("/")
    if base_url.endswith("/api"):
        base_url = base_url[:-4]
    headers: dict[str, str] = {}
    if ollama_api_key:
        headers["Authorization"] = f"Bearer {ollama_api_key}"

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


def can_probe_provider_impl(
    *,
    provider: str,
    settings_obj: Any,
    resolve_openai_catalog_provider_fn: Any,
    create_provider_fn: Any,
    reset_ollama_availability_cache_fn: Any,
    check_ollama_host_reachable_fn: Any,
    summarize_probe_error_fn: Any,
) -> tuple[bool, str | None]:
    legacy_openrouter_slot = is_openrouter_legacy_slot_configured(settings_obj)
    if provider in {"openai", "openrouter"} and legacy_openrouter_slot:
        active_slot = resolve_openai_catalog_provider_fn(
            active_provider=settings_obj.llm_provider,
            openai_base_url=settings_obj.openai_base_url,
        )
        if provider != active_slot:
            return (
                False,
                f"Shared OpenAI-compatible slot is currently targeting {active_slot}, not {provider}.",
            )

    try:
        provider_obj = create_provider_fn(provider)
    except Exception as exc:
        return False, summarize_probe_error_fn("provider init", exc)
    if not provider_obj.is_configured():
        return False, "Provider is not configured."
    if provider == "ollama":
        reset_ollama_availability_cache_fn()
        if not check_ollama_host_reachable_fn(force_refresh=True):
            base_url = getattr(settings_obj, "ollama_base_url", None) or "http://localhost:11434"
            return False, f"Ollama host unreachable at {base_url}."
    return True, None


def summarize_probe_error_impl(*, label: str, exc: Exception) -> str:
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


async def probe_provider_capabilities_impl(
    *,
    provider: str,
    get_selected_models_fn: Any,
    probe_google_runtime_health_fn: Any,
    create_provider_fn: Any,
    summarize_probe_error_fn: Any,
    probe_tool_calling_fn: Any,
    probe_structured_output_fn: Any,
    probe_streaming_fn: Any,
    probe_ollama_context_window_fn: Any,
) -> dict[str, Any]:
    selected_models = get_selected_models_fn()
    model_name = selected_models.get(provider, {}).get("model")

    if provider == "google":
        await probe_google_runtime_health_fn(model_name)
        return {
            "probe_model": model_name,
            "live_probe_note": "Live health probe passed. Capability flags are sourced from the runtime catalog.",
            "last_live_probe_error": None,
        }

    try:
        provider_obj = create_provider_fn(provider)
        llm = provider_obj.create_instance("light", temperature=0.0)
    except Exception as exc:
        raise RuntimeError(summarize_probe_error_fn("provider bootstrap", exc)) from exc

    result: dict[str, Any] = {
        "probe_model": model_name,
        "live_probe_note": "Live probe passed.",
        "last_live_probe_error": None,
    }
    errors: list[str] = []

    try:
        tool_calling_supported = await probe_tool_calling_fn(provider, llm)
        result["tool_calling_supported"] = tool_calling_supported
        result["tool_calling_source"] = "live_probe"
    except Exception as exc:
        result["tool_calling_supported"] = None
        result["tool_calling_source"] = "probe_failed"
        errors.append(summarize_probe_error_fn("tool calling", exc))

    try:
        structured_output_supported = await probe_structured_output_fn(provider, llm, model_name)
        result["structured_output_supported"] = structured_output_supported
        result["structured_output_source"] = "live_probe"
    except Exception as exc:
        result["structured_output_supported"] = None
        result["structured_output_source"] = "probe_failed"
        errors.append(summarize_probe_error_fn("structured output", exc))

    try:
        streaming_supported = await probe_streaming_fn(llm)
        result["streaming_supported"] = streaming_supported
        result["streaming_source"] = "live_probe"
    except Exception as exc:
        result["streaming_supported"] = None
        result["streaming_source"] = "probe_failed"
        errors.append(summarize_probe_error_fn("streaming", exc))

    context_window_tokens = None
    context_window_source = None
    if provider == "ollama":
        context_window_tokens, context_window_source = await probe_ollama_context_window_fn(model_name)
    if context_window_tokens is not None:
        result["context_window_tokens"] = context_window_tokens
        result["context_window_source"] = context_window_source

    if errors:
        result["last_live_probe_error"] = "; ".join(errors)
        result["live_probe_note"] = "Live probe completed with partial failures."
    return result


async def run_live_capability_probes_impl(
    *,
    catalog: Mapping[str, Any],
    providers: list[str] | None,
    get_current_audit_payload_fn: Any,
    get_selected_models_fn: Any,
    iso_now: str,
    supported_provider_names: list[str],
    lookup_selected_model_metadata_fn: Any,
    apply_metadata_hints_fn: Any,
    can_probe_provider_fn: Any,
    refresh_degraded_state_fn: Any,
    probe_provider_capabilities_fn: Any,
    summarize_probe_error_fn: Any,
    persist_snapshot_fn: Any,
) -> Any:
    payload = get_current_audit_payload_fn()
    selected_models = get_selected_models_fn()

    targets = providers or list(supported_provider_names)
    for provider in targets:
        if provider not in payload["providers"]:
            continue

        state = payload["providers"][provider]
        selected = selected_models.get(provider, {})
        state["selected_model"] = selected.get("model")
        state["selected_model_advanced"] = selected.get("advanced")
        state["probe_model"] = selected.get("model")
        state["last_live_probe_attempt_at"] = iso_now
        state["last_live_probe_error"] = None
        state["live_probe_note"] = None

        metadata = lookup_selected_model_metadata_fn(catalog, provider, selected.get("model"))
        apply_metadata_hints_fn(state, metadata)

        can_probe, note = can_probe_provider_fn(provider)
        if not can_probe:
            state["live_probe_note"] = note
            lowered_note = (note or "").lower()
            if note and any(
                marker in lowered_note
                for marker in ("unreachable", "dependency_missing", "connecterror", "timeout")
            ):
                state["last_live_probe_error"] = note
            refresh_degraded_state_fn(provider, state)
            continue

        try:
            state.update(await probe_provider_capabilities_fn(provider))
            state["last_live_probe_success_at"] = iso_now
        except Exception as exc:
            state["last_live_probe_error"] = summarize_probe_error_fn("provider probe", exc)
            state["live_probe_note"] = "Live probe failed."

        refresh_degraded_state_fn(provider, state)

    payload["audit_updated_at"] = iso_now
    payload["last_live_probe_at"] = iso_now
    return persist_snapshot_fn(payload)


def build_runtime_audit_summary_impl(audit_record: Any, sanitize_payload_fn: Any) -> dict[str, Any]:
    if audit_record is None:
        return {
            "audit_updated_at": None,
            "last_live_probe_at": None,
            "degraded_providers": [],
            "audit_persisted": False,
            "audit_warnings": [],
        }

    payload = sanitize_payload_fn(audit_record.payload)
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
