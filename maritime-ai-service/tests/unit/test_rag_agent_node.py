"""
Tests for RAGAgentNode - Knowledge Retrieval Specialist.

Tests CorrectiveRAG delegation, state wiring, error handling,
and thinking/reasoning_trace propagation.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


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

        assert "Xin lỗi" in result["rag_output"]
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
