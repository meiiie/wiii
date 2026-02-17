"""
Tests for Agentic Loop real-time streaming — Sprint 69.

Tests cover:
- LoopConfig event_queue and node_id fields
- Event push via _push_event
- _loop_with_langchain pushing events to queue
- agentic_loop_streaming real-time event yielding
"""

import asyncio
import sys
import types
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Break circular import: multi_agent.__init__ → graph → agents → tutor_node
# → services.__init__ → chat_service → multi_agent.graph
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

from app.engine.multi_agent.agent_loop import (
    LoopConfig,
    LoopResult,
    agentic_loop,
    agentic_loop_streaming,
    _push_event,
    _loop_with_langchain,
)

if not _had_cs:
    sys.modules.pop(_cs_key, None)
    if not _had_svc:
        sys.modules.pop(_svc_key, None)
elif _orig_cs is not None:
    sys.modules[_cs_key] = _orig_cs


# =============================================================================
# TestLoopConfigQueue
# =============================================================================


class TestLoopConfigQueue:
    """Tests for LoopConfig event_queue field."""

    def test_default_none(self):
        config = LoopConfig()
        assert config.event_queue is None

    def test_can_set_queue(self):
        q = asyncio.Queue()
        config = LoopConfig(event_queue=q)
        assert config.event_queue is q

    def test_node_id_default_none(self):
        config = LoopConfig()
        assert config.node_id is None

    def test_can_set_node_id(self):
        config = LoopConfig(node_id="tutor_agent")
        assert config.node_id == "tutor_agent"


# =============================================================================
# TestPushEvent
# =============================================================================


class TestPushEvent:
    """Tests for _push_event helper."""

    @pytest.mark.asyncio
    async def test_push_to_queue(self):
        q = asyncio.Queue()
        await _push_event(q, {"type": "test", "content": "hello"})
        assert q.qsize() == 1
        event = q.get_nowait()
        assert event["type"] == "test"

    @pytest.mark.asyncio
    async def test_push_none_queue_noop(self):
        # Should not raise
        await _push_event(None, {"type": "test"})

    @pytest.mark.asyncio
    async def test_push_multiple_events(self):
        q = asyncio.Queue()
        await _push_event(q, {"type": "a"})
        await _push_event(q, {"type": "b"})
        assert q.qsize() == 2


# =============================================================================
# TestEventQueuePush
# =============================================================================


class TestEventQueuePush:
    """Tests for event queue pushing in loop paths."""

    @pytest.mark.asyncio
    async def test_langchain_pushes_thinking_delta(self):
        """LangChain path should push thinking_delta when response has content."""
        q = asyncio.Queue()
        config = LoopConfig(event_queue=q, node_id="tutor_agent", max_steps=1)

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Some thinking..."
        mock_response.tool_calls = []
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch(
            "app.engine.llm_pool.get_llm_moderate",
            return_value=mock_llm,
        ), patch(
            "app.engine.llm_pool.get_llm_deep",
            return_value=mock_llm,
        ), patch(
            "app.engine.llm_pool.get_llm_light",
            return_value=mock_llm,
        ):
            result = await _loop_with_langchain(
                "test query", [], "system prompt", config,
            )

        assert result.response == "Some thinking..."
        # Check that thinking_delta was pushed
        assert q.qsize() >= 1
        event = q.get_nowait()
        assert event["type"] == "thinking_delta"
        assert event["content"] == "Some thinking..."
        assert event["node"] == "tutor_agent"

    @pytest.mark.asyncio
    async def test_langchain_pushes_tool_call(self):
        """LangChain path should push tool_call when tools are called."""
        q = asyncio.Queue()
        config = LoopConfig(event_queue=q, node_id="tutor", max_steps=2)

        mock_llm = MagicMock()

        # First call returns tool calls, second returns final response
        tool_call_resp = MagicMock()
        tool_call_resp.content = ""
        tool_call_resp.tool_calls = [
            {"name": "search", "args": {"q": "test"}, "id": "call_1"},
        ]

        final_resp = MagicMock()
        final_resp.content = "Final answer"
        final_resp.tool_calls = []

        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(side_effect=[tool_call_resp, final_resp])

        mock_tool = MagicMock()
        mock_tool.name = "search"
        mock_tool.ainvoke = AsyncMock(return_value="search result")

        with patch(
            "app.engine.llm_pool.get_llm_moderate",
            return_value=mock_llm,
        ), patch(
            "app.engine.llm_pool.get_llm_deep",
            return_value=mock_llm,
        ), patch(
            "app.engine.llm_pool.get_llm_light",
            return_value=mock_llm,
        ):
            result = await _loop_with_langchain(
                "test query", [mock_tool], "system prompt", config,
            )

        # Collect all events
        events = []
        while not q.empty():
            events.append(q.get_nowait())

        event_types = [e["type"] for e in events]
        assert "tool_call" in event_types
        assert "tool_result" in event_types

    @pytest.mark.asyncio
    async def test_langchain_no_push_when_queue_none(self):
        """When event_queue is None, no events should be pushed."""
        config = LoopConfig(max_steps=1)
        assert config.event_queue is None

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Response"
        mock_response.tool_calls = []
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch(
            "app.engine.llm_pool.get_llm_moderate",
            return_value=mock_llm,
        ), patch(
            "app.engine.llm_pool.get_llm_deep",
            return_value=mock_llm,
        ), patch(
            "app.engine.llm_pool.get_llm_light",
            return_value=mock_llm,
        ):
            result = await _loop_with_langchain(
                "test query", [], "system prompt", config,
            )

        assert result.response == "Response"
        # No crash, no queue interaction

    @pytest.mark.asyncio
    async def test_events_in_order(self):
        """Events should arrive in execution order."""
        q = asyncio.Queue()
        config = LoopConfig(event_queue=q, node_id="test", max_steps=2)

        mock_llm = MagicMock()

        # Step 1: tool call
        tc_resp = MagicMock()
        tc_resp.content = "thinking..."
        tc_resp.tool_calls = [
            {"name": "search", "args": {}, "id": "c1"},
        ]

        # Step 2: final answer
        final_resp = MagicMock()
        final_resp.content = "answer"
        final_resp.tool_calls = []

        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(side_effect=[tc_resp, final_resp])

        mock_tool = MagicMock()
        mock_tool.name = "search"
        mock_tool.ainvoke = AsyncMock(return_value="result")

        with patch(
            "app.engine.llm_pool.get_llm_moderate",
            return_value=mock_llm,
        ), patch(
            "app.engine.llm_pool.get_llm_deep",
            return_value=mock_llm,
        ), patch(
            "app.engine.llm_pool.get_llm_light",
            return_value=mock_llm,
        ):
            await _loop_with_langchain(
                "query", [mock_tool], "prompt", config,
            )

        events = []
        while not q.empty():
            events.append(q.get_nowait())

        types = [e["type"] for e in events]
        # thinking_delta first (from step 1 content), then tool_call, tool_result,
        # then thinking_delta from step 2
        assert types[0] == "thinking_delta"
        assert "tool_call" in types
        assert "tool_result" in types


# =============================================================================
# TestAgenticLoopStreamingRealTime
# =============================================================================


class TestAgenticLoopStreamingRealTime:
    """Tests for agentic_loop_streaming real-time event yielding."""

    @pytest.mark.asyncio
    async def test_yields_answer_last(self):
        """Streaming should yield answer event from final result."""
        mock_result = LoopResult(response="final answer", steps=1)

        with patch(
            "app.engine.multi_agent.agent_loop.agentic_loop",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            events = []
            async for event in agentic_loop_streaming(
                "query", [], "prompt",
            ):
                events.append(event)

            assert len(events) >= 1
            last = events[-1]
            assert last["type"] == "answer"
            assert last["content"] == "final answer"

    @pytest.mark.asyncio
    async def test_max_steps_enforced(self):
        """Loop should respect max_steps."""
        config = LoopConfig(max_steps=1)
        mock_result = LoopResult(response="done", steps=1)

        with patch(
            "app.engine.multi_agent.agent_loop.agentic_loop",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            events = []
            async for event in agentic_loop_streaming(
                "query", [], "prompt", config,
            ):
                events.append(event)

            answer_events = [e for e in events if e["type"] == "answer"]
            assert len(answer_events) == 1

    @pytest.mark.asyncio
    async def test_empty_tools_no_crash(self):
        """Should work fine with empty tools list."""
        mock_result = LoopResult(response="no tools", steps=1)

        with patch(
            "app.engine.multi_agent.agent_loop.agentic_loop",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            events = []
            async for event in agentic_loop_streaming(
                "query", [], "prompt",
            ):
                events.append(event)

            assert any(e["type"] == "answer" for e in events)

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Streaming should handle loop errors gracefully."""
        with patch(
            "app.engine.multi_agent.agent_loop.agentic_loop",
            new_callable=AsyncMock,
            side_effect=ValueError("LLM error"),
        ):
            events = []
            async for event in agentic_loop_streaming(
                "query", [], "prompt",
            ):
                events.append(event)

            assert any(e["type"] == "error" for e in events)

    @pytest.mark.asyncio
    async def test_queue_events_yielded_before_answer(self):
        """Events pushed to queue during loop should be yielded before answer."""
        async def mock_loop(query, tools, prompt, config, context):
            # Push events to queue during execution
            if config.event_queue:
                config.event_queue.put_nowait({
                    "type": "thinking_delta",
                    "content": "thinking...",
                    "node": "test",
                })
                config.event_queue.put_nowait({
                    "type": "tool_call",
                    "content": {"name": "search", "args": {}, "id": "c1"},
                    "node": "test",
                })
            return LoopResult(response="answer", steps=1)

        with patch(
            "app.engine.multi_agent.agent_loop.agentic_loop",
            side_effect=mock_loop,
        ):
            events = []
            async for event in agentic_loop_streaming(
                "query", [], "prompt",
            ):
                events.append(event)

            types = [e["type"] for e in events]
            # thinking_delta and tool_call should come before answer
            assert "thinking_delta" in types
            assert "tool_call" in types
            answer_idx = types.index("answer")
            td_idx = types.index("thinking_delta")
            assert td_idx < answer_idx
