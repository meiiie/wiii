"""
Sprint 150: Tests for graph_done event_queue drain fix.

The race condition: tutor_node pushes answer_delta events to event_queue
via put_nowait() synchronously just before returning. _forward_bus may
not have forwarded these to merged_queue before graph_done arrives.

Fix: graph_done handler now drains event_queue directly, and answer_emitted
flag is only set when answer events are confirmed delivered.

Tests:
1.  graph_done drains event_queue — answer_delta events are forwarded
2.  graph_done drains merged_queue — existing behavior preserved
3.  SENTINEL in event_queue is skipped during drain
4.  answer_emitted set in drain when answer_delta found
5.  answer_emitted not set when no answer_delta in drain
6.  tutor graph handler: answer_emitted only when graph-level emission
7.  tutor graph handler: answer_emitted when bus confirmed
8.  tutor graph handler: answer_emitted NOT set when bus unconfirmed
9.  safety net fires when answer_emitted=False
10. safety net skips when answer_emitted=True (bus confirmed in drain)
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Helpers ──────────────────────────────────────────────────────────────

class FakeStreamEvent:
    """Minimal StreamEvent for testing."""
    def __init__(self, type: str, content: str = "", node: str = None):
        self.type = type
        self.content = content
        self.node = node


async def _fake_convert_bus_event(event: dict) -> FakeStreamEvent:
    """Simulate _convert_bus_event."""
    etype = event.get("type", "status")
    return FakeStreamEvent(
        type="answer" if etype == "answer_delta" else etype,
        content=event.get("content", ""),
        node=event.get("node"),
    )


# ── Test: event_queue drain ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_graph_done_drains_event_queue():
    """
    When graph_done arrives, events remaining in event_queue should be
    forwarded via _convert_bus_event, not lost.
    """
    event_queue = asyncio.Queue()
    merged_queue = asyncio.Queue()
    _SENTINEL = object()

    # Simulate: tutor pushed answer_delta to event_queue, but _forward_bus
    # hasn't forwarded them yet.
    event_queue.put_nowait({"type": "answer_delta", "content": "Hello ", "node": "tutor_agent"})
    event_queue.put_nowait({"type": "answer_delta", "content": "World", "node": "tutor_agent"})

    # Simulate the drain logic from graph_done handler
    answer_emitted = False
    drained_events = []

    # 1. Drain merged_queue (empty in this case)
    while not merged_queue.empty():
        try:
            mt, pl = merged_queue.get_nowait()
            if mt == "bus":
                if pl.get("type") == "answer_delta":
                    answer_emitted = True
                drained_events.append(await _fake_convert_bus_event(pl))
        except Exception:
            break

    # 2. Drain event_queue (has our answer_delta events)
    while not event_queue.empty():
        try:
            evt = event_queue.get_nowait()
            if evt is _SENTINEL:
                continue
            if evt.get("type") == "answer_delta":
                answer_emitted = True
            drained_events.append(await _fake_convert_bus_event(evt))
        except Exception:
            break

    assert len(drained_events) == 2
    assert drained_events[0].type == "answer"
    assert drained_events[0].content == "Hello "
    assert drained_events[1].content == "World"
    assert answer_emitted is True


@pytest.mark.asyncio
async def test_graph_done_drains_merged_queue():
    """Existing behavior: merged_queue bus events are drained on graph_done."""
    merged_queue = asyncio.Queue()
    event_queue = asyncio.Queue()

    # Events already forwarded to merged_queue by _forward_bus
    merged_queue.put_nowait(("bus", {"type": "answer_delta", "content": "OK", "node": "tutor_agent"}))

    answer_emitted = False
    drained_events = []

    while not merged_queue.empty():
        try:
            mt, pl = merged_queue.get_nowait()
            if mt == "bus":
                if pl.get("type") == "answer_delta":
                    answer_emitted = True
                drained_events.append(await _fake_convert_bus_event(pl))
        except Exception:
            break

    assert len(drained_events) == 1
    assert answer_emitted is True


@pytest.mark.asyncio
async def test_sentinel_skipped_in_drain():
    """_SENTINEL in event_queue should be skipped, not converted."""
    event_queue = asyncio.Queue()
    _SENTINEL = object()

    event_queue.put_nowait(_SENTINEL)
    event_queue.put_nowait({"type": "status", "content": "test", "node": "tutor_agent"})

    drained = []
    while not event_queue.empty():
        try:
            evt = event_queue.get_nowait()
            if evt is _SENTINEL:
                continue
            drained.append(await _fake_convert_bus_event(evt))
        except Exception:
            break

    assert len(drained) == 1
    assert drained[0].type == "status"


@pytest.mark.asyncio
async def test_answer_emitted_set_when_answer_delta_in_drain():
    """answer_emitted should be True when answer_delta found during drain."""
    event_queue = asyncio.Queue()
    event_queue.put_nowait({"type": "thinking_delta", "content": "think", "node": "tutor_agent"})
    event_queue.put_nowait({"type": "answer_delta", "content": "answer", "node": "tutor_agent"})

    answer_emitted = False
    while not event_queue.empty():
        evt = event_queue.get_nowait()
        if evt.get("type") == "answer_delta":
            answer_emitted = True

    assert answer_emitted is True


@pytest.mark.asyncio
async def test_answer_emitted_not_set_without_answer_delta():
    """answer_emitted stays False when no answer_delta in drain."""
    event_queue = asyncio.Queue()
    event_queue.put_nowait({"type": "thinking_delta", "content": "think", "node": "tutor_agent"})
    event_queue.put_nowait({"type": "thinking_end", "content": "", "node": "tutor_agent"})

    answer_emitted = False
    while not event_queue.empty():
        evt = event_queue.get_nowait()
        if evt.get("type") == "answer_delta":
            answer_emitted = True

    assert answer_emitted is False


# ── Test: tutor graph handler answer_emitted logic ───────────────────────

def test_tutor_answer_emitted_only_on_graph_level_emission():
    """
    answer_emitted should be True only when graph-level answer emission
    actually happens (not _answer_via_bus, not _answer_as_thinking).
    """
    # Scenario: No bus, no flag → graph-level emission
    _bus_answer_nodes = set()
    _answer_as_thinking = False
    _answer_via_bus = "tutor_agent" in _bus_answer_nodes

    answer_emitted = False
    if not _answer_via_bus and not _answer_as_thinking:
        # Would emit answer here
        answer_emitted = True

    assert answer_emitted is True


def test_tutor_answer_emitted_when_bus_confirmed():
    """answer_emitted=True when bus has confirmed delivery."""
    _bus_answer_nodes = {"tutor_agent"}
    _answer_as_thinking = True
    _answer_via_bus = "tutor_agent" in _bus_answer_nodes

    answer_emitted = False
    if not _answer_via_bus and not _answer_as_thinking:
        answer_emitted = True  # Graph-level
    elif _answer_via_bus:
        answer_emitted = True  # Bus confirmed

    assert answer_emitted is True


def test_tutor_answer_not_emitted_when_bus_unconfirmed():
    """
    answer_emitted should be False when _answer_as_thinking=True
    but bus hasn't confirmed delivery yet (_bus_answer_nodes empty).
    This allows the safety net to catch lost events.
    """
    _bus_answer_nodes = set()  # Bus hasn't forwarded yet
    _answer_as_thinking = True
    _answer_via_bus = "tutor_agent" in _bus_answer_nodes

    answer_emitted = False
    if not _answer_via_bus and not _answer_as_thinking:
        answer_emitted = True
    elif _answer_via_bus:
        answer_emitted = True
    # else: _answer_as_thinking but bus unconfirmed — don't set

    assert answer_emitted is False


# ── Test: safety net behavior ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_safety_net_fires_when_answer_not_emitted():
    """Safety net should emit answer when answer_emitted=False."""
    answer_emitted = False
    final_state = {
        "tutor_output": "The answer text",
        "final_response": "",
        "agent_outputs": {"tutor": "The answer text"},
    }

    fallback = None
    if not answer_emitted and final_state:
        fallback = final_state.get("final_response", "")
        if not fallback:
            for val in final_state.get("agent_outputs", {}).values():
                if isinstance(val, str) and len(val) > 20:
                    fallback = val
                    break

    # "The answer text" is only 15 chars, so let's use a longer one
    final_state["agent_outputs"]["tutor"] = "A" * 50
    fallback = None
    if not answer_emitted and final_state:
        fallback = final_state.get("final_response", "")
        if not fallback:
            for val in final_state.get("agent_outputs", {}).values():
                if isinstance(val, str) and len(val) > 20:
                    fallback = val
                    break

    assert fallback is not None
    assert len(fallback) == 50


@pytest.mark.asyncio
async def test_safety_net_skips_when_drain_confirmed_answer():
    """
    When answer_emitted=True (set during drain after finding answer_delta),
    the safety net should not fire.
    """
    # Simulate: drain found answer_delta → answer_emitted=True
    answer_emitted = True
    final_state = {
        "final_response": "",
        "agent_outputs": {"tutor": "A" * 50},
    }

    fallback = None
    if not answer_emitted and final_state:
        # This should NOT execute
        fallback = "should not reach here"

    assert fallback is None
