"""
Tests for RAGAgentNode - Knowledge Retrieval Specialist.

Tests CorrectiveRAG delegation, state wiring, error handling,
and thinking/reasoning_trace propagation.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_crag_result(**overrides):
    """Build a mock CorrectiveRAGResult."""
    defaults = {
        "answer": "Rule 13 quy định về tàu vượt...",
        "sources": [{"title": "COLREGs", "page": 13}],
        "confidence": 85.0,
        "reasoning_trace": None,
        "thinking_content": None,
        "thinking": None,
        "grading_result": None,
    }
    defaults.update(overrides)
    result = MagicMock()
    for k, v in defaults.items():
        setattr(result, k, v)
    return result


def _make_node(crag_mock):
    """Create RAGAgentNode with injected CorrectiveRAG mock."""
    with patch(
        "app.engine.multi_agent.agents.rag_node.get_corrective_rag",
        return_value=crag_mock,
    ):
        from app.engine.multi_agent.agents.rag_node import RAGAgentNode
        return RAGAgentNode()


@pytest.fixture
def base_state():
    return {
        "query": "COLREGs Rule 13 là gì?",
        "user_id": "user-1",
        "session_id": "sess-1",
        "context": {"history": "previous chat"},
    }


# ---------------------------------------------------------------------------
# process() happy path
# ---------------------------------------------------------------------------

class TestRAGAgentProcess:
    @pytest.mark.asyncio
    async def test_process_happy_path(self, base_state):
        crag = MagicMock()
        crag.process = AsyncMock(return_value=_make_crag_result())
        crag.is_available.return_value = True
        node = _make_node(crag)

        result = await node.process(base_state)

        assert result["rag_output"] == "Rule 13 quy định về tàu vượt..."
        assert result["sources"] == [{"title": "COLREGs", "page": 13}]
        assert result["agent_outputs"]["rag"] == result["rag_output"]
        assert result["current_agent"] == "rag_agent"

    @pytest.mark.asyncio
    async def test_process_no_sources(self, base_state):
        crag = MagicMock()
        crag.process = AsyncMock(return_value=_make_crag_result(sources=[]))
        node = _make_node(crag)

        result = await node.process(base_state)
        assert result["sources"] == []

    @pytest.mark.asyncio
    async def test_process_crag_error(self, base_state):
        crag = MagicMock()
        crag.process = AsyncMock(side_effect=Exception("CRAG unavailable"))
        node = _make_node(crag)

        result = await node.process(base_state)

        assert "Wiii tìm kiếm bị trục trặc" in result["rag_output"]
        assert result["error"] == "rag_error"


# ---------------------------------------------------------------------------
# Thinking / reasoning_trace propagation
# ---------------------------------------------------------------------------

class TestRAGThinkingPropagation:
    @pytest.mark.asyncio
    async def test_reasoning_trace_propagated(self, base_state):
        trace = MagicMock()
        trace.total_steps = 5
        crag = MagicMock()
        crag.process = AsyncMock(return_value=_make_crag_result(reasoning_trace=trace))
        node = _make_node(crag)

        result = await node.process(base_state)
        assert result["reasoning_trace"] is trace

    @pytest.mark.asyncio
    async def test_thinking_content_propagated(self, base_state):
        crag = MagicMock()
        crag.process = AsyncMock(
            return_value=_make_crag_result(thinking_content="Phân tích query...")
        )
        node = _make_node(crag)

        result = await node.process(base_state)
        assert result["thinking_content"] == "Phân tích query..."

    @pytest.mark.asyncio
    async def test_native_thinking_propagated(self, base_state):
        crag = MagicMock()
        crag.process = AsyncMock(
            return_value=_make_crag_result(thinking="<thinking>Deep analysis</thinking>")
        )
        node = _make_node(crag)

        result = await node.process(base_state)
        assert result["thinking"] == "<thinking>Deep analysis</thinking>"

    @pytest.mark.asyncio
    async def test_no_thinking_fields_when_absent(self, base_state):
        crag = MagicMock()
        crag.process = AsyncMock(return_value=_make_crag_result())
        node = _make_node(crag)

        result = await node.process(base_state)
        assert "thinking" not in result
        assert "thinking_content" not in result
        assert "reasoning_trace" not in result


# ---------------------------------------------------------------------------
# Grading result
# ---------------------------------------------------------------------------

class TestRAGGradingResult:
    @pytest.mark.asyncio
    async def test_grading_score_set(self, base_state):
        grading = MagicMock()
        grading.avg_score = 8.5
        crag = MagicMock()
        crag.process = AsyncMock(return_value=_make_crag_result(grading_result=grading))
        node = _make_node(crag)

        result = await node.process(base_state)
        assert result["grader_score"] == 8.5

    @pytest.mark.asyncio
    async def test_no_grading_score_when_absent(self, base_state):
        crag = MagicMock()
        crag.process = AsyncMock(return_value=_make_crag_result())
        node = _make_node(crag)

        result = await node.process(base_state)
        assert "grader_score" not in result


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

class TestRAGProperties:
    def test_config_property(self):
        crag = MagicMock()
        node = _make_node(crag)
        from app.engine.agents import RAG_AGENT_CONFIG
        assert node.config is RAG_AGENT_CONFIG

    def test_agent_id(self):
        crag = MagicMock()
        node = _make_node(crag)
        assert node.agent_id == "rag_agent"

    def test_is_available_delegates_to_crag(self):
        crag = MagicMock()
        crag.is_available.return_value = True
        node = _make_node(crag)
        assert node.is_available() is True

        crag.is_available.return_value = False
        assert node.is_available() is False


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestRAGSingleton:
    def test_get_rag_agent_node_returns_instance(self):
        import app.engine.multi_agent.agents.rag_node as mod
        mod._rag_node = None
        try:
            with patch.object(mod, "get_corrective_rag", return_value=MagicMock()):
                node = mod.get_rag_agent_node()
                assert isinstance(node, mod.RAGAgentNode)
                node2 = mod.get_rag_agent_node()
                assert node is node2
        finally:
            mod._rag_node = None


class TestRAGStreamingSurfaceSanitization:
    @pytest.mark.asyncio
    async def test_retrieval_thinking_is_sanitized_before_surface(self, base_state):
        async def fake_streaming(query, context):
            yield {"type": "thinking", "content": "Tìm thấy 0 tài liệu liên quan", "step": "retrieval"}
            yield {"type": "result", "data": _make_crag_result()}

        crag = MagicMock()
        crag.process_streaming = fake_streaming
        crag.is_available.return_value = True
        node = _make_node(crag)

        event_queue = asyncio.Queue()
        mock_beat = MagicMock()
        mock_beat.label = "Mình đang rà nguồn phù hợp trước khi chốt câu trả lời."
        mock_beat.summary = "Đang kiểm tra nguồn phù hợp."
        mock_beat.phase = "retrieve"

        with patch("app.engine.multi_agent.agents.rag_node.get_reasoning_narrator") as mock_narrator_fn:
            mock_narrator = MagicMock()
            mock_narrator.render = AsyncMock(return_value=mock_beat)
            mock_narrator_fn.return_value = mock_narrator

            result = await node._process_with_streaming("có thể uống rượu thưởng trăng không ?", base_state, event_queue)

        assert result is not None

        queue_items = []
        while not event_queue.empty():
            queue_items.append(event_queue.get_nowait())

        thinking_deltas = [item for item in queue_items if item.get("type") == "thinking_delta"]
        assert thinking_deltas, "Expected sanitized thinking_delta event"
        assert "Tìm thấy 0 tài liệu liên quan" not in thinking_deltas[0]["content"]
        assert "nguồn nào thật sự khớp" in thinking_deltas[0]["content"].lower()
    @pytest.mark.asyncio
    async def test_analysis_telemetry_is_demoted_to_status_only(self, base_state):
        async def fake_streaming(query, context):
            yield {
                "type": "thinking",
                "content": "Do phuc tap: simple\nChu de: dau, tai chinh\nDo tin cay phan tich: 100%",
                "step": "analysis",
            }
            yield {"type": "result", "data": _make_crag_result()}

        crag = MagicMock()
        crag.process_streaming = fake_streaming
        crag.is_available.return_value = True
        node = _make_node(crag)

        event_queue = asyncio.Queue()
        result = await node._process_with_streaming("gia dau hom nay", base_state, event_queue)

        assert result is not None

        queue_items = []
        while not event_queue.empty():
            queue_items.append(event_queue.get_nowait())

        assert not [item for item in queue_items if item.get("type") == "thinking_delta"]
        status_events = [item for item in queue_items if item.get("type") == "status"]
        assert status_events
        assert status_events[0]["details"]["visibility"] == "status_only"
        assert status_events[0]["details"]["rag_step"] == "analysis"

    @pytest.mark.asyncio
    async def test_sync_telemetry_thinking_is_not_propagated(self, base_state):
        crag = MagicMock()
        crag.process = AsyncMock(
            return_value=_make_crag_result(
                thinking_content="Do phuc tap: simple\nChu de: dau\nDo tin cay phan tich: 100%",
                thinking="Chien luoc tim kiem: rag",
            )
        )
        node = _make_node(crag)

        result = await node.process(base_state)

        assert "thinking_content" not in result
        assert "thinking" not in result
