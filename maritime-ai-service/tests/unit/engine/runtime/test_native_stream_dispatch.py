"""Phase 30 native stream dispatch — Runtime Migration #207.

Locks the contract:
- All chunks pass through unchanged (SSE wire shape preserved).
- user_message event recorded BEFORE first chunk.
- assistant_message event recorded AFTER stream exhausts, with
  accumulated answer text.
- Status=success on clean exit, status=error on inner generator raise.
- Metrics + lifecycle hooks fire in the right order.
- _extract_answer_token parses ``event: answer`` SSE chunks.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import AsyncGenerator

import pytest

from app.engine.runtime import runtime_metrics as rm
from app.engine.runtime.lifecycle import HookPoint, get_lifecycle
from app.engine.runtime.native_stream_dispatch import (
    _extract_answer_token,
    native_stream_dispatch,
)
from app.engine.runtime.session_event_log import InMemorySessionEventLog


@pytest.fixture(autouse=True)
def reset_state():
    rm._reset_for_tests()
    get_lifecycle().reset()
    yield
    rm._reset_for_tests()
    get_lifecycle().reset()


def _make_request(
    *, session_id="stream-1", user_id="user-1", message="hello", org_id="org-A"
):
    return SimpleNamespace(
        user_id=user_id,
        session_id=session_id,
        message=message,
        organization_id=org_id,
        role=SimpleNamespace(value="student"),
        domain_id="maritime",
    )


async def _make_sse_generator(chunks: list[str]) -> AsyncGenerator[str, None]:
    for chunk in chunks:
        yield chunk


# ── _extract_answer_token ──

def test_extract_answer_token_parses_answer_event():
    chunk = 'event: answer\ndata: {"content": "hello"}\n\n'
    assert _extract_answer_token(chunk) == "hello"


def test_extract_answer_token_returns_none_for_other_events():
    assert _extract_answer_token('event: status\ndata: {"step": "x"}\n\n') is None
    assert _extract_answer_token('event: done\ndata: {}\n\n') is None
    assert _extract_answer_token('event: sources\ndata: {"sources": []}\n\n') is None


def test_extract_answer_token_handles_malformed_json():
    assert _extract_answer_token('event: answer\ndata: not-json\n\n') is None


def test_extract_answer_token_handles_missing_content():
    assert _extract_answer_token('event: answer\ndata: {"foo": "bar"}\n\n') is None


def test_extract_answer_token_handles_empty_content():
    assert _extract_answer_token('event: answer\ndata: {"content": ""}\n\n') is None


def test_extract_answer_token_returns_none_for_non_string():
    assert _extract_answer_token(None) is None  # type: ignore[arg-type]
    assert _extract_answer_token(12345) is None  # type: ignore[arg-type]


# ── pass-through ──

async def test_all_chunks_pass_through_unchanged():
    log = InMemorySessionEventLog()
    chunks = [
        "retry: 3000\n\n",
        "event: status\ndata: {\"step\": \"prep\"}\n\n",
        'event: answer\ndata: {"content": "hello"}\n\n',
        'event: answer\ndata: {"content": " world"}\n\n',
        "event: done\ndata: {}\n\n",
    ]
    inner = _make_sse_generator(chunks)
    wrapped = native_stream_dispatch(_make_request(), inner, event_log=log)
    received = [c async for c in wrapped]
    assert received == chunks  # exact pass-through, no re-encoding


# ── durable log ──

async def test_user_message_event_recorded_before_assistant():
    log = InMemorySessionEventLog()
    chunks = ['event: answer\ndata: {"content": "hi"}\n\n', "event: done\ndata: {}\n\n"]
    wrapped = native_stream_dispatch(
        _make_request(message="trigger"),
        _make_sse_generator(chunks),
        event_log=log,
    )
    async for _ in wrapped:
        pass
    events = await log.get_events(session_id="stream-1")
    assert [e.event_type for e in events] == [
        "user_message",
        "assistant_message",
    ]
    assert events[0].payload["text"] == "trigger"
    assert events[0].payload["transport"] == "stream/v3"


async def test_assistant_text_accumulated_from_answer_chunks():
    log = InMemorySessionEventLog()
    chunks = [
        "event: status\ndata: {\"step\": \"prep\"}\n\n",
        'event: answer\ndata: {"content": "Hello"}\n\n',
        'event: answer\ndata: {"content": " "}\n\n',
        'event: answer\ndata: {"content": "Wiii"}\n\n',
        "event: done\ndata: {}\n\n",
    ]
    wrapped = native_stream_dispatch(
        _make_request(), _make_sse_generator(chunks), event_log=log
    )
    async for _ in wrapped:
        pass
    events = await log.get_events(session_id="stream-1")
    assistant = events[1].payload
    assert assistant["text"] == "Hello Wiii"
    assert assistant["status"] == "success"
    assert assistant["transport"] == "stream/v3"


async def test_org_id_propagated_to_both_events():
    log = InMemorySessionEventLog()
    chunks = ['event: answer\ndata: {"content": "x"}\n\n']
    wrapped = native_stream_dispatch(
        _make_request(org_id="org-B"),
        _make_sse_generator(chunks),
        event_log=log,
    )
    async for _ in wrapped:
        pass
    events_b = await log.get_events(session_id="stream-1", org_id="org-B")
    assert len(events_b) == 2
    events_other = await log.get_events(session_id="stream-1", org_id="org-other")
    assert events_other == []


# ── error path ──

async def test_inner_generator_raise_records_error_assistant_event():
    log = InMemorySessionEventLog()

    async def bad_gen() -> AsyncGenerator[str, None]:
        yield 'event: answer\ndata: {"content": "partial"}\n\n'
        raise RuntimeError("provider hung up")

    wrapped = native_stream_dispatch(_make_request(), bad_gen(), event_log=log)
    received = []
    with pytest.raises(RuntimeError, match="provider hung up"):
        async for chunk in wrapped:
            received.append(chunk)
    # First chunk passed through before the raise.
    assert received == ['event: answer\ndata: {"content": "partial"}\n\n']
    events = await log.get_events(session_id="stream-1")
    assert [e.event_type for e in events] == [
        "user_message",
        "assistant_message",
    ]
    assistant = events[1].payload
    assert assistant["status"] == "error"
    assert "provider hung up" in assistant["error"]
    # Even on error, the partially-accumulated text is preserved.
    assert assistant["text"] == "partial"


# ── metrics ──

async def test_success_run_records_metrics():
    log = InMemorySessionEventLog()
    chunks = ['event: answer\ndata: {"content": "ok"}\n\n']
    wrapped = native_stream_dispatch(
        _make_request(), _make_sse_generator(chunks), event_log=log
    )
    async for _ in wrapped:
        pass
    snap = rm.snapshot()
    assert (
        snap["counters"]["runtime.native_stream_dispatch.runs"][
            (("status", "success"),)
        ]
        == 1
    )
    durations = snap["histograms"][
        "runtime.native_stream_dispatch.duration_ms"
    ][(("status", "success"),)]
    assert len(durations) == 1
    assert durations[0] >= 0


async def test_error_run_records_error_metric():
    log = InMemorySessionEventLog()

    async def bad_gen():
        if False:
            yield ""
        raise RuntimeError("boom")

    wrapped = native_stream_dispatch(_make_request(), bad_gen(), event_log=log)
    with pytest.raises(RuntimeError):
        async for _ in wrapped:
            pass
    snap = rm.snapshot()
    assert (
        snap["counters"]["runtime.native_stream_dispatch.runs"][
            (("status", "error"),)
        ]
        == 1
    )


# ── lifecycle hooks ──

async def test_lifecycle_fires_run_start_then_run_end_on_success():
    log = InMemorySessionEventLog()
    captured: list[HookPoint] = []
    lc = get_lifecycle()

    async def on_start(payload):
        captured.append(HookPoint.ON_RUN_START)

    async def on_end(payload):
        captured.append(HookPoint.ON_RUN_END)

    lc.register(HookPoint.ON_RUN_START, on_start)
    lc.register(HookPoint.ON_RUN_END, on_end)

    chunks = ['event: answer\ndata: {"content": "ok"}\n\n']
    wrapped = native_stream_dispatch(
        _make_request(), _make_sse_generator(chunks), event_log=log
    )
    async for _ in wrapped:
        pass
    assert captured == [HookPoint.ON_RUN_START, HookPoint.ON_RUN_END]


async def test_lifecycle_fires_error_then_end_on_failure():
    log = InMemorySessionEventLog()
    captured: list[HookPoint] = []
    lc = get_lifecycle()

    async def record(point):
        async def hook(payload):
            captured.append(point)

        return hook

    lc.register(HookPoint.ON_RUN_START, await record(HookPoint.ON_RUN_START))
    lc.register(HookPoint.ON_RUN_ERROR, await record(HookPoint.ON_RUN_ERROR))
    lc.register(HookPoint.ON_RUN_END, await record(HookPoint.ON_RUN_END))

    async def bad_gen():
        if False:
            yield ""
        raise RuntimeError("nope")

    wrapped = native_stream_dispatch(_make_request(), bad_gen(), event_log=log)
    with pytest.raises(RuntimeError):
        async for _ in wrapped:
            pass
    assert captured == [
        HookPoint.ON_RUN_START,
        HookPoint.ON_RUN_ERROR,
        HookPoint.ON_RUN_END,
    ]


# ── session_id fallback ──

async def test_session_id_falls_back_when_request_omits_it():
    log = InMemorySessionEventLog()
    request = _make_request(session_id=None, user_id="bob")
    chunks = ['event: answer\ndata: {"content": "x"}\n\n']
    wrapped = native_stream_dispatch(
        request, _make_sse_generator(chunks), event_log=log
    )
    async for _ in wrapped:
        pass
    events = await log.get_events(session_id="native-stream::bob")
    assert len(events) == 2
