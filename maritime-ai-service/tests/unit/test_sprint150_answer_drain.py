"""
Sprint 150+: tests for graph_done drain behavior with tutor answer suppression.

Current contract:
- tutor_agent may stream thinking/tool traces through the bus
- tutor_agent must NOT surface answer_delta on the public stream
- synthesizer owns the final answer emission
"""

import asyncio

import pytest

from app.engine.multi_agent.graph_stream_merge_runtime import (
    drain_pending_bus_events_impl,
)


class FakeStreamEvent:
    """Minimal stand-in for StreamEvent."""

    def __init__(self, type: str, content: str = "", node: str | None = None):
        self.type = type
        self.content = content
        self.node = node


async def _fake_convert_bus_event(event: dict) -> FakeStreamEvent:
    etype = event.get("type", "status")
    return FakeStreamEvent(
        type="answer" if etype == "answer_delta" else etype,
        content=event.get("content", ""),
        node=event.get("node"),
    )


@pytest.mark.asyncio
async def test_graph_done_suppresses_tutor_answer_delta_in_event_queue():
    event_queue = asyncio.Queue()
    merged_queue = asyncio.Queue()
    sentinel = object()

    event_queue.put_nowait({"type": "answer_delta", "content": "Hello ", "node": "tutor_agent"})
    event_queue.put_nowait({"type": "answer_delta", "content": "World", "node": "tutor_agent"})

    events, answer_emitted = await drain_pending_bus_events_impl(
        merged_queue=merged_queue,
        event_queue=event_queue,
        convert_bus_event=_fake_convert_bus_event,
        answer_emitted=False,
        sentinel=sentinel,
    )

    assert events == []
    assert answer_emitted is False


@pytest.mark.asyncio
async def test_graph_done_suppresses_tutor_answer_delta_in_merged_queue():
    event_queue = asyncio.Queue()
    merged_queue = asyncio.Queue()
    sentinel = object()

    merged_queue.put_nowait(("bus", {"type": "answer_delta", "content": "OK", "node": "tutor_agent"}))

    events, answer_emitted = await drain_pending_bus_events_impl(
        merged_queue=merged_queue,
        event_queue=event_queue,
        convert_bus_event=_fake_convert_bus_event,
        answer_emitted=False,
        sentinel=sentinel,
    )

    assert events == []
    assert answer_emitted is False


@pytest.mark.asyncio
async def test_graph_done_keeps_non_tutor_answer_delta():
    event_queue = asyncio.Queue()
    merged_queue = asyncio.Queue()
    sentinel = object()

    event_queue.put_nowait({"type": "answer_delta", "content": "Grounded answer", "node": "rag_agent"})

    events, answer_emitted = await drain_pending_bus_events_impl(
        merged_queue=merged_queue,
        event_queue=event_queue,
        convert_bus_event=_fake_convert_bus_event,
        answer_emitted=False,
        sentinel=sentinel,
    )

    assert len(events) == 1
    assert events[0].type == "answer"
    assert events[0].content == "Grounded answer"
    assert events[0].node == "rag_agent"
    assert answer_emitted is True


@pytest.mark.asyncio
async def test_graph_done_keeps_tutor_thinking_but_drops_tutor_answer():
    event_queue = asyncio.Queue()
    merged_queue = asyncio.Queue()
    sentinel = object()

    event_queue.put_nowait({"type": "thinking_delta", "content": "dang ra soat...", "node": "tutor_agent"})
    event_queue.put_nowait({"type": "answer_delta", "content": "draft answer", "node": "tutor_agent"})

    events, answer_emitted = await drain_pending_bus_events_impl(
        merged_queue=merged_queue,
        event_queue=event_queue,
        convert_bus_event=_fake_convert_bus_event,
        answer_emitted=False,
        sentinel=sentinel,
    )

    assert len(events) == 1
    assert events[0].type == "thinking_delta"
    assert events[0].content == "dang ra soat..."
    assert answer_emitted is False


@pytest.mark.asyncio
async def test_graph_done_skips_sentinel_and_keeps_status():
    event_queue = asyncio.Queue()
    merged_queue = asyncio.Queue()
    sentinel = object()

    event_queue.put_nowait(sentinel)
    event_queue.put_nowait({"type": "status", "content": "test", "node": "tutor_agent"})

    events, answer_emitted = await drain_pending_bus_events_impl(
        merged_queue=merged_queue,
        event_queue=event_queue,
        convert_bus_event=_fake_convert_bus_event,
        answer_emitted=False,
        sentinel=sentinel,
    )

    assert len(events) == 1
    assert events[0].type == "status"
    assert events[0].content == "test"
    assert answer_emitted is False
