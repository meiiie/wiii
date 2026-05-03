"""Phase 11a session wake() — Runtime Migration #207.

Locks the conversation-reconstruction contract: replay an InMemory or
Postgres event log into a ``WakeState`` ready for the next turn. Same
contract drives both backends — tests use the in-memory log for speed.
"""

from __future__ import annotations

import pytest

from app.engine.runtime.session_event_log import InMemorySessionEventLog
from app.engine.runtime.session_wake import WakeState, wake


@pytest.fixture
def log() -> InMemorySessionEventLog:
    return InMemorySessionEventLog()


# ── empty / unknown ──

async def test_wake_empty_session_returns_blank_state(log):
    state = await wake(session_id="unknown", log=log)
    assert isinstance(state, WakeState)
    assert state.messages == []
    assert state.pending_tool_calls == []
    assert state.latest_seq == 0
    assert state.event_count == 0


async def test_wake_skips_unknown_event_types(log):
    await log.append(
        session_id="s", event_type="status_ping", payload={"ok": True}
    )
    await log.append(
        session_id="s", event_type="user_message", payload={"text": "hi"}
    )
    state = await wake(session_id="s", log=log)
    assert [m.role for m in state.messages] == ["user"]
    assert state.event_count == 2  # both visited
    assert state.latest_seq == 2


# ── basic message replay ──

async def test_wake_user_then_assistant(log):
    await log.append(
        session_id="s", event_type="user_message", payload={"text": "hello"}
    )
    await log.append(
        session_id="s",
        event_type="assistant_message",
        payload={"text": "world"},
    )
    state = await wake(session_id="s", log=log)
    assert [m.role for m in state.messages] == ["user", "assistant"]
    assert state.messages[0].content == "hello"
    assert state.messages[1].content == "world"
    assert state.latest_seq == 2
    assert state.pending_tool_calls == []


async def test_wake_system_message_round_trips(log):
    await log.append(
        session_id="s",
        event_type="system_message",
        payload={"text": "you are a maritime tutor"},
    )
    state = await wake(session_id="s", log=log)
    assert state.messages[0].role == "system"
    assert state.messages[0].content == "you are a maritime tutor"


async def test_wake_accepts_legacy_content_alias(log):
    """Older recorders may have written ``content`` instead of ``text``."""
    await log.append(
        session_id="s",
        event_type="user_message",
        payload={"content": "legacy form"},
    )
    state = await wake(session_id="s", log=log)
    assert state.messages[0].content == "legacy form"


async def test_wake_drops_messages_with_empty_text(log):
    """Empty payload → not a real user/assistant turn; skip."""
    await log.append(
        session_id="s", event_type="user_message", payload={"text": ""}
    )
    await log.append(
        session_id="s", event_type="user_message", payload={"text": "real"}
    )
    state = await wake(session_id="s", log=log)
    assert [m.content for m in state.messages] == ["real"]


# ── tool calls ──

async def test_wake_assistant_with_tool_calls_marks_pending(log):
    await log.append(
        session_id="s",
        event_type="assistant_message",
        payload={
            "text": "let me check",
            "tool_calls": [
                {"id": "call_1", "name": "search", "arguments": {"q": "x"}}
            ],
        },
    )
    state = await wake(session_id="s", log=log)
    assert state.messages[0].role == "assistant"
    assert state.messages[0].tool_calls is not None
    assert state.messages[0].tool_calls[0].name == "search"
    assert len(state.pending_tool_calls) == 1
    assert state.pending_tool_calls[0].id == "call_1"


async def test_wake_tool_result_clears_pending_call(log):
    await log.append(
        session_id="s",
        event_type="assistant_message",
        payload={
            "text": "let me check",
            "tool_calls": [
                {"id": "call_1", "name": "search", "arguments": {"q": "x"}}
            ],
        },
    )
    await log.append(
        session_id="s",
        event_type="tool_result",
        payload={"tool_call_id": "call_1", "content": "result-text"},
    )
    state = await wake(session_id="s", log=log)
    assert [m.role for m in state.messages] == ["assistant", "tool"]
    assert state.messages[1].tool_call_id == "call_1"
    assert state.messages[1].content == "result-text"
    assert state.pending_tool_calls == []


async def test_wake_partial_tool_results_keeps_remaining_pending(log):
    """Two tool_calls, only one resolves → the other stays pending."""
    await log.append(
        session_id="s",
        event_type="assistant_message",
        payload={
            "text": "checking two things",
            "tool_calls": [
                {"id": "a", "name": "f", "arguments": {}},
                {"id": "b", "name": "g", "arguments": {}},
            ],
        },
    )
    await log.append(
        session_id="s",
        event_type="tool_result",
        payload={"tool_call_id": "a", "content": "ok"},
    )
    state = await wake(session_id="s", log=log)
    pending_ids = {c.id for c in state.pending_tool_calls}
    assert pending_ids == {"b"}


async def test_wake_new_assistant_turn_replaces_pending(log):
    """Only the *most recent* assistant turn's pending calls matter."""
    await log.append(
        session_id="s",
        event_type="assistant_message",
        payload={
            "text": "first call",
            "tool_calls": [{"id": "old", "name": "f", "arguments": {}}],
        },
    )
    # second turn: different unresolved call.
    await log.append(
        session_id="s",
        event_type="assistant_message",
        payload={
            "text": "second call",
            "tool_calls": [{"id": "new", "name": "g", "arguments": {}}],
        },
    )
    state = await wake(session_id="s", log=log)
    pending_ids = {c.id for c in state.pending_tool_calls}
    assert pending_ids == {"new"}


# ── filters ──

async def test_wake_since_seq_replays_window_only(log):
    await log.append(
        session_id="s", event_type="user_message", payload={"text": "old"}
    )
    await log.append(
        session_id="s", event_type="user_message", payload={"text": "new"}
    )
    state = await wake(session_id="s", since_seq=1, log=log)
    assert [m.content for m in state.messages] == ["new"]
    assert state.latest_seq == 2


async def test_wake_org_id_filter(log):
    await log.append(
        session_id="s", event_type="user_message", payload={"text": "A"}, org_id="A"
    )
    await log.append(
        session_id="s", event_type="user_message", payload={"text": "B"}, org_id="B"
    )
    state = await wake(session_id="s", org_id="A", log=log)
    assert [m.content for m in state.messages] == ["A"]


# ── defensive parsing ──

async def test_wake_ignores_malformed_tool_call_entries(log):
    await log.append(
        session_id="s",
        event_type="assistant_message",
        payload={
            "text": "mixed list",
            "tool_calls": [
                "not-a-dict",
                {"id": "ok", "name": "f", "arguments": {}},
                {"missing": "id-and-name"},  # validation will fail
            ],
        },
    )
    state = await wake(session_id="s", log=log)
    assert state.messages[0].tool_calls is not None
    assert [c.id for c in state.messages[0].tool_calls] == ["ok"]


async def test_wake_handles_non_dict_payload_gracefully(log):
    """The log layer enforces dict payloads, but the parser should not
    rely on that — guard against future event sources."""
    import dataclasses

    await log.append(
        session_id="s", event_type="user_message", payload={"text": "ok"}
    )
    # Sneak in a non-dict payload directly via internal API.
    state_obj = log._sessions["s"]
    bad_event = dataclasses.replace(state_obj.events[0], payload="not-a-dict")
    state_obj.events[0] = bad_event
    state = await wake(session_id="s", log=log)
    # Bad payload is treated as empty; no crash.
    assert state.messages == []
