"""Phase 5 session event log — Runtime Migration #207.

Locks in the in-memory backend contract: monotonic seq, org filtering,
dict-payload immutability, since_seq replay window.
"""

from __future__ import annotations

import pytest

from app.engine.runtime.session_event_log import (
    InMemorySessionEventLog,
    SessionEvent,
    get_session_event_log,
)


@pytest.fixture
def log() -> InMemorySessionEventLog:
    return InMemorySessionEventLog()


# ── append ──

async def test_append_assigns_monotonic_seq_per_session(log):
    e1 = await log.append(session_id="s1", event_type="user_message", payload={"text": "hi"})
    e2 = await log.append(session_id="s1", event_type="assistant_message", payload={"text": "hello"})
    e3 = await log.append(session_id="s2", event_type="user_message", payload={"text": "x"})
    assert e1.seq == 1
    assert e2.seq == 2
    assert e3.seq == 1  # different session, fresh counter


async def test_append_returns_immutable_event(log):
    payload = {"q": "x"}
    event = await log.append(session_id="s", event_type="tool_call", payload=payload)
    assert isinstance(event, SessionEvent)
    payload["q"] = "mutated"
    assert event.payload == {"q": "x"}  # snapshot, not aliased


async def test_append_records_org_id_when_supplied(log):
    event = await log.append(
        session_id="s", event_type="user_message", payload={}, org_id="org-1"
    )
    assert event.org_id == "org-1"


# ── get_events ──

async def test_get_events_returns_in_append_order(log):
    await log.append(session_id="s", event_type="user_message", payload={"i": 1})
    await log.append(session_id="s", event_type="user_message", payload={"i": 2})
    await log.append(session_id="s", event_type="user_message", payload={"i": 3})
    events = await log.get_events(session_id="s")
    assert [e.payload["i"] for e in events] == [1, 2, 3]


async def test_get_events_unknown_session_returns_empty(log):
    assert await log.get_events(session_id="missing") == []


async def test_get_events_since_seq_filters_window(log):
    await log.append(session_id="s", event_type="x", payload={"i": 1})
    await log.append(session_id="s", event_type="x", payload={"i": 2})
    await log.append(session_id="s", event_type="x", payload={"i": 3})
    events = await log.get_events(session_id="s", since_seq=1)
    assert [e.seq for e in events] == [2, 3]


async def test_get_events_filters_by_org(log):
    await log.append(session_id="s", event_type="x", payload={}, org_id="A")
    await log.append(session_id="s", event_type="x", payload={}, org_id="B")
    await log.append(session_id="s", event_type="x", payload={}, org_id="A")
    a_events = await log.get_events(session_id="s", org_id="A")
    assert all(e.org_id == "A" for e in a_events)
    assert len(a_events) == 2


# ── latest_seq ──

async def test_latest_seq_zero_for_unknown_session(log):
    assert await log.latest_seq(session_id="missing") == 0


async def test_latest_seq_tracks_global_seq_without_org(log):
    await log.append(session_id="s", event_type="x", payload={})
    await log.append(session_id="s", event_type="x", payload={})
    assert await log.latest_seq(session_id="s") == 2


async def test_latest_seq_respects_org_filter(log):
    await log.append(session_id="s", event_type="x", payload={}, org_id="A")
    await log.append(session_id="s", event_type="x", payload={}, org_id="B")
    await log.append(session_id="s", event_type="x", payload={}, org_id="A")
    assert await log.latest_seq(session_id="s", org_id="A") == 3
    assert await log.latest_seq(session_id="s", org_id="B") == 2
    assert await log.latest_seq(session_id="s", org_id="C") == 0


# ── singleton ──

def test_get_session_event_log_returns_singleton():
    a = get_session_event_log()
    b = get_session_event_log()
    assert a is b


# ── concurrency safety ──

async def test_concurrent_appends_preserve_monotonic_seq(log):
    import asyncio

    async def write(idx: int) -> SessionEvent:
        return await log.append(
            session_id="s", event_type="x", payload={"i": idx}
        )

    events = await asyncio.gather(*(write(i) for i in range(20)))
    seqs = sorted(e.seq for e in events)
    assert seqs == list(range(1, 21))
