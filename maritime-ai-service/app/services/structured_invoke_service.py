"""Centralized structured invocation policy for multi-provider runtime."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional, Type

from pydantic import BaseModel

from app.core.exceptions import ProviderUnavailableError
from app.engine.llm_pool import (
    FAILOVER_MODE_AUTO,
    FAILOVER_MODE_PINNED,
    TIMEOUT_PROFILE_STRUCTURED,
    ainvoke_with_failover,
)

logger = logging.getLogger(__name__)
_KNOWN_PROVIDERS = {"google", "zhipu", "openai", "openrouter", "nvidia", "ollama"}


def _normalize_provider(provider: Optional[str]) -> Optional[str]:
    if not provider:
        return None
    if not isinstance(provider, str):
        return None
    normalized = str(provider).strip().lower()
    if not normalized or normalized == "auto":
        return None
    if normalized not in _KNOWN_PROVIDERS:
        return None
    return normalized


def _failover_mode_for_provider(provider: Optional[str]) -> str:
    return FAILOVER_MODE_PINNED if _normalize_provider(provider) else FAILOVER_MODE_AUTO


def _resolve_runtime_provider(llm: Any, requested_provider: Optional[str]) -> Optional[str]:
    return _normalize_provider(requested_provider) or _normalize_provider(
        getattr(llm, "_wiii_provider_name", None)
    )


def _copy_runtime_markers(source: Any, target: Any) -> Any:
    for attr in ("_wiii_provider_name", "_wiii_requested_provider"):
        if hasattr(source, attr):
            try:
                setattr(target, attr, getattr(source, attr))
            except Exception:
                pass
    return target


def _set_runtime_markers(
    target: Any,
    *,
    provider_name: Optional[str],
    requested_provider: Optional[str],
) -> Any:
    for attr, value in (
        ("_wiii_provider_name", provider_name),
        ("_wiii_requested_provider", requested_provider),
    ):
        try:
            setattr(target, attr, value)
        except Exception:
            continue
    return target


def _structured_base_llm(llm: Any) -> Any:
    streaming = getattr(llm, "streaming", None)
    if streaming is not True:
        return llm

    model_copy = getattr(llm, "model_copy", None)
    if callable(model_copy):
        try:
            return _copy_runtime_markers(llm, model_copy(update={"streaming": False}))
        except Exception:
            pass

    copy_method = getattr(llm, "copy", None)
    if callable(copy_method):
        try:
            return _copy_runtime_markers(llm, copy_method(update={"streaming": False}))
        except Exception:
            pass

    return llm


def _select_primary_runtime_llm(
    llm: Any,
    *,
    resolved_provider: Optional[str],
    route_llm: Any,
    requested_provider: Optional[str],
) -> Any:
    current_provider = _normalize_provider(getattr(llm, "_wiii_provider_name", None))
    if resolved_provider and current_provider == resolved_provider:
        return _set_runtime_markers(
            llm,
            provider_name=resolved_provider,
            requested_provider=requested_provider,
        )
    return _set_runtime_markers(
        route_llm,
        provider_name=resolved_provider,
        requested_provider=requested_provider,
    )


def _structured_runtime_llm(llm: Any, schema: Type[BaseModel], *, provider_name: Optional[str], requested_provider: Optional[str]) -> Any:
    base_llm = _structured_base_llm(llm)
    structured_llm = base_llm.with_structured_output(schema)
    _copy_runtime_markers(base_llm, structured_llm)
    return _set_runtime_markers(
        structured_llm,
        provider_name=provider_name,
        requested_provider=requested_provider,
    )


def _prefer_json_structured_path(provider: Optional[str]) -> bool:
    return provider in {"zhipu", "nvidia"}


def _extract_text_content(response: Any) -> str:
    from app.services.output_processor import extract_thinking_from_response

    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    text_content, _thinking = extract_thinking_from_response(content)
    return text_content.strip()


def _augment_payload_for_json(schema: Type[BaseModel], payload: Any):
    schema_text = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    instruction = (
        "Tra ve DUY NHAT JSON hop le theo schema sau. "
        "Khong them markdown, khong them giai thich.\n"
        f"Schema: {schema_text}"
    )

    if isinstance(payload, list):
        try:
            from langchain_core.messages import SystemMessage

            return [SystemMessage(content=instruction), *payload]
        except Exception:
            return payload
    return f"{instruction}\n\n{payload}"


def _parse_json_response(schema: Type[BaseModel], response: Any) -> BaseModel:
    text = _extract_text_content(response).strip()
    if not text:
        raise ValueError("Structured invoke fallback returned empty content.")

    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    parsed = json.loads(text)
    return schema.model_validate(parsed)


class StructuredInvokeService:
    """Centralize schema invocation, validation, and fallback strategy."""

    @classmethod
    async def ainvoke(
        cls,
        *,
        llm: Any,
        schema: Type[BaseModel],
        payload: Any,
        tier: str = "moderate",
        provider: str | None = None,
        on_switch=None,
        on_failover=None,
        primary_timeout: float | None = None,
        timeout_profile: str | None = None,
    ) -> BaseModel:
        requested_provider = _normalize_provider(provider) or _normalize_provider(
            getattr(llm, "_wiii_requested_provider", None)
        )
        preferred_provider = requested_provider or _normalize_provider(
            getattr(llm, "_wiii_provider_name", None)
        )
        failover_mode = _failover_mode_for_provider(requested_provider)
        effective_timeout_profile = (
            timeout_profile
            if timeout_profile is not None
            else (TIMEOUT_PROFILE_STRUCTURED if primary_timeout is None else None)
        )
        allow_native_structured = not _prefer_json_structured_path(preferred_provider)
        # Auto mode with Google as the optimistic primary still needs to fail
        # over cleanly to providers like Zhipu that prefer JSON parsing instead
        # of native schema wrappers. Going straight to the JSON path here keeps
        # routing resilient when Gemini is quota-busy.
        if requested_provider is None and preferred_provider == "google":
            allow_native_structured = False

        def _prepare_structured_runtime_llm(candidate_llm: Any) -> Any:
            runtime_provider = _resolve_runtime_provider(candidate_llm, requested_provider)
            return _structured_runtime_llm(
                candidate_llm,
                schema,
                provider_name=runtime_provider,
                requested_provider=requested_provider,
            )

        def _prepare_json_runtime_llm(candidate_llm: Any) -> Any:
            runtime_provider = _resolve_runtime_provider(candidate_llm, requested_provider)
            return _set_runtime_markers(
                _structured_base_llm(candidate_llm),
                provider_name=runtime_provider,
                requested_provider=requested_provider,
            )

        if allow_native_structured:
            try:
                structured_llm = _prepare_structured_runtime_llm(llm)
            except Exception as exc:
                if isinstance(exc, ProviderUnavailableError):
                    raise
                logger.warning(
                    "[STRUCTURED_INVOKE] Native structured path unavailable; falling back to JSON path. provider=%s schema=%s error=%s",
                    preferred_provider,
                    schema.__name__,
                    exc,
                )
            else:
                try:
                    return await ainvoke_with_failover(
                        structured_llm,
                        payload,
                        tier=tier,
                        provider=preferred_provider,
                        failover_mode=failover_mode,
                        on_primary=_prepare_structured_runtime_llm,
                        on_fallback=_prepare_structured_runtime_llm,
                        on_switch=on_switch,
                        on_failover=on_failover,
                        primary_timeout=primary_timeout,
                        timeout_profile=effective_timeout_profile,
                    )
                except Exception as exc:
                    if isinstance(exc, ProviderUnavailableError):
                        raise
                    logger.warning(
                        "[STRUCTURED_INVOKE] Native structured invoke failed; falling back to JSON path. provider=%s schema=%s error=%s",
                        preferred_provider,
                        schema.__name__,
                        exc,
                    )

        raw_response = await ainvoke_with_failover(
            _prepare_json_runtime_llm(llm),
            _augment_payload_for_json(schema, payload),
            tier=tier,
            provider=preferred_provider,
            failover_mode=failover_mode,
            on_primary=_prepare_json_runtime_llm,
            on_fallback=_prepare_json_runtime_llm,
            on_switch=on_switch,
            on_failover=on_failover,
            primary_timeout=primary_timeout,
            timeout_profile=effective_timeout_profile,
        )
        return _parse_json_response(schema, raw_response)
