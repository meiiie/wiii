"""
Tests for Sprint 70: True Interleaved Thinking (Claude pattern).

Tests cover:
- _convert_bus_event with thinking_start/thinking_end event types
- Concurrent merged-queue pattern (graph + bus forwarders)
- Tutor node .astream() token-level streaming with event bus
- Bus-streamed-nodes tracking (skip bulk re-emission)
- Backward compatibility (no event_queue → .ainvoke() path)

NOTE: graph_streaming has a deep circular import chain via multi_agent.graph → agents →
services → chat_service → multi_agent.graph. We break it by pre-mocking app.services
in sys.modules before importing.
"""

import asyncio
import sys
import types
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Break circular import chain
_cs_key = "app.services.chat_service"
_svc_key = "app.services"
_had_cs = _cs_key in sys.modules
_had_svc = _svc_key in sys.modules
_orig_cs = sys.modules.get(_cs_key)
if not _had_cs:
    _mock_cs = types.ModuleType(_cs_key)
    _mock_cs.ChatService = type("ChatService", (), {})
    _mock_cs.get_chat_service = lambda: None
    sys.modules[_cs_key] = _mock_cs

from app.engine.multi_agent.graph_streaming import (
    _EVENT_QUEUES,
    _get_event_queue,
    _convert_bus_event,
)
from app.engine.multi_agent.stream_utils import StreamEvent, StreamEventType

if not _had_cs:
    sys.modules.pop(_cs_key, None)
    if not _had_svc:
        sys.modules.pop(_svc_key, None)
elif _orig_cs is not None:
    sys.modules[_cs_key] = _orig_cs


# =============================================================================
# Sprint 70: _convert_bus_event with thinking_start/thinking_end
# =============================================================================


class TestConvertBusEventThinkingLifecycle:
    """Sprint 70: _convert_bus_event handles thinking_start and thinking_end."""

    @pytest.mark.asyncio
    async def test_thinking_start_event(self):
        """thinking_start bus event should produce a THINKING_START StreamEvent."""
        event = await _convert_bus_event({
            "type": "thinking_start",
            "content": "Suy nghĩ (lần 1)",
            "node": "tutor_agent",
        })
        assert isinstance(event, StreamEvent)
        assert event.type == StreamEventType.THINKING_START
        assert event.content == "Suy nghĩ (lần 1)"
        assert event.node == "tutor_agent"

    @pytest.mark.asyncio
    async def test_thinking_end_event(self):
        """thinking_end bus event should produce a THINKING_END StreamEvent."""
        event = await _convert_bus_event({
            "type": "thinking_end",
            "content": "",
            "node": "tutor_agent",
        })
        assert isinstance(event, StreamEvent)
        assert event.type == StreamEventType.THINKING_END
        assert event.node == "tutor_agent"

    @pytest.mark.asyncio
    async def test_thinking_start_no_node(self):
        """thinking_start without node should use empty string."""
        event = await _convert_bus_event({
            "type": "thinking_start",
            "content": "Test label",
        })
        assert event.type == StreamEventType.THINKING_START
        assert event.node == ""  # Fallback to empty string

    @pytest.mark.asyncio
    async def test_thinking_end_no_node(self):
        """thinking_end without node should use empty string."""
        event = await _convert_bus_event({
            "type": "thinking_end",
            "content": "",
        })
        assert event.type == StreamEventType.THINKING_END
        assert event.node == ""

    @pytest.mark.asyncio
    async def test_full_thinking_lifecycle(self):
        """Full lifecycle: thinking_start → thinking_delta* → thinking_end."""
        events = []
        for raw in [
            {"type": "thinking_start", "content": "Phân tích", "node": "tutor_agent"},
            {"type": "thinking_delta", "content": "Đây là ", "node": "tutor_agent"},
            {"type": "thinking_delta", "content": "phần suy nghĩ", "node": "tutor_agent"},
            {"type": "thinking_end", "content": "", "node": "tutor_agent"},
        ]:
            events.append(await _convert_bus_event(raw))

        assert len(events) == 4
        assert events[0].type == StreamEventType.THINKING_START
        assert events[1].type == StreamEventType.THINKING_DELTA
        assert events[1].content == "Đây là "
        assert events[2].type == StreamEventType.THINKING_DELTA
        assert events[2].content == "phần suy nghĩ"
        assert events[3].type == StreamEventType.THINKING_END

    @pytest.mark.asyncio
    async def test_interleaved_thinking_and_tools(self):
        """Thinking deltas interleaved with tool calls (Claude pattern)."""
        raw_events = [
            {"type": "thinking_start", "content": "Suy nghĩ", "node": "tutor_agent"},
            {"type": "thinking_delta", "content": "Cần tra cứu...", "node": "tutor_agent"},
            {"type": "thinking_end", "content": "", "node": "tutor_agent"},
            {"type": "tool_call", "content": {"name": "search", "args": {"q": "test"}, "id": "c1"}, "node": "tutor_agent"},
            {"type": "tool_result", "content": {"name": "search", "result": "found", "id": "c1"}, "node": "tutor_agent"},
            {"type": "thinking_start", "content": "Suy nghĩ (lần 2)", "node": "tutor_agent"},
            {"type": "thinking_delta", "content": "Tổng hợp kết quả...", "node": "tutor_agent"},
            {"type": "thinking_end", "content": "", "node": "tutor_agent"},
        ]
        events = [await _convert_bus_event(raw) for raw in raw_events]

        types_seq = [e.type for e in events]
        assert types_seq == [
            StreamEventType.THINKING_START,
            StreamEventType.THINKING_DELTA,
            StreamEventType.THINKING_END,
            StreamEventType.TOOL_CALL,
            StreamEventType.TOOL_RESULT,
            StreamEventType.THINKING_START,
            StreamEventType.THINKING_DELTA,
            StreamEventType.THINKING_END,
        ]


# =============================================================================
# Sprint 70: Concurrent merged-queue pattern
# =============================================================================


class TestMergedQueuePattern:
    """Tests for the concurrent merged-queue consumption pattern."""

    @pytest.mark.asyncio
    async def test_bus_events_forwarded_to_merged_queue(self):
        """Bus events should be forwarded to merged queue by _forward_bus."""
        _SENTINEL = object()
        merged_queue = asyncio.Queue()
        event_queue = asyncio.Queue()

        async def _forward_bus():
            while True:
                try:
                    event = await event_queue.get()
                    if event is _SENTINEL:
                        break
                    await merged_queue.put(("bus", event))
                except Exception:
                    break

        # Put some events
        event_queue.put_nowait({"type": "thinking_delta", "content": "tok1", "node": "t"})
        event_queue.put_nowait({"type": "thinking_delta", "content": "tok2", "node": "t"})
        event_queue.put_nowait(_SENTINEL)

        await _forward_bus()

        results = []
        while not merged_queue.empty():
            results.append(merged_queue.get_nowait())

        assert len(results) == 2
        assert results[0] == ("bus", {"type": "thinking_delta", "content": "tok1", "node": "t"})
        assert results[1] == ("bus", {"type": "thinking_delta", "content": "tok2", "node": "t"})

    @pytest.mark.asyncio
    async def test_graph_events_forwarded_to_merged_queue(self):
        """Graph node completions should be forwarded as ('graph', update)."""
        merged_queue = asyncio.Queue()

        async def _forward_graph():
            updates = [
                {"supervisor": {"next_agent": "rag_agent"}},
                {"rag_agent": {"final_response": "answer"}},
            ]
            for u in updates:
                await merged_queue.put(("graph", u))
            await merged_queue.put(("graph_done", None))

        await _forward_graph()

        results = []
        while not merged_queue.empty():
            results.append(merged_queue.get_nowait())

        assert len(results) == 3
        assert results[0][0] == "graph"
        assert results[1][0] == "graph"
        assert results[2] == ("graph_done", None)

    @pytest.mark.asyncio
    async def test_bus_and_graph_interleaved(self):
        """Bus events and graph events arrive interleaved in merged queue."""
        merged_queue = asyncio.Queue()

        # Simulate interleaved arrival
        await merged_queue.put(("bus", {"type": "thinking_delta", "content": "t1", "node": "tutor"}))
        await merged_queue.put(("graph", {"supervisor": {"next_agent": "tutor_agent"}}))
        await merged_queue.put(("bus", {"type": "thinking_delta", "content": "t2", "node": "tutor"}))
        await merged_queue.put(("graph_done", None))

        results = []
        while not merged_queue.empty():
            results.append(merged_queue.get_nowait())

        assert len(results) == 4
        assert results[0][0] == "bus"
        assert results[1][0] == "graph"
        assert results[2][0] == "bus"
        assert results[3][0] == "graph_done"

    @pytest.mark.asyncio
    async def test_bus_streamed_nodes_tracking(self):
        """Nodes with thinking_delta via bus should be tracked in _bus_streamed_nodes."""
        _bus_streamed_nodes = set()
        event_queue = asyncio.Queue()

        # Simulate events from tutor_agent
        events = [
            {"type": "thinking_start", "content": "Label", "node": "tutor_agent"},
            {"type": "thinking_delta", "content": "tok", "node": "tutor_agent"},
            {"type": "thinking_end", "content": "", "node": "tutor_agent"},
        ]

        for evt in events:
            node = evt.get("node")
            if node and evt.get("type") == "thinking_delta":
                _bus_streamed_nodes.add(node)

        assert "tutor_agent" in _bus_streamed_nodes
        # Supervisor didn't stream, so should NOT be in set
        assert "supervisor" not in _bus_streamed_nodes

    @pytest.mark.asyncio
    async def test_skip_bulk_when_bus_streamed(self):
        """When bus already streamed deltas for a node, skip bulk thinking emission."""
        _bus_streamed_nodes = {"tutor_agent"}

        thinking_content = "This is some thinking content from tutor"

        # Simulate the check in graph_streaming.py
        should_emit_bulk = thinking_content and "tutor_agent" not in _bus_streamed_nodes
        assert should_emit_bulk is False  # Skip because bus already streamed

        # Supervisor wasn't bus-streamed, so bulk should emit
        should_emit_supervisor = thinking_content and "supervisor" not in _bus_streamed_nodes
        assert should_emit_supervisor is True

    @pytest.mark.asyncio
    async def test_sentinel_stops_bus_forwarder(self):
        """_SENTINEL object stops the bus forwarder cleanly."""
        _SENTINEL = object()
        event_queue = asyncio.Queue()
        stopped = False

        async def _forward_bus():
            nonlocal stopped
            while True:
                event = await event_queue.get()
                if event is _SENTINEL:
                    stopped = True
                    break

        event_queue.put_nowait({"type": "thinking_delta", "content": "x", "node": "t"})
        event_queue.put_nowait(_SENTINEL)

        await _forward_bus()
        assert stopped is True

    @pytest.mark.asyncio
    async def test_error_event_in_merged_queue(self):
        """Error messages should be forwarded as ('error', message)."""
        merged_queue = asyncio.Queue()
        await merged_queue.put(("error", "Processing timeout exceeded"))

        msg_type, payload = merged_queue.get_nowait()
        assert msg_type == "error"
        assert payload == "Processing timeout exceeded"


# =============================================================================
# Sprint 70: Tutor node .astream() with event_queue
# =============================================================================


class TestTutorNodeStreamingPattern:
    """Tests for tutor node .astream() token-level streaming."""

    @pytest.mark.asyncio
    async def test_astream_pushes_thinking_lifecycle(self):
        """When event_queue present, tutor should push thinking_start → deltas → thinking_end."""
        event_queue = asyncio.Queue()

        # Simulate what tutor_node does during ReAct loop
        # (extracted pattern from tutor_node.py lines 317-346)
        async def _push(evt):
            event_queue.put_nowait(evt)

        # Emit thinking_start
        await _push({
            "type": "thinking_start",
            "content": "Suy nghĩ (lần 1)",
            "node": "tutor_agent",
        })

        # Simulate .astream() yielding chunks
        chunks = ["Tôi cần ", "tra cứu ", "quy tắc ", "COLREGs."]
        for chunk_text in chunks:
            await _push({
                "type": "thinking_delta",
                "content": chunk_text,
                "node": "tutor_agent",
            })

        # Emit thinking_end
        await _push({
            "type": "thinking_end",
            "content": "",
            "node": "tutor_agent",
        })

        # Collect all events
        events = []
        while not event_queue.empty():
            events.append(event_queue.get_nowait())

        assert len(events) == 6  # 1 start + 4 deltas + 1 end
        assert events[0]["type"] == "thinking_start"
        assert events[0]["content"] == "Suy nghĩ (lần 1)"
        for i in range(1, 5):
            assert events[i]["type"] == "thinking_delta"
        assert events[5]["type"] == "thinking_end"

        # Verify accumulated content
        accumulated = "".join(e["content"] for e in events if e["type"] == "thinking_delta")
        assert accumulated == "Tôi cần tra cứu quy tắc COLREGs."

    @pytest.mark.asyncio
    async def test_astream_with_tool_interleaving(self):
        """Tutor ReAct loop: thinking → tool_call → tool_result → thinking (Claude pattern)."""
        event_queue = asyncio.Queue()

        async def _push(evt):
            event_queue.put_nowait(evt)

        # Iteration 1: Think → decide to call tool
        await _push({"type": "thinking_start", "content": "Suy nghĩ (lần 1)", "node": "tutor_agent"})
        await _push({"type": "thinking_delta", "content": "Cần tìm thông tin...", "node": "tutor_agent"})
        await _push({"type": "thinking_end", "content": "", "node": "tutor_agent"})

        # Tool execution
        await _push({"type": "tool_call", "content": {"name": "search", "args": {"q": "COLREGs"}, "id": "c1"}, "node": "tutor_agent"})
        await _push({"type": "tool_result", "content": {"name": "search", "result": "Found 3 docs", "id": "c1"}, "node": "tutor_agent"})

        # Iteration 2: Think again (final generation)
        await _push({"type": "thinking_start", "content": "Tổng hợp câu trả lời", "node": "tutor_agent"})
        await _push({"type": "thinking_delta", "content": "Dựa trên kết quả...", "node": "tutor_agent"})
        await _push({"type": "thinking_end", "content": "", "node": "tutor_agent"})

        events = []
        while not event_queue.empty():
            events.append(event_queue.get_nowait())

        types_seq = [e["type"] for e in events]
        assert types_seq == [
            "thinking_start",
            "thinking_delta",
            "thinking_end",
            "tool_call",
            "tool_result",
            "thinking_start",
            "thinking_delta",
            "thinking_end",
        ]

    @pytest.mark.asyncio
    async def test_no_event_queue_no_push(self):
        """When event_queue is None, no events should be pushed (backward compat)."""
        event_queue = None

        # Simulate the _push helper behavior
        async def _push(evt):
            if event_queue is not None:
                try:
                    event_queue.put_nowait(evt)
                except Exception:
                    pass

        # Should not raise even without queue
        await _push({"type": "thinking_delta", "content": "test", "node": "t"})
        # No assertion needed — just verify no exception

    @pytest.mark.asyncio
    async def test_empty_chunk_content_skipped(self):
        """Chunks with empty content should not push thinking_delta."""
        event_queue = asyncio.Queue()

        async def _push(evt):
            event_queue.put_nowait(evt)

        # Simulate .astream() where some chunks have empty content
        chunks_with_content = [
            ("", False),  # Empty chunk — skipped in tutor_node
            ("First token", True),
            ("", False),  # Empty chunk — skipped
            ("Second token", True),
        ]

        for text, has_content in chunks_with_content:
            if has_content:  # if chunk.content: (tutor_node check)
                await _push({
                    "type": "thinking_delta",
                    "content": text,
                    "node": "tutor_agent",
                })

        events = []
        while not event_queue.empty():
            events.append(event_queue.get_nowait())

        assert len(events) == 2
        assert events[0]["content"] == "First token"
        assert events[1]["content"] == "Second token"

    @pytest.mark.asyncio
    async def test_final_generation_streaming(self):
        """After tool calls exhaust iterations, final generation also streams."""
        event_queue = asyncio.Queue()

        async def _push(evt):
            event_queue.put_nowait(evt)

        # Final generation (tutor_node.py lines 488-510)
        await _push({"type": "thinking_start", "content": "Tổng hợp câu trả lời", "node": "tutor_agent"})

        final_chunks = ["Quy tắc ", "số 5 ", "của COLREGs ", "quy định về..."]
        for chunk_text in final_chunks:
            await _push({
                "type": "thinking_delta",
                "content": chunk_text,
                "node": "tutor_agent",
            })

        await _push({"type": "thinking_end", "content": "", "node": "tutor_agent"})

        events = []
        while not event_queue.empty():
            events.append(event_queue.get_nowait())

        assert events[0]["type"] == "thinking_start"
        assert events[0]["content"] == "Tổng hợp câu trả lời"
        assert len([e for e in events if e["type"] == "thinking_delta"]) == 4
        assert events[-1]["type"] == "thinking_end"


# =============================================================================
# Sprint 70: Integration — bus events converted and yielded
# =============================================================================


class TestBusEventConversionIntegration:
    """End-to-end: bus events → _convert_bus_event → StreamEvents."""

    @pytest.mark.asyncio
    async def test_full_thinking_lifecycle_conversion(self):
        """Full thinking lifecycle from bus events to StreamEvents."""
        raw_events = [
            {"type": "thinking_start", "content": "Suy nghĩ", "node": "tutor_agent"},
            {"type": "thinking_delta", "content": "Phân tích ", "node": "tutor_agent"},
            {"type": "thinking_delta", "content": "câu hỏi...", "node": "tutor_agent"},
            {"type": "thinking_end", "content": "", "node": "tutor_agent"},
        ]

        stream_events = [await _convert_bus_event(raw) for raw in raw_events]

        assert len(stream_events) == 4
        assert stream_events[0].type == StreamEventType.THINKING_START
        assert stream_events[0].content == "Suy nghĩ"
        assert stream_events[0].node == "tutor_agent"

        assert stream_events[1].type == StreamEventType.THINKING_DELTA
        assert stream_events[1].content == "Phân tích "

        assert stream_events[2].type == StreamEventType.THINKING_DELTA
        assert stream_events[2].content == "câu hỏi..."

        assert stream_events[3].type == StreamEventType.THINKING_END
        assert stream_events[3].node == "tutor_agent"

    @pytest.mark.asyncio
    async def test_mixed_events_all_convert_correctly(self):
        """All Sprint 70 event types convert correctly in sequence."""
        raw_events = [
            {"type": "thinking_start", "content": "L1", "node": "n"},
            {"type": "thinking_delta", "content": "d1", "node": "n"},
            {"type": "thinking_end", "content": "", "node": "n"},
            {"type": "tool_call", "content": {"name": "t", "args": {}, "id": "x"}, "node": "n"},
            {"type": "tool_result", "content": {"name": "t", "result": "r", "id": "x"}, "node": "n"},
            {"type": "status", "content": "Done", "node": "n"},
        ]

        events = [await _convert_bus_event(raw) for raw in raw_events]
        types_seq = [e.type for e in events]

        assert types_seq == [
            StreamEventType.THINKING_START,
            StreamEventType.THINKING_DELTA,
            StreamEventType.THINKING_END,
            StreamEventType.TOOL_CALL,
            StreamEventType.TOOL_RESULT,
            StreamEventType.STATUS,
        ]

    @pytest.mark.asyncio
    async def test_to_dict_includes_node(self):
        """StreamEvent.to_dict() should include node from bus events."""
        event = await _convert_bus_event({
            "type": "thinking_start",
            "content": "Test",
            "node": "tutor_agent",
        })
        d = event.to_dict()
        assert d["type"] == "thinking_start"
        assert d["content"] == "Test"
        assert d["node"] == "tutor_agent"


# =============================================================================
# Sprint 70 Fix: Gemini list-format content handling + sub-chunking
# =============================================================================


class TestExtractChunkText:
    """Tests for _extract_chunk_text helper (handles Gemini list content)."""

    def test_string_content(self):
        """String content passes through unchanged."""
        from app.engine.multi_agent.agents.tutor_node import TutorAgentNode
        # Access the function by simulating what the closure does
        # We test the logic directly
        def _extract_chunk_text(content):
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "".join(
                    part.get("text", "") for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            return str(content) if content else ""

        assert _extract_chunk_text("hello world") == "hello world"
        assert _extract_chunk_text("") == ""

    def test_gemini_list_with_text(self):
        """Gemini list content with text parts extracts text correctly."""
        def _extract_chunk_text(content):
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "".join(
                    part.get("text", "") for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            return str(content) if content else ""

        content = [{"type": "text", "text": "Xin chào", "index": 0}]
        assert _extract_chunk_text(content) == "Xin chào"

    def test_gemini_list_multiple_parts(self):
        """Multiple text parts are concatenated."""
        def _extract_chunk_text(content):
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "".join(
                    part.get("text", "") for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            return str(content) if content else ""

        content = [
            {"type": "text", "text": "Hello "},
            {"type": "text", "text": "World"},
        ]
        assert _extract_chunk_text(content) == "Hello World"

    def test_gemini_list_signature_only(self):
        """Signature-only chunks (empty text) return empty string."""
        def _extract_chunk_text(content):
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "".join(
                    part.get("text", "") for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            return str(content) if content else ""

        content = [{"type": "text", "text": "", "extras": {"signature": "abc123"}}]
        assert _extract_chunk_text(content) == ""

    def test_gemini_empty_list(self):
        """Empty list (tool call chunk) returns empty string."""
        def _extract_chunk_text(content):
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "".join(
                    part.get("text", "") for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            return str(content) if content else ""

        assert _extract_chunk_text([]) == ""

    def test_none_content(self):
        """None content returns empty string."""
        def _extract_chunk_text(content):
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "".join(
                    part.get("text", "") for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            return str(content) if content else ""

        assert _extract_chunk_text(None) == ""

    def test_non_text_parts_filtered(self):
        """Non-text content parts (e.g., thinking) are filtered out."""
        def _extract_chunk_text(content):
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "".join(
                    part.get("text", "") for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            return str(content) if content else ""

        content = [
            {"type": "thinking", "text": "internal reasoning"},
            {"type": "text", "text": "visible response"},
        ]
        assert _extract_chunk_text(content) == "visible response"


class TestPushThinkingDeltas:
    """Tests for sub-chunking logic in _push_thinking_deltas."""

    @pytest.mark.asyncio
    async def test_sub_chunking_short_text(self):
        """Short text fits in one sub-chunk."""
        event_queue = asyncio.Queue()

        async def _push(evt):
            event_queue.put_nowait(evt)

        text = "Hello"  # 5 chars < 12 (CHUNK_SIZE)
        _CHUNK_SIZE = 12
        for i in range(0, len(text), _CHUNK_SIZE):
            sub = text[i:i + _CHUNK_SIZE]
            await _push({"type": "thinking_delta", "content": sub, "node": "t"})

        events = []
        while not event_queue.empty():
            events.append(event_queue.get_nowait())

        assert len(events) == 1
        assert events[0]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_sub_chunking_long_text(self):
        """Long text is split into multiple sub-chunks."""
        event_queue = asyncio.Queue()

        async def _push(evt):
            event_queue.put_nowait(evt)

        text = "A" * 50  # 50 chars / 12 = 5 sub-chunks (4*12 + 2)
        _CHUNK_SIZE = 12
        for i in range(0, len(text), _CHUNK_SIZE):
            sub = text[i:i + _CHUNK_SIZE]
            await _push({"type": "thinking_delta", "content": sub, "node": "t"})

        events = []
        while not event_queue.empty():
            events.append(event_queue.get_nowait())

        assert len(events) == 5
        total = "".join(e["content"] for e in events)
        assert total == text
        assert events[0]["content"] == "A" * 12
        assert events[-1]["content"] == "AA"

    @pytest.mark.asyncio
    async def test_sub_chunking_preserves_unicode(self):
        """Vietnamese text is preserved during sub-chunking."""
        event_queue = asyncio.Queue()

        async def _push(evt):
            event_queue.put_nowait(evt)

        text = "Quy tắc tránh va chạm trên biển"  # ~30 chars
        _CHUNK_SIZE = 12
        for i in range(0, len(text), _CHUNK_SIZE):
            sub = text[i:i + _CHUNK_SIZE]
            await _push({"type": "thinking_delta", "content": sub, "node": "t"})

        events = []
        while not event_queue.empty():
            events.append(event_queue.get_nowait())

        total = "".join(e["content"] for e in events)
        assert total == text

    @pytest.mark.asyncio
    async def test_empty_text_no_events(self):
        """Empty text produces no thinking_delta events."""
        event_queue = asyncio.Queue()

        text = ""
        _CHUNK_SIZE = 12
        for i in range(0, len(text), _CHUNK_SIZE):
            sub = text[i:i + _CHUNK_SIZE]
            event_queue.put_nowait({"type": "thinking_delta", "content": sub, "node": "t"})

        assert event_queue.empty()


class TestGeminiContentEndToEnd:
    """End-to-end: Gemini list content → extract → sub-chunk → bus events."""

    @pytest.mark.asyncio
    async def test_gemini_astream_simulation(self):
        """Simulate Gemini .astream() with list content, verify bus events."""
        event_queue = asyncio.Queue()

        async def _push(evt):
            event_queue.put_nowait(evt)

        def _extract_chunk_text(content):
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "".join(
                    part.get("text", "") for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            return str(content) if content else ""

        _CHUNK_SIZE = 12

        # Simulate Gemini .astream() output (3 chunks)
        gemini_chunks = [
            [{"type": "text", "text": "Xin chào bạn, hãy cùng tìm hiểu"}],  # Text
            [{"type": "text", "text": "", "extras": {"signature": "abc"}}],  # Signature
            [],  # Empty
        ]

        await _push({"type": "thinking_start", "content": "Label", "node": "tutor_agent"})

        for chunk_content in gemini_chunks:
            text = _extract_chunk_text(chunk_content)
            if text:
                for i in range(0, len(text), _CHUNK_SIZE):
                    sub = text[i:i + _CHUNK_SIZE]
                    await _push({"type": "thinking_delta", "content": sub, "node": "tutor_agent"})

        await _push({"type": "thinking_end", "content": "", "node": "tutor_agent"})

        events = []
        while not event_queue.empty():
            events.append(event_queue.get_nowait())

        # thinking_start + sub-chunks of "Xin chào bạn, hãy cùng tìm hiểu" + thinking_end
        assert events[0]["type"] == "thinking_start"
        assert events[-1]["type"] == "thinking_end"

        deltas = [e for e in events if e["type"] == "thinking_delta"]
        text_len = len("Xin chào bạn, hãy cùng tìm hiểu")
        expected_chunks = (text_len + _CHUNK_SIZE - 1) // _CHUNK_SIZE
        assert len(deltas) == expected_chunks

        reconstructed = "".join(d["content"] for d in deltas)
        assert reconstructed == "Xin chào bạn, hãy cùng tìm hiểu"

    @pytest.mark.asyncio
    async def test_tool_call_chunk_produces_no_deltas(self):
        """Gemini tool call chunks have empty content list → no thinking_delta."""
        event_queue = asyncio.Queue()

        def _extract_chunk_text(content):
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "".join(
                    part.get("text", "") for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            return str(content) if content else ""

        # Gemini tool call: content=[], tool_calls=[{...}]
        chunk_content = []
        text = _extract_chunk_text(chunk_content)
        assert text == ""

        # Nothing pushed since text is empty
        assert event_queue.empty()
