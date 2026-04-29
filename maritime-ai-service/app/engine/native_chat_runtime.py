"""Native chat message helpers for Wiii runtime.

This module is intentionally independent from LangChain.  It accepts plain
OpenAI-compatible dictionaries and LangChain-like duck-typed objects so the
hot direct stream path can move off framework message classes first, while
legacy RAG/tool lanes migrate in smaller follow-up slices.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import Any


OPENAI_ROLES = {"system", "user", "assistant", "tool", "function"}
_VALID_TOOL_CHOICE_STRINGS = frozenset({"auto", "none", "required", "validated"})
_TOOL_CHOICE_ALIASES = {
    "any": "required",
    "tool": "required",
}


@dataclass(slots=True)
class NativeAssistantMessage:
    """Minimal assistant response object used by Wiii native runtime."""

    content: Any = ""
    additional_kwargs: dict[str, Any] = field(default_factory=dict)
    response_metadata: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    invalid_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage_metadata: dict[str, Any] | None = None
    id: str | None = None
    name: str | None = None
    type: str = "ai"


@dataclass(slots=True)
class NativeSystemMessage:
    """Framework-free system message with a LangChain-like surface."""

    content: Any = ""
    role: str = "system"
    type: str = "system"


@dataclass(slots=True)
class NativeUserMessage:
    """Framework-free user message with a LangChain-like surface."""

    content: Any = ""
    role: str = "user"
    type: str = "human"


@dataclass(slots=True)
class NativeToolMessage:
    """Framework-free tool-result message for native tool loops."""

    content: Any = ""
    tool_call_id: str = ""
    role: str = "tool"
    type: str = "tool"


@dataclass(slots=True)
class NativeChatModelHandle:
    """Provider/model metadata for native OpenAI-compatible calls."""

    _wiii_provider_name: str
    _wiii_model_name: str
    _wiii_tier_key: str = "moderate"
    temperature: float | None = None
    _wiii_requested_provider: str | None = None
    _wiii_native_route: bool = True
    _wiii_bound_tools: list[dict[str, Any]] = field(default_factory=list)
    _wiii_tool_choice: Any = None

    @property
    def model_name(self) -> str:
        return self._wiii_model_name

    def bind_tools(self, tools: list, **kwargs: Any) -> "NativeChatModelHandle":
        """Return a copy with OpenAI-compatible tools attached."""
        return replace(
            self,
            _wiii_bound_tools=tools_to_openai_schemas(tools),
            _wiii_tool_choice=normalize_tool_choice(kwargs.get("tool_choice")),
        )

    async def ainvoke(self, messages: list, **_kwargs: Any) -> NativeAssistantMessage:
        """Invoke the provider through Wiii's native OpenAI-compatible adapter."""
        from app.engine.multi_agent.openai_stream_runtime import (
            _ainvoke_openai_compatible_chat_impl,
        )

        return await _ainvoke_openai_compatible_chat_impl(self, messages)


def flatten_message_content(content: Any) -> str:
    """Flatten common text block shapes into OpenAI chat text content."""
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


def message_to_openai_payload(message: Any) -> dict[str, Any]:
    """Convert a native or LangChain-like message to an OpenAI chat payload."""
    raw = dict(message) if isinstance(message, dict) else None
    content = flatten_message_content(
        raw.get("content", "") if raw is not None else getattr(message, "content", "")
    )
    role = _normalize_role(
        raw.get("role") or raw.get("type") if raw is not None
        else getattr(message, "role", None) or getattr(message, "type", None)
    )

    payload: dict[str, Any] = {"role": role, "content": content}
    if role == "tool":
        tool_call_id = _get_value(message, raw, "tool_call_id")
        if tool_call_id:
            payload["tool_call_id"] = str(tool_call_id)
    if role == "function":
        name = _get_value(message, raw, "name")
        if name:
            payload["name"] = str(name)
    if role == "assistant":
        tool_calls = _normalize_tool_calls(_get_value(message, raw, "tool_calls") or [])
        if tool_calls:
            payload["tool_calls"] = tool_calls
    return payload


def make_assistant_message(
    content: Any,
    *,
    additional_kwargs: dict[str, Any] | None = None,
    response_metadata: dict[str, Any] | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    invalid_tool_calls: list[dict[str, Any]] | None = None,
    usage_metadata: dict[str, Any] | None = None,
    id: str | None = None,
    name: str | None = None,
) -> NativeAssistantMessage:
    """Create a framework-free assistant message with LangChain-like fields."""
    return NativeAssistantMessage(
        content=content,
        additional_kwargs=dict(additional_kwargs or {}),
        response_metadata=dict(response_metadata or {}),
        tool_calls=list(tool_calls or []),
        invalid_tool_calls=list(invalid_tool_calls or []),
        usage_metadata=usage_metadata,
        id=id,
        name=name,
    )


def make_system_message(content: Any) -> NativeSystemMessage:
    """Create a framework-free system message."""
    return NativeSystemMessage(content=content)


def make_user_message(content: Any) -> NativeUserMessage:
    """Create a framework-free user message."""
    return NativeUserMessage(content=content)


def make_tool_message(content: Any, *, tool_call_id: str) -> NativeToolMessage:
    """Create a framework-free tool result message."""
    return NativeToolMessage(
        content=content,
        tool_call_id=str(tool_call_id or ""),
    )


def tool_to_openai_schema(tool: Any) -> dict[str, Any] | None:
    """Serialize a Wiii/LangChain-like tool to OpenAI function-tool schema."""
    if isinstance(tool, dict) and tool.get("type") == "function":
        return dict(tool)

    name = str(getattr(tool, "name", "") or getattr(tool, "__name__", "") or "").strip()
    if not name:
        return None

    description = str(getattr(tool, "description", "") or "").strip()
    parameters: dict[str, Any] = {}
    args_schema = getattr(tool, "args_schema", None)
    if args_schema is not None:
        if hasattr(args_schema, "model_json_schema"):
            parameters = dict(args_schema.model_json_schema())
        elif hasattr(args_schema, "schema"):
            parameters = dict(args_schema.schema())
    elif isinstance(getattr(tool, "parameters", None), dict):
        parameters = dict(getattr(tool, "parameters"))
    elif isinstance(getattr(tool, "args", None), dict):
        parameters = {
            "type": "object",
            "properties": dict(getattr(tool, "args")),
        }

    if not parameters:
        parameters = {"type": "object", "properties": {}}

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


def tools_to_openai_schemas(tools: list | tuple | None) -> list[dict[str, Any]]:
    """Serialize a sequence of tools, dropping only unnameable entries."""
    schemas: list[dict[str, Any]] = []
    for tool in tools or []:
        schema = tool_to_openai_schema(tool)
        if schema is not None:
            schemas.append(schema)
    return schemas


def normalize_tool_choice(value: Any) -> Any:
    """Normalize Wiii tool-choice hints for OpenAI-compatible endpoints."""
    if not isinstance(value, str):
        return value
    normalized = value.strip()
    if not normalized:
        return None
    aliased = _TOOL_CHOICE_ALIASES.get(normalized, normalized)
    if aliased in _VALID_TOOL_CHOICE_STRINGS:
        return aliased
    return {"type": "function", "function": {"name": normalized}}


def openai_response_to_assistant_message(response: Any) -> NativeAssistantMessage:
    """Convert an OpenAI Chat Completions response into a native message."""
    choices = list(getattr(response, "choices", []) or [])
    choice = choices[0] if choices else None
    raw_message = getattr(choice, "message", None) if choice is not None else None
    content = getattr(raw_message, "content", "") or ""

    tool_calls: list[dict[str, Any]] = []
    for idx, tool_call in enumerate(getattr(raw_message, "tool_calls", []) or []):
        function = getattr(tool_call, "function", None)
        name = str(getattr(function, "name", "") or "").strip()
        if not name:
            continue
        raw_args = getattr(function, "arguments", None)
        args: Any = {}
        if isinstance(raw_args, str) and raw_args.strip():
            try:
                args = json.loads(raw_args)
            except Exception:
                args = raw_args
        elif raw_args is not None:
            args = raw_args
        tool_calls.append({
            "id": str(getattr(tool_call, "id", "") or f"call_{idx}"),
            "name": name,
            "args": args if isinstance(args, dict) else {"_raw": str(args)},
        })

    usage = getattr(response, "usage", None)
    if hasattr(usage, "model_dump"):
        usage_metadata = usage.model_dump()
    elif isinstance(usage, dict):
        usage_metadata = dict(usage)
    else:
        usage_metadata = None

    response_metadata = {
        "model": getattr(response, "model", None),
        "finish_reason": getattr(choice, "finish_reason", None) if choice is not None else None,
    }
    return make_assistant_message(
        content,
        tool_calls=tool_calls,
        response_metadata={
            key: value for key, value in response_metadata.items() if value is not None
        },
        usage_metadata=usage_metadata,
    )


def _get_value(message: Any, raw: dict[str, Any] | None, key: str) -> Any:
    if raw is not None:
        return raw.get(key)
    return getattr(message, key, None)


def _normalize_role(raw_role: Any) -> str:
    role = str(raw_role or "").strip().lower()
    if role in OPENAI_ROLES:
        return role
    if role in {"human", "chatmessage", "user_message"}:
        return "user"
    if role in {"ai", "ai_message", "assistant_message"}:
        return "assistant"
    if role in {"system_message"}:
        return "system"
    if role in {"tool_message"}:
        return "tool"
    return "user"


def _normalize_tool_calls(tool_calls: Any) -> list[dict[str, Any]]:
    if not isinstance(tool_calls, list):
        return []

    normalized: list[dict[str, Any]] = []
    for idx, tool_call in enumerate(tool_calls):
        raw = dict(tool_call) if isinstance(tool_call, dict) else None
        name = _get_value(tool_call, raw, "name")
        if not name and raw:
            function = raw.get("function") or {}
            if isinstance(function, dict):
                name = function.get("name")
        if not name:
            continue

        arguments = _get_value(tool_call, raw, "args")
        if arguments is None and raw:
            function = raw.get("function") or {}
            if isinstance(function, dict):
                arguments = function.get("arguments")
        if isinstance(arguments, str):
            arguments_json = arguments
        else:
            arguments_json = json.dumps(arguments or {}, ensure_ascii=False)

        normalized.append({
            "id": str(_get_value(tool_call, raw, "id") or f"tc_{idx}"),
            "type": "function",
            "function": {
                "name": str(name),
                "arguments": arguments_json,
            },
        })
    return normalized
