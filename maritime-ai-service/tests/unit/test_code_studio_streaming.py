"""Tests for Code Studio streaming events (code_open, code_delta, code_complete).

Phase 1: Backend chunked code streaming pipeline.
"""
import asyncio
import pytest

from app.engine.multi_agent.stream_utils import (
    StreamEventType,
    create_code_open_event,
    create_code_delta_event,
    create_code_complete_event,
)
from app.engine.multi_agent.graph import (
    CODE_CHUNK_SIZE,
    CODE_CHUNK_DELAY_SEC,
    _maybe_emit_code_studio_events,
)


# =============================================================================
# StreamEventType constants
# =============================================================================

class TestCodeStudioEventTypes:
    def test_code_open_type(self):
        assert StreamEventType.CODE_OPEN == "code_open"

    def test_code_delta_type(self):
        assert StreamEventType.CODE_DELTA == "code_delta"

    def test_code_complete_type(self):
        assert StreamEventType.CODE_COMPLETE == "code_complete"


# =============================================================================
# Stream event generators
# =============================================================================

class TestCodeOpenEvent:
    @pytest.mark.asyncio
    async def test_basic(self):
        event = await create_code_open_event(
            session_id="vs_123",
            title="Chart Example",
            language="html",
            version=1,
            node="code_studio_agent",
        )
        assert event.type == "code_open"
        assert event.content["session_id"] == "vs_123"
        assert event.content["title"] == "Chart Example"
        assert event.content["language"] == "html"
        assert event.content["version"] == 1
        assert event.node == "code_studio_agent"

    @pytest.mark.asyncio
    async def test_serialization(self):
        event = await create_code_open_event(
            session_id="s1", title="T", language="html", version=2,
        )
        d = event.to_dict()
        assert d["type"] == "code_open"
        assert d["content"]["session_id"] == "s1"
        assert d["content"]["version"] == 2


class TestCodeDeltaEvent:
    @pytest.mark.asyncio
    async def test_basic(self):
        event = await create_code_delta_event(
            session_id="vs_123",
            chunk="<div>Hello</div>",
            chunk_index=0,
            total_bytes=500,
            node="code_studio_agent",
        )
        assert event.type == "code_delta"
        assert event.content["chunk"] == "<div>Hello</div>"
        assert event.content["chunk_index"] == 0
        assert event.content["total_bytes"] == 500

    @pytest.mark.asyncio
    async def test_serialization(self):
        event = await create_code_delta_event(
            session_id="s1", chunk="abc", chunk_index=3, total_bytes=100,
        )
        d = event.to_dict()
        assert d["type"] == "code_delta"
        assert d["content"]["chunk"] == "abc"


class TestCodeCompleteEvent:
    @pytest.mark.asyncio
    async def test_basic(self):
        event = await create_code_complete_event(
            session_id="vs_123",
            full_code="<html>full</html>",
            language="html",
            version=1,
            node="code_studio_agent",
        )
        assert event.type == "code_complete"
        assert event.content["full_code"] == "<html>full</html>"
        assert "visual_payload" not in event.content

    @pytest.mark.asyncio
    async def test_with_visual_payload(self):
        vp = {"id": "v1", "type": "data_visualization"}
        event = await create_code_complete_event(
            session_id="s1",
            full_code="<div/>",
            language="html",
            version=1,
            visual_payload=vp,
        )
        assert event.content["visual_payload"] == vp


# =============================================================================
# Chunked emission integration
# =============================================================================

class TestMaybeEmitCodeStudioEvents:
    @pytest.mark.asyncio
    async def test_emits_open_deltas_complete(self):
        """Verify code_open → code_delta × N → code_complete sequence."""
        events = []

        async def push_event(event):
            events.append(event)

        class FakePayload:
            fallback_html = "A" * 600  # 600 chars → 3 chunks at 250
            visual_session_id = "vs_test"
            title = "Test Chart"
            figure_index = 1

        await _maybe_emit_code_studio_events(
            push_event=push_event,
            payload=FakePayload(),
            payload_dict={"id": "v1"},
            node="code_studio_agent",
        )

        # Should have: 1 code_open + 3 code_delta + 1 code_complete = 5
        types = [e["type"] for e in events]
        assert types[0] == "code_open"
        assert types[-1] == "code_complete"
        assert types.count("code_delta") == 3

        # Verify code_open metadata
        open_event = events[0]
        assert open_event["content"]["session_id"] == "vs_test"
        assert open_event["content"]["title"] == "Test Chart"
        assert open_event["content"]["language"] == "html"

        # Verify code_complete has full code
        complete_event = events[-1]
        assert len(complete_event["content"]["full_code"]) == 600
        assert complete_event["content"]["visual_payload"] == {"id": "v1"}

        # Verify chunk indices are sequential
        delta_events = [e for e in events if e["type"] == "code_delta"]
        for i, de in enumerate(delta_events):
            assert de["content"]["chunk_index"] == i
            assert de["content"]["total_bytes"] == 600

    @pytest.mark.asyncio
    async def test_no_emit_when_no_fallback_html(self):
        events = []

        async def push_event(event):
            events.append(event)

        class FakePayload:
            fallback_html = None
            visual_session_id = "vs_test"
            title = "T"
            figure_index = 1

        await _maybe_emit_code_studio_events(
            push_event=push_event,
            payload=FakePayload(),
            payload_dict={},
            node="n",
        )
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_single_chunk_for_short_code(self):
        events = []

        async def push_event(event):
            events.append(event)

        class FakePayload:
            fallback_html = "<p>Hi</p>"  # 9 chars → 1 chunk
            visual_session_id = "vs_short"
            title = "Short"
            figure_index = 1

        await _maybe_emit_code_studio_events(
            push_event=push_event,
            payload=FakePayload(),
            payload_dict={},
            node="n",
        )

        types = [e["type"] for e in events]
        assert types == ["code_open", "code_delta", "code_complete"]
        assert events[1]["content"]["chunk"] == "<p>Hi</p>"

    @pytest.mark.asyncio
    async def test_prefers_code_studio_version_metadata_over_figure_index(self):
        events = []

        async def push_event(event):
            events.append(event)

        class FakePayload:
            fallback_html = "<div>patched</div>"
            visual_session_id = "vs_patch"
            title = "Patched App"
            figure_index = 1

        await _maybe_emit_code_studio_events(
            push_event=push_event,
            payload=FakePayload(),
            payload_dict={"metadata": {"code_studio_version": 3}},
            node="code_studio_agent",
        )

        assert events[0]["content"]["version"] == 3
        assert events[-1]["content"]["version"] == 3

    @pytest.mark.asyncio
    async def test_forwards_requested_view_when_present(self):
        events = []

        async def push_event(event):
            events.append(event)

        class FakePayload:
            fallback_html = "<div>patched</div>"
            visual_session_id = "vs_patch"
            title = "Patched App"
            figure_index = 1

        await _maybe_emit_code_studio_events(
            push_event=push_event,
            payload=FakePayload(),
            payload_dict={"metadata": {"requested_view": "code"}},
            node="code_studio_agent",
        )

        assert events[0]["content"]["requested_view"] == "code"
        assert events[-1]["content"]["requested_view"] == "code"


class TestCodeStudioConstants:
    def test_chunk_size(self):
        assert CODE_CHUNK_SIZE == 250

    def test_chunk_delay(self):
        assert CODE_CHUNK_DELAY_SEC == 0.015
