"""
Tests for GraderAgentNode - Quality Control Specialist.

Tests LLM grading, rule-based fallback, JSON parsing, and state wiring.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# ---------------------------------------------------------------------------
# Sprint 103: These tests validate legacy text-based grading.
# Structured grading tested in test_sprint67_structured_outputs.py.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _force_legacy_grading(monkeypatch):
    """Sprint 103: default changed to True — force legacy path for these tests."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "enable_structured_outputs", False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node(llm=None):
    """Create GraderAgentNode with optional mocked LLM."""
    with patch(
        "app.engine.multi_agent.agents.grader_agent.get_llm_moderate",
        return_value=llm,
    ):
        from app.engine.multi_agent.agents.grader_agent import GraderAgentNode
        return GraderAgentNode()


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.ainvoke = AsyncMock()
    return llm


@pytest.fixture
def base_state():
    return {
        "query": "Giải thích COLREGs Rule 13",
        "agent_outputs": {
            "rag": "Rule 13 quy định về tàu vượt. Tàu vượt phải nhường đường cho tàu bị vượt."
        },
    }


# Patch target: lazy import inside _grade_response() does
# `from app.services.output_processor import extract_thinking_from_response`
# so we patch at the SOURCE module.
EXTRACT_THINKING_PATCH = "app.services.output_processor.extract_thinking_from_response"


# ---------------------------------------------------------------------------
# process() tests
# ---------------------------------------------------------------------------

class TestGraderProcess:
    @pytest.mark.asyncio
    async def test_process_with_rag_output(self, mock_llm, base_state):
        json_str = '{"score": 8, "is_helpful": true, "is_accurate": true, "is_complete": true, "feedback": "Good"}'
        mock_llm.ainvoke.return_value = MagicMock(content=json_str)
        node = _make_node(mock_llm)

        with patch(EXTRACT_THINKING_PATCH, return_value=(json_str, None)):
            result = await node.process(base_state)

        assert result["grader_score"] == 8
        assert result["grader_feedback"] == "Good"
        assert result["current_agent"] == "grader"

    @pytest.mark.asyncio
    async def test_process_with_tutor_output(self, mock_llm):
        state = {
            "query": "Explain Rule 14",
            "agent_outputs": {"tutor": "Rule 14 là head-on situation..."},
        }
        json_str = '{"score": 7, "feedback": "OK"}'
        mock_llm.ainvoke.return_value = MagicMock(content=json_str)
        node = _make_node(mock_llm)

        with patch(EXTRACT_THINKING_PATCH, return_value=(json_str, None)):
            result = await node.process(state)

        assert result["grader_score"] == 7

    @pytest.mark.asyncio
    async def test_process_no_outputs(self):
        state = {"query": "test", "agent_outputs": {}}
        node = _make_node(MagicMock())
        result = await node.process(state)

        assert result["grader_score"] == 0.0
        assert result["grader_feedback"] == "No output to grade"

    @pytest.mark.asyncio
    async def test_process_exception_returns_default_score(self, mock_llm, base_state):
        mock_llm.ainvoke.side_effect = Exception("LLM crash")
        node = _make_node(mock_llm)

        # _grade_response catches exception → fallback; process catches outer
        result = await node.process(base_state)
        # The rule-based fallback should produce some score
        assert isinstance(result["grader_score"], float)
        assert result["current_agent"] == "grader"

    @pytest.mark.asyncio
    async def test_process_memory_output_used(self, mock_llm):
        """When only memory output exists, grader grades that."""
        state = {
            "query": "tên tôi là gì",
            "agent_outputs": {"memory": "Tên bạn là Minh"},
        }
        json_str = '{"score": 6, "feedback": "Simple"}'
        mock_llm.ainvoke.return_value = MagicMock(content=json_str)
        node = _make_node(mock_llm)

        with patch(EXTRACT_THINKING_PATCH, return_value=(json_str, None)):
            result = await node.process(state)

        assert result["grader_score"] == 6


# ---------------------------------------------------------------------------
# _grade_response() tests
# ---------------------------------------------------------------------------

class TestGradeResponse:
    @pytest.mark.asyncio
    async def test_llm_returns_valid_json(self, mock_llm):
        json_str = '{"score": 9, "is_helpful": true, "is_accurate": true, "is_complete": true, "feedback": "Excellent"}'
        mock_llm.ainvoke.return_value = MagicMock(content=json_str)
        node = _make_node(mock_llm)

        with patch(EXTRACT_THINKING_PATCH, return_value=(json_str, None)):
            result = await node._grade_response("test query", "detailed answer")

        assert result["score"] == 9
        assert result["feedback"] == "Excellent"

    @pytest.mark.asyncio
    async def test_llm_returns_markdown_json(self, mock_llm):
        md_json = '```json\n{"score": 7, "feedback": "Good"}\n```'
        mock_llm.ainvoke.return_value = MagicMock(content=md_json)
        node = _make_node(mock_llm)

        with patch(EXTRACT_THINKING_PATCH, return_value=(md_json, None)):
            result = await node._grade_response("query", "answer")

        assert result["score"] == 7

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_rule_based(self, mock_llm):
        mock_llm.ainvoke.side_effect = Exception("API error")
        node = _make_node(mock_llm)

        result = await node._grade_response("COLREGs Rule 13", "Rule 13 quy định về tàu vượt")
        assert result["feedback"] == "Rule-based grading"
        assert isinstance(result["score"], float)

    @pytest.mark.asyncio
    async def test_no_llm_uses_rule_based(self):
        node = _make_node(None)
        result = await node._grade_response("test", "a short answer")
        assert result["feedback"] == "Rule-based grading"

    @pytest.mark.asyncio
    async def test_invalid_json_falls_back(self, mock_llm):
        mock_llm.ainvoke.return_value = MagicMock(content="not json at all")
        node = _make_node(mock_llm)

        with patch(EXTRACT_THINKING_PATCH, return_value=("not json at all", None)):
            result = await node._grade_response("query", "answer")

        assert result["feedback"] == "Rule-based grading"

    @pytest.mark.asyncio
    async def test_answer_truncated_for_grading(self, mock_llm):
        """Answer longer than 1500 chars is truncated in prompt."""
        json_str = '{"score": 7, "feedback": "OK"}'
        mock_llm.ainvoke.return_value = MagicMock(content=json_str)
        node = _make_node(mock_llm)

        long_answer = "A" * 3000

        with patch(EXTRACT_THINKING_PATCH, return_value=(json_str, None)):
            result = await node._grade_response("query", long_answer)

        # Verify LLM was called (meaning truncation didn't crash)
        assert mock_llm.ainvoke.called
        assert result["score"] == 7


# ---------------------------------------------------------------------------
# _rule_based_grade() tests
# ---------------------------------------------------------------------------

class TestRuleBasedGrade:
    def test_long_answer_high_score(self):
        node = _make_node(None)
        answer = "A " * 300  # > 500 chars
        result = node._rule_based_grade("test query", answer)
        # base 5 + 1 (>100) + 1 (>500) + coverage
        assert result["score"] >= 7.0

    def test_short_answer_low_score(self):
        node = _make_node(None)
        result = node._rule_based_grade("test query", "ok")
        # base 5.0, short answer, low coverage
        assert result["score"] <= 7.0

    def test_query_word_coverage(self):
        node = _make_node(None)
        result = node._rule_based_grade(
            "COLREGs Rule 13",
            "COLREGs Rule 13 quy định về tàu vượt"  # all query words present
        )
        # High coverage should boost score
        assert result["score"] >= 6.0

    def test_score_capped_at_10(self):
        node = _make_node(None)
        # Very long answer with full coverage
        answer = "a b c d e f g " * 200
        result = node._rule_based_grade("a b c", answer)
        assert result["score"] <= 10.0

    def test_is_complete_flag(self):
        node = _make_node(None)
        short = node._rule_based_grade("q", "short")
        long_ = node._rule_based_grade("q", "a " * 150)
        assert short["is_complete"] is False
        assert long_["is_complete"] is True

    def test_is_helpful_flag(self):
        node = _make_node(None)
        # Score < 6 → not helpful
        low = node._rule_based_grade("xyz", "no")
        assert low["is_helpful"] is False
        # Score >= 6 → helpful
        high = node._rule_based_grade("test", "test " * 100)
        assert high["is_helpful"] is True


# ---------------------------------------------------------------------------
# is_available() tests
# ---------------------------------------------------------------------------

class TestGraderIsAvailable:
    def test_available_with_llm(self, mock_llm):
        node = _make_node(mock_llm)
        assert node.is_available() is True

    def test_not_available_without_llm(self):
        node = _make_node(None)
        assert node.is_available() is False


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestGraderSingleton:
    def test_get_grader_agent_node_returns_instance(self):
        import app.engine.multi_agent.agents.grader_agent as mod
        mod._grader_node = None
        try:
            with patch.object(mod, "get_llm_moderate", return_value=MagicMock()):
                node = mod.get_grader_agent_node()
                assert isinstance(node, mod.GraderAgentNode)
                node2 = mod.get_grader_agent_node()
                assert node is node2
        finally:
            mod._grader_node = None
