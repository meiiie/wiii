"""
Tests for Sprint 44: MiniJudgeGrader coverage.

Tests LLM Mini-Judge binary relevance grading including:
- MiniJudgeResult/MiniJudgeConfig dataclasses
- Prompt building
- Single document judging with mock LLM
- Batch pre-grading
- Filtering docs for full grading
- Disabled behavior
- Error/timeout handling
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================================
# MiniJudgeResult dataclass
# ============================================================================


class TestMiniJudgeResult:
    """Test MiniJudgeResult dataclass."""

    def test_relevant_result(self):
        from app.engine.agentic_rag.mini_judge_grader import MiniJudgeResult
        result = MiniJudgeResult(
            document_id="doc1",
            content_preview="COLREGs Rule 15",
            is_relevant=True,
            confidence="high",
            reason="Mini-Judge: yes",
            latency_ms=150.0
        )
        assert result.is_relevant is True
        assert result.confidence == "high"

    def test_irrelevant_result(self):
        from app.engine.agentic_rag.mini_judge_grader import MiniJudgeResult
        result = MiniJudgeResult(
            document_id="doc2",
            content_preview="Unrelated",
            is_relevant=False,
            confidence="high",
            reason="Mini-Judge: no",
            latency_ms=120.0
        )
        assert result.is_relevant is False


# ============================================================================
# MiniJudgeConfig
# ============================================================================


class TestMiniJudgeConfig:
    """Test MiniJudgeConfig defaults and customization."""

    def test_defaults(self):
        from app.engine.agentic_rag.mini_judge_grader import MiniJudgeConfig
        config = MiniJudgeConfig()
        assert config.max_parallel == 10
        assert config.timeout_seconds == 4.0
        assert config.max_doc_chars == 300
        assert config.max_query_chars == 200
        assert config.on_error == "uncertain"
        assert config.enabled is True

    def test_custom_config(self):
        from app.engine.agentic_rag.mini_judge_grader import MiniJudgeConfig
        config = MiniJudgeConfig(
            max_parallel=5,
            timeout_seconds=2.0,
            enabled=False
        )
        assert config.max_parallel == 5
        assert config.timeout_seconds == 2.0
        assert config.enabled is False


# ============================================================================
# MiniJudgeGrader initialization
# ============================================================================


class TestMiniJudgeGraderInit:
    """Test MiniJudgeGrader initialization."""

    def test_default_init(self):
        with patch("app.engine.agentic_rag.mini_judge_grader.get_llm_light"):
            from app.engine.agentic_rag.mini_judge_grader import MiniJudgeGrader
            grader = MiniJudgeGrader()
            assert grader._llm is None
            assert grader._initialized is False

    def test_custom_config(self):
        with patch("app.engine.agentic_rag.mini_judge_grader.get_llm_light"):
            from app.engine.agentic_rag.mini_judge_grader import MiniJudgeGrader, MiniJudgeConfig
            config = MiniJudgeConfig(max_parallel=3)
            grader = MiniJudgeGrader(config=config)
            assert grader._config.max_parallel == 3

    def test_lazy_llm(self):
        """LLM is lazily initialized."""
        mock_llm = MagicMock()
        with patch("app.engine.agentic_rag.mini_judge_grader.get_llm_light", return_value=mock_llm) as mock_get:
            from app.engine.agentic_rag.mini_judge_grader import MiniJudgeGrader
            grader = MiniJudgeGrader()
            # Not called yet
            assert grader._llm is None
            grader._ensure_llm()
            assert grader._llm is mock_llm
            assert grader._initialized is True


# ============================================================================
# Prompt building
# ============================================================================


class TestBuildPrompt:
    """Test _build_prompt."""

    @pytest.fixture
    def grader(self):
        with patch("app.engine.agentic_rag.mini_judge_grader.get_llm_light"):
            from app.engine.agentic_rag.mini_judge_grader import MiniJudgeGrader
            return MiniJudgeGrader()

    def test_basic_prompt(self, grader):
        prompt = grader._build_prompt("What is Rule 15?", "Rule 15 crossing situation")
        assert "Rule 15" in prompt
        assert "yes" in prompt.lower()
        assert "no" in prompt.lower()

    def test_truncation(self, grader):
        """Long query/doc are truncated."""
        long_query = "x" * 500
        long_doc = "y" * 1000
        prompt = grader._build_prompt(long_query, long_doc)
        # Config defaults: max_query_chars=200, max_doc_chars=300
        assert len(prompt) < len(long_query) + len(long_doc)


# ============================================================================
# Single document judging
# ============================================================================


class TestJudgeSingle:
    """Test _judge_single with mock LLM."""

    @pytest.fixture
    def grader_with_llm(self):
        mock_llm = AsyncMock()
        with patch("app.engine.agentic_rag.mini_judge_grader.get_llm_light", return_value=mock_llm):
            from app.engine.agentic_rag.mini_judge_grader import MiniJudgeGrader
            grader = MiniJudgeGrader()
            grader._ensure_llm()
            return grader, mock_llm

    @pytest.mark.asyncio
    async def test_yes_response(self, grader_with_llm):
        """'yes' response marks document as relevant."""
        grader, mock_llm = grader_with_llm
        mock_llm.ainvoke.return_value = MagicMock(content="yes")
        result = await grader._judge_single(
            "What is Rule 15?",
            {"id": "d1", "content": "Rule 15 crossing situation"},
            0
        )
        assert result.is_relevant is True
        assert result.confidence == "high"

    @pytest.mark.asyncio
    async def test_no_response(self, grader_with_llm):
        """'no' response marks document as not relevant."""
        grader, mock_llm = grader_with_llm
        mock_llm.ainvoke.return_value = MagicMock(content="no")
        result = await grader._judge_single(
            "What is Rule 15?",
            {"id": "d1", "content": "Weather forecast for tomorrow"},
            0
        )
        assert result.is_relevant is False
        assert result.confidence == "high"

    @pytest.mark.asyncio
    async def test_ambiguous_with_no_in_word(self, grader_with_llm):
        """Response with 'no' as substring (e.g., 'not') gets medium confidence."""
        grader, mock_llm = grader_with_llm
        # "not" contains "no" as substring, so "no" in result_text is True
        mock_llm.ainvoke.return_value = MagicMock(content="I'm not sure about this")
        result = await grader._judge_single("query", {"id": "d1", "content": "text"}, 0)
        assert result.confidence == "medium"
        # "no" in first 10 chars "i'm not su" is True, so is_relevant depends on "yes" check
        assert result.is_relevant is False  # "yes" not in first 10 chars

    @pytest.mark.asyncio
    async def test_truly_ambiguous_response(self, grader_with_llm):
        """Response without yes/no anywhere gets low confidence."""
        grader, mock_llm = grader_with_llm
        mock_llm.ainvoke.return_value = MagicMock(content="I am uncertain about this matter")
        result = await grader._judge_single("query", {"id": "d1", "content": "text"}, 0)
        assert result.confidence == "low"

    @pytest.mark.asyncio
    async def test_yes_beyond_first_10_chars(self, grader_with_llm):
        """'yes' beyond first 10 chars means not relevant."""
        grader, mock_llm = grader_with_llm
        # "i think yes" — "yes" starts at index 8, [:10] = "i think ye" — no "yes"
        mock_llm.ainvoke.return_value = MagicMock(content="I think yes, this is relevant")
        result = await grader._judge_single("query", {"id": "d1", "content": "text"}, 0)
        assert result.is_relevant is False  # "yes" not in first 10 chars
        assert result.confidence == "medium"  # "yes" is in full text

    @pytest.mark.asyncio
    async def test_timeout_handling(self, grader_with_llm):
        """Timeout returns low confidence result."""
        grader, mock_llm = grader_with_llm
        mock_llm.ainvoke.side_effect = asyncio.TimeoutError()
        result = await grader._judge_single("query", {"id": "d1", "content": "text"}, 0)
        assert result.confidence == "low"
        assert "Timeout" in result.reason

    @pytest.mark.asyncio
    async def test_error_handling(self, grader_with_llm):
        """Error returns low confidence result."""
        grader, mock_llm = grader_with_llm
        mock_llm.ainvoke.side_effect = Exception("LLM error")
        result = await grader._judge_single("query", {"id": "d1", "content": "text"}, 0)
        assert result.confidence == "low"
        assert "Error" in result.reason

    @pytest.mark.asyncio
    async def test_on_error_relevant_config(self):
        """on_error='relevant' makes errors return relevant."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception("fail")
        with patch("app.engine.agentic_rag.mini_judge_grader.get_llm_light", return_value=mock_llm):
            from app.engine.agentic_rag.mini_judge_grader import MiniJudgeGrader, MiniJudgeConfig
            grader = MiniJudgeGrader(config=MiniJudgeConfig(on_error="relevant"))
            grader._ensure_llm()
            result = await grader._judge_single("q", {"id": "d1", "content": "c"}, 0)
            assert result.is_relevant is True

    @pytest.mark.asyncio
    async def test_list_content_response(self, grader_with_llm):
        """Gemini 3 list content format handled."""
        grader, mock_llm = grader_with_llm
        mock_llm.ainvoke.return_value = MagicMock(content=[
            {"type": "text", "text": "yes"}
        ])
        result = await grader._judge_single("q", {"id": "d1", "content": "c"}, 0)
        assert result.is_relevant is True

    @pytest.mark.asyncio
    async def test_doc_id_fallback(self, grader_with_llm):
        """Missing 'id' falls back to doc_index."""
        grader, mock_llm = grader_with_llm
        mock_llm.ainvoke.return_value = MagicMock(content="yes")
        result = await grader._judge_single("q", {"content": "text"}, 7)
        assert result.document_id == "doc_7"


# ============================================================================
# Batch pre-grading
# ============================================================================


class TestPreGradeBatch:
    """Test pre_grade_batch."""

    @pytest.mark.asyncio
    async def test_empty_documents(self):
        with patch("app.engine.agentic_rag.mini_judge_grader.get_llm_light"):
            from app.engine.agentic_rag.mini_judge_grader import MiniJudgeGrader
            grader = MiniJudgeGrader()
            results = await grader.pre_grade_batch("query", [])
            assert results == []

    @pytest.mark.asyncio
    async def test_disabled_returns_all_relevant(self):
        """Disabled grader marks all as relevant with low confidence."""
        with patch("app.engine.agentic_rag.mini_judge_grader.get_llm_light"):
            from app.engine.agentic_rag.mini_judge_grader import MiniJudgeGrader, MiniJudgeConfig
            grader = MiniJudgeGrader(config=MiniJudgeConfig(enabled=False))
            docs = [
                {"id": "d1", "content": "text1"},
                {"id": "d2", "content": "text2"},
            ]
            results = await grader.pre_grade_batch("query", docs)
            assert len(results) == 2
            assert all(r.is_relevant for r in results)
            assert all(r.confidence == "low" for r in results)
            assert all(r.latency_ms == 0 for r in results)

    @pytest.mark.asyncio
    async def test_batch_calls_llm_for_each(self):
        """Batch calls LLM for each document."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content="yes")
        with patch("app.engine.agentic_rag.mini_judge_grader.get_llm_light", return_value=mock_llm):
            from app.engine.agentic_rag.mini_judge_grader import MiniJudgeGrader
            grader = MiniJudgeGrader()
            docs = [
                {"id": "d1", "content": "text1"},
                {"id": "d2", "content": "text2"},
                {"id": "d3", "content": "text3"},
            ]
            results = await grader.pre_grade_batch("Rule 15?", docs)
            assert len(results) == 3
            assert mock_llm.ainvoke.call_count == 3


# ============================================================================
# get_docs_for_full_grading
# ============================================================================


class TestGetDocsForFullGrading:
    """Test get_docs_for_full_grading filtering."""

    @pytest.fixture
    def grader(self):
        with patch("app.engine.agentic_rag.mini_judge_grader.get_llm_light"):
            from app.engine.agentic_rag.mini_judge_grader import MiniJudgeGrader
            return MiniJudgeGrader()

    def test_all_relevant_high_confidence(self, grader):
        """All relevant with high confidence returns no docs for grading."""
        from app.engine.agentic_rag.mini_judge_grader import MiniJudgeResult
        docs = [{"id": "d1"}, {"id": "d2"}]
        results = [
            MiniJudgeResult("d1", "p1", True, "high", "yes", 100),
            MiniJudgeResult("d2", "p2", True, "medium", "yes", 100),
        ]
        for_grading, relevant = grader.get_docs_for_full_grading(docs, results)
        assert len(for_grading) == 0
        assert len(relevant) == 2

    def test_mixed_results(self, grader):
        """Mixed results split correctly."""
        from app.engine.agentic_rag.mini_judge_grader import MiniJudgeResult
        docs = [{"id": "d1"}, {"id": "d2"}, {"id": "d3"}]
        results = [
            MiniJudgeResult("d1", "p1", True, "high", "yes", 100),
            MiniJudgeResult("d2", "p2", False, "high", "no", 100),
            MiniJudgeResult("d3", "p3", True, "low", "maybe", 100),
        ]
        for_grading, relevant = grader.get_docs_for_full_grading(docs, results)
        assert len(relevant) == 1  # Only d1 (high confidence + relevant)
        assert len(for_grading) == 2  # d2 (not relevant) + d3 (low confidence)

    def test_max_docs_limit(self, grader):
        """Respects max_docs limit."""
        from app.engine.agentic_rag.mini_judge_grader import MiniJudgeResult
        docs = [{"id": f"d{i}"} for i in range(10)]
        results = [
            MiniJudgeResult(f"d{i}", f"p{i}", False, "high", "no", 100)
            for i in range(10)
        ]
        for_grading, _ = grader.get_docs_for_full_grading(docs, results, max_docs=3)
        assert len(for_grading) == 3
