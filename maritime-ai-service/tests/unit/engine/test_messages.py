"""Phase 1 native message types + provider adapters — Runtime Migration #207.

Locks in the contract for ``Message`` / ``ToolCall`` / ``ToolResult`` and the
three provider dict adapters. Anything that consumes these types downstream
relies on this exact shape.
"""

from __future__ import annotations

import json

import pytest

from app.engine.messages import Message, ToolCall, ToolResult
from app.engine.messages_adapters import (
    to_anthropic_dict,
    to_gemini_dict,
    to_openai_dict,
)


# ── Message model ──

def test_message_defaults_empty_content():
    msg = Message(role="user")
    assert msg.role == "user"
    assert msg.content == ""
    assert msg.tool_calls is None
    assert msg.tool_call_id is None
    assert msg.name is None


def test_message_role_must_be_known_literal():
    with pytest.raises(Exception):
        Message(role="invalid")  # type: ignore[arg-type]


def test_tool_call_arguments_default_to_empty_dict():
    tc = ToolCall(id="call_1", name="search")
    assert tc.arguments == {}


def test_tool_result_is_error_default_false():
    res = ToolResult(tool_call_id="call_1", content="ok")
    assert res.is_error is False


# ── to_openai_dict ──

def test_to_openai_dict_minimal_user():
    out = to_openai_dict(Message(role="user", content="hello"))
    assert out == {"role": "user", "content": "hello"}


def test_to_openai_dict_assistant_with_tool_calls():
    msg = Message(
        role="assistant",
        content="",
        tool_calls=[ToolCall(id="c1", name="search", arguments={"q": "vịnh hạ long"})],
    )
    out = to_openai_dict(msg)
    assert out["role"] == "assistant"
    assert out["tool_calls"][0]["id"] == "c1"
    assert out["tool_calls"][0]["type"] == "function"
    assert out["tool_calls"][0]["function"]["name"] == "search"
    parsed_args = json.loads(out["tool_calls"][0]["function"]["arguments"])
    assert parsed_args == {"q": "vịnh hạ long"}


def test_to_openai_dict_tool_role_carries_tool_call_id():
    msg = Message(role="tool", content="result", tool_call_id="c1")
    out = to_openai_dict(msg)
    assert out["role"] == "tool"
    assert out["tool_call_id"] == "c1"


def test_to_openai_dict_function_name_passthrough():
    msg = Message(role="tool", content="r", tool_call_id="c1", name="search")
    out = to_openai_dict(msg)
    assert out["name"] == "search"


# ── to_anthropic_dict ──

def test_to_anthropic_dict_user_passthrough():
    out = to_anthropic_dict(Message(role="user", content="hi"))
    assert out == {"role": "user", "content": "hi"}


def test_to_anthropic_dict_tool_role_becomes_user_block():
    out = to_anthropic_dict(Message(role="tool", content="r", tool_call_id="c1"))
    assert out["role"] == "user"
    assert out["content"][0]["type"] == "tool_result"
    assert out["content"][0]["tool_use_id"] == "c1"
    assert out["content"][0]["content"] == "r"
    assert out["content"][0]["is_error"] is False


def test_to_anthropic_dict_assistant_with_tool_calls_uses_typed_blocks():
    msg = Message(
        role="assistant",
        content="thinking out loud",
        tool_calls=[ToolCall(id="c1", name="search", arguments={"q": "x"})],
    )
    out = to_anthropic_dict(msg)
    assert out["role"] == "assistant"
    assert out["content"][0] == {"type": "text", "text": "thinking out loud"}
    assert out["content"][1]["type"] == "tool_use"
    assert out["content"][1]["id"] == "c1"
    assert out["content"][1]["input"] == {"q": "x"}


def test_to_anthropic_dict_assistant_only_tool_calls_no_text_block():
    msg = Message(
        role="assistant",
        content="",
        tool_calls=[ToolCall(id="c1", name="search")],
    )
    out = to_anthropic_dict(msg)
    assert all(block["type"] != "text" for block in out["content"])
    assert out["content"][0]["type"] == "tool_use"


# ── to_gemini_dict ──

def test_to_gemini_dict_matches_openai_shape():
    msg = Message(role="user", content="hello")
    assert to_gemini_dict(msg) == to_openai_dict(msg)
