"""OpenAI-compatible/native streaming helpers extracted from the graph shell."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Optional

from app.core import config as app_config
from app.core.config import settings
from app.engine.openai_compatible_credentials import (
    resolve_openai_api_key,
    resolve_openai_base_url,
    resolve_openrouter_api_key,
    resolve_openrouter_base_url,
)
from app.engine.reasoning import sanitize_visible_reasoning_text

logger = logging.getLogger(__name__)

# Zombie Tier-2 phrases that should be stripped from thinking content
_ZOMBIE_PHRASES = (
    "Chỗ khó của câu này không nằm ở",
    "Mình sẽ đi thẳng vào phần lõi",
    "Điều dễ sai nhất là nhầm giữa",
)


def _derive_code_stream_session_id_impl(
    *,
    runtime_context_base=None,
    state=None,
) -> str:
    """Build a stable Code Studio stream session id for one request lifecycle."""
    request_id = ""
    if runtime_context_base is not None:
        request_id = str(getattr(runtime_context_base, "request_id", "") or "").strip()
    if not request_id and state:
        context = state.get("context") or {}
        if isinstance(context, dict):
            request_id = str(context.get("request_id") or "").strip()
    if request_id:
        return f"vs-stream-{uuid.uuid5(uuid.NAMESPACE_URL, request_id).hex[:12]}"
    return f"vs-stream-{uuid.uuid4().hex[:12]}"


def _should_enable_real_code_streaming_impl(
    provider: str | None,
    *,
    llm: Any | None = None,
) -> bool:
    """Enable real Code Studio code-delta streaming only for proven-stable providers."""
    if not getattr(app_config.get_settings(), "enable_real_code_streaming", False):
        return False

    normalized = str(provider or "").strip().lower()
    model_name = str(getattr(llm, "_wiii_model_name", "") or "").strip().lower()

    if normalized in {"openai", "openrouter", "zhipu"}:
        return True

    return False


def _supports_native_answer_streaming_impl(provider: str | None) -> bool:
    normalized = str(provider or "").strip().lower()
    return normalized in {"google", "zhipu", "openai", "openrouter"}


def _flatten_langchain_content_impl(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                if item.strip():
                    parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            text = item.get("text") or item.get("content") or item.get("value")
            if text:
                parts.append(str(text))
        return "\n".join(part for part in parts if part)
    return str(content or "")


def _langchain_message_to_openai_payload_impl(
    message: Any,
    *,
    flatten_langchain_content,
) -> dict[str, Any]:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

    content = flatten_langchain_content(getattr(message, "content", ""))
    if isinstance(message, SystemMessage):
        return {"role": "system", "content": content}
    if isinstance(message, HumanMessage):
        return {"role": "user", "content": content}
    if isinstance(message, ToolMessage):
        payload = {"role": "tool", "content": content}
        tool_call_id = getattr(message, "tool_call_id", None)
        if tool_call_id:
            payload["tool_call_id"] = tool_call_id
        return payload
    if isinstance(message, AIMessage):
        payload: dict[str, Any] = {"role": "assistant", "content": content}
        tool_calls = getattr(message, "tool_calls", None) or []
        if tool_calls:
            payload["tool_calls"] = [
                {
                    "id": str(tool_call.get("id") or f"tc_{idx}"),
                    "type": "function",
                    "function": {
                        "name": str(tool_call.get("name") or ""),
                        "arguments": json.dumps(
                            tool_call.get("args") or {},
                            ensure_ascii=False,
                        ),
                    },
                }
                for idx, tool_call in enumerate(tool_calls)
                if tool_call.get("name")
            ]
        return payload
    role = getattr(message, "type", None) or getattr(message, "role", None) or "user"
    if role in {"human", "user"}:
        return {"role": "user", "content": content}
    if role == "system":
        return {"role": "system", "content": content}
    if role == "tool":
        payload = {"role": "tool", "content": content}
        tool_call_id = getattr(message, "tool_call_id", None)
        if tool_call_id:
            payload["tool_call_id"] = tool_call_id
        return payload
    return {"role": "assistant", "content": content}


def _create_openai_compatible_stream_client_impl(provider_name: str):
    from openai import AsyncOpenAI

    normalized = str(provider_name or "").strip().lower()
    if normalized == "google":
        if not settings.google_api_key:
            return None
        return AsyncOpenAI(
            api_key=settings.google_api_key,
            base_url=settings.google_openai_compat_url,
        )
    if normalized == "zhipu":
        if not settings.zhipu_api_key:
            return None
        return AsyncOpenAI(
            api_key=settings.zhipu_api_key,
            base_url=settings.zhipu_base_url,
        )
    if normalized == "openrouter":
        if not resolve_openrouter_api_key(settings):
            return None
        return AsyncOpenAI(
            api_key=resolve_openrouter_api_key(settings),
            base_url=resolve_openrouter_base_url(settings),
        )
    if normalized == "openai":
        if not resolve_openai_api_key(settings):
            return None
        return AsyncOpenAI(
            api_key=resolve_openai_api_key(settings),
            base_url=resolve_openai_base_url(settings),
        )
    return None


def _resolve_openai_stream_model_name_impl(
    llm: Any,
    provider_name: str,
    tier_key: str,
) -> str | None:
    tagged_provider = str(getattr(llm, "_wiii_provider_name", "") or "").strip().lower()
    tagged_model = (
        getattr(llm, "_wiii_model_name", None)
        or getattr(llm, "model_name", None)
        or getattr(llm, "model", None)
    )
    if tagged_provider == provider_name and tagged_model:
        return str(tagged_model)

    normalized = str(provider_name or "").strip().lower()
    if normalized == "google":
        if tier_key == "deep":
            return getattr(settings, "google_model_advanced", settings.google_model)
        return settings.google_model
    if normalized == "zhipu":
        if tier_key == "deep":
            return settings.zhipu_model_advanced
        return settings.zhipu_model
    if normalized == "openrouter":
        return settings.openai_model or "openai/gpt-oss-20b:free"
    if normalized == "openai":
        if tier_key == "deep":
            return settings.openai_model_advanced
        return settings.openai_model
    return None


def _extract_openai_delta_text_impl(delta: Any) -> tuple[str, str]:
    reasoning_parts: list[str] = []
    answer_parts: list[str] = []

    reasoning = getattr(delta, "reasoning_content", None)
    if isinstance(reasoning, str) and reasoning:
        reasoning_parts.append(reasoning)
    elif isinstance(reasoning, list):
        for item in reasoning:
            text = item.get("text") if isinstance(item, dict) else None
            if text:
                reasoning_parts.append(str(text))

    content = getattr(delta, "content", None)
    if isinstance(content, str) and content:
        answer_parts.append(content)
    elif isinstance(content, list):
        for item in content:
            text = item.get("text") if isinstance(item, dict) else None
            if text:
                answer_parts.append(str(text))

    return "".join(reasoning_parts), "".join(answer_parts)


def _extract_google_tagged_thinking_impl(
    text: str,
    *,
    state: dict[str, Any],
) -> tuple[str, str]:
    """Split streamed Google <thinking> tags out of visible answer text."""
    incoming = f"{state.get('pending', '')}{text or ''}"
    state["pending"] = ""
    if not incoming:
        return "", ""

    reasoning_parts: list[str] = []
    visible_parts: list[str] = []
    inside_thinking = bool(state.get("inside_thinking"))
    index = 0

    while index < len(incoming):
        if incoming[index] == "<":
            close_index = incoming.find(">", index + 1)
            if close_index < 0:
                state["pending"] = incoming[index:]
                break
            tag = incoming[index : close_index + 1].strip().lower()
            if tag == "<thinking>":
                inside_thinking = True
            elif tag == "</thinking>":
                inside_thinking = False
            else:
                target = reasoning_parts if inside_thinking else visible_parts
                target.append(incoming[index : close_index + 1])
            index = close_index + 1
            continue

        next_tag_index = incoming.find("<", index)
        if next_tag_index < 0:
            segment = incoming[index:]
            index = len(incoming)
        else:
            segment = incoming[index:next_tag_index]
            index = next_tag_index
        if not segment:
            continue
        target = reasoning_parts if inside_thinking else visible_parts
        target.append(segment)

    state["inside_thinking"] = inside_thinking
    return "".join(reasoning_parts), "".join(visible_parts)


async def _stream_openai_compatible_answer_with_route_impl(
    route,
    messages: list,
    push_event,
    *,
    node: str = "direct",
    thinking_stop_signal: Optional[asyncio.Event] = None,
    supports_native_answer_streaming,
    create_openai_compatible_stream_client,
    resolve_openai_stream_model_name,
    langchain_message_to_openai_payload,
    extract_openai_delta_text,
) -> tuple[object | None, bool]:
    from langchain_core.messages import AIMessage

    provider_name = str(route.provider or "").strip().lower()
    if not supports_native_answer_streaming(provider_name):
        return None, False

    client = create_openai_compatible_stream_client(provider_name)
    if client is None:
        return None, False

    tier_key = str(getattr(route.llm, "_wiii_tier_key", "") or "moderate").strip().lower()
    model_name = resolve_openai_stream_model_name(route.llm, provider_name, tier_key)
    if not model_name:
        return None, False

    request_messages = [
        langchain_message_to_openai_payload(message)
        for message in messages
    ]
    request_kwargs: dict[str, Any] = {
        "model": model_name,
        "messages": request_messages,
        "stream": True,
    }
    temperature = getattr(route.llm, "temperature", None)
    if temperature is not None:
        request_kwargs["temperature"] = temperature

    if provider_name == "openrouter":
        from app.engine.openrouter_routing import build_openrouter_extra_body

        extra_body = build_openrouter_extra_body(settings, primary_model=model_name)
        if extra_body:
            request_kwargs["extra_body"] = extra_body

    emitted_answer = ""
    thinking_closed = False
    emit_provider_reasoning = str(node or "").strip().lower() != "code_studio_agent"
    google_tag_state = {"inside_thinking": False, "pending": ""}
    reasoning_started = False

    try:
        stream = await client.chat.completions.create(**request_kwargs)
        async for chunk in stream:
            for choice in getattr(chunk, "choices", []) or []:
                delta = getattr(choice, "delta", None)
                if delta is None:
                    continue
                reasoning_delta, answer_delta = extract_openai_delta_text(delta)
                if answer_delta and str(node or "").strip().lower() != "code_studio_agent":
                    tagged_reasoning, cleaned_answer = _extract_google_tagged_thinking_impl(
                        answer_delta,
                        state=google_tag_state,
                    )
                    if tagged_reasoning:
                        reasoning_delta = f"{reasoning_delta}{tagged_reasoning}"
                    answer_delta = cleaned_answer
                if reasoning_delta and emit_provider_reasoning and not thinking_closed:
                    reasoning_delta = sanitize_visible_reasoning_text(reasoning_delta)
                    # Strip zombie boilerplate phrases
                    for zp in _ZOMBIE_PHRASES:
                        if zp in reasoning_delta:
                            reasoning_delta = reasoning_delta.replace(zp, "").strip()
                if reasoning_delta and emit_provider_reasoning and not thinking_closed and not reasoning_started:
                    await push_event({
                        "type": "thinking_start",
                        "content": "Suy nghĩ câu trả lời",
                        "node": node,
                    })
                    reasoning_started = True
                if reasoning_delta and emit_provider_reasoning and not thinking_closed:
                    await push_event({
                        "type": "thinking_delta",
                        "content": reasoning_delta,
                        "node": node,
                    })
                if not answer_delta:
                    continue
                if not thinking_closed:
                    if thinking_stop_signal is not None:
                        thinking_stop_signal.set()
                    if reasoning_started:
                        await push_event({
                            "type": "thinking_end",
                            "content": "",
                            "node": node,
                        })
                    thinking_closed = True
                await push_event({
                    "type": "answer_delta",
                    "content": answer_delta,
                    "node": node,
                })
                emitted_answer += answer_delta
        if emitted_answer:
            if not thinking_closed:
                if thinking_stop_signal is not None:
                    thinking_stop_signal.set()
                if reasoning_started:
                    await push_event({
                        "type": "thinking_end",
                        "content": "",
                        "node": node,
                    })
            return AIMessage(content=emitted_answer), True
    except Exception as exc:
        logger.warning(
            "[%s] Native OpenAI-compatible stream failed (%s/%s): %s",
            node.upper(),
            provider_name,
            model_name,
            exc,
            exc_info=True,
        )
        if emitted_answer:
            return AIMessage(content=emitted_answer), True
    logger.info(
        "[%s] Native stream result: provider=%s model=%s answer=%d chars",
        node.upper(),
        provider_name,
        model_name,
        len(emitted_answer),
    )
    return None, False
