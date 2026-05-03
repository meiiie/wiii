"""Phase 4 edge protocol adapters — Runtime Migration #207.

Locks in the wire-shape → ``TurnRequest`` contract for both adapters
shipped in this phase.
"""

from __future__ import annotations

from app.engine.messages import Message
from app.engine.runtime.adapters import (
    openai_chat_completions_to_turn_request,
    wiii_chat_request_to_turn_request,
)


# ── Wiii native adapter ──

def test_wiii_native_minimum_request():
    req = wiii_chat_request_to_turn_request(
        message="Hi",
        user_id="u1",
        session_id="s1",
    )
    assert req.user_id == "u1"
    assert req.session_id == "s1"
    assert req.role == "student"
    assert len(req.messages) == 1
    assert req.messages[0].role == "user"
    assert req.messages[0].content == "Hi"
    assert req.requested_streaming is False


def test_wiii_native_appends_message_after_history():
    history = [Message(role="user", content="prev"), Message(role="assistant", content="ack")]
    req = wiii_chat_request_to_turn_request(
        message="next", user_id="u1", session_id="s1", history=history
    )
    assert [m.content for m in req.messages] == ["prev", "ack", "next"]


def test_wiii_native_passes_streaming_and_capabilities():
    req = wiii_chat_request_to_turn_request(
        message="Hi",
        user_id="u1",
        session_id="s1",
        requested_streaming=True,
        requested_capabilities=["tools"],
        metadata={"preferred_provider": "google"},
    )
    assert req.requested_streaming is True
    assert "tools" in req.requested_capabilities
    assert req.metadata["preferred_provider"] == "google"


# ── OpenAI Chat Completions adapter ──

def test_openai_compat_basic_text_request():
    body = {
        "model": "wiii-default",
        "messages": [
            {"role": "system", "content": "You are Wiii."},
            {"role": "user", "content": "Hi"},
        ],
    }
    req = openai_chat_completions_to_turn_request(
        body, user_id="u1", session_id="s1"
    )
    assert [m.role for m in req.messages] == ["system", "user"]
    assert req.metadata["openai_model"] == "wiii-default"
    assert req.requested_streaming is False
    assert req.requested_capabilities == []


def test_openai_compat_streaming_flag():
    body = {"model": "x", "messages": [{"role": "user", "content": "hi"}], "stream": True}
    req = openai_chat_completions_to_turn_request(body, user_id="u", session_id="s")
    assert req.requested_streaming is True


def test_openai_compat_tools_capability():
    body = {
        "model": "x",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [{"type": "function", "function": {"name": "search"}}],
    }
    req = openai_chat_completions_to_turn_request(body, user_id="u", session_id="s")
    assert "tools" in req.requested_capabilities


def test_openai_compat_structured_output_via_response_format():
    body = {
        "model": "x",
        "messages": [{"role": "user", "content": "hi"}],
        "response_format": {"type": "json_object"},
    }
    req = openai_chat_completions_to_turn_request(body, user_id="u", session_id="s")
    assert "structured_output" in req.requested_capabilities


def test_openai_compat_vision_block_detection():
    body = {
        "model": "x",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "what is this?"},
                    {"type": "image_url", "image_url": {"url": "data:..."}},
                ],
            }
        ],
    }
    req = openai_chat_completions_to_turn_request(body, user_id="u", session_id="s")
    assert "vision" in req.requested_capabilities
    # Multimodal content collapses to text for the canonical Message; raw
    # body is preserved in metadata for downstream vision-aware code.
    assert req.messages[0].content == "what is this?"
    assert req.metadata["original_messages"] == body["messages"]


def test_openai_compat_assistant_tool_calls_round_trip():
    body = {
        "model": "x",
        "messages": [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "search", "arguments": '{"q": "x"}'},
                    }
                ],
            }
        ],
    }
    req = openai_chat_completions_to_turn_request(body, user_id="u", session_id="s")
    assert req.messages[0].tool_calls is not None
    assert req.messages[0].tool_calls[0].id == "c1"
    assert req.messages[0].tool_calls[0].arguments == {"q": "x"}


def test_openai_compat_tool_role_message_carries_tool_call_id():
    body = {
        "model": "x",
        "messages": [
            {"role": "tool", "content": "result", "tool_call_id": "c1"}
        ],
    }
    req = openai_chat_completions_to_turn_request(body, user_id="u", session_id="s")
    assert req.messages[0].role == "tool"
    assert req.messages[0].tool_call_id == "c1"


def test_openai_compat_unknown_role_falls_back_to_user():
    body = {"model": "x", "messages": [{"role": "function", "content": "x"}]}
    req = openai_chat_completions_to_turn_request(body, user_id="u", session_id="s")
    assert req.messages[0].role == "user"


def test_openai_compat_temperature_and_max_tokens_into_metadata():
    body = {
        "model": "x",
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0.3,
        "max_tokens": 256,
    }
    req = openai_chat_completions_to_turn_request(body, user_id="u", session_id="s")
    assert req.metadata["temperature"] == 0.3
    assert req.metadata["max_tokens"] == 256
