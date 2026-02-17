"""
Tests for Sprint 44: RetrievalGrader coverage.

Tests document relevance grading including:
- DocumentGrade/GradingResult dataclasses
- needs_rewrite logic with configurable thresholds
- Rule-based fallback grading
- Batch response parsing
- Feedback generation
- LLM-based single document grading
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass


# ============================================================================
# DocumentGrade dataclass
# ============================================================================


class TestDocumentGrade:
    """Test DocumentGrade dataclass."""

    def test_basic_creation(self):
        from app.engine.agentic_rag.retrieval_grader import DocumentGrade
        grade = DocumentGrade(
            document_id="doc1",
            content_preview="Some content",
            score=8.5,
            is_relevant=True,
            reason="High relevance"
        )
        assert grade.document_id == "doc1"
        assert grade.score == 8.5
        assert grade.is_relevant is True

    def test_irrelevant_document(self):
        from app.engine.agentic_rag.retrieval_grader import DocumentGrade
        grade = DocumentGrade(
            document_id="doc2",
            content_preview="Unrelated",
            score=2.0,
            is_relevant=False,
            reason="Off topic"
        )
        assert grade.is_relevant is False
        assert grade.score == 2.0


# ============================================================================
# GradingResult dataclass
# ============================================================================


class TestGradingResult:
    """Test GradingResult dataclass."""

    def test_empty_grades(self):
        from app.engine.agentic_rag.retrieval_grader import GradingResult
        result = GradingResult(query="test query")
        assert result.avg_score == 0.0
        assert result.relevant_count == 0
        assert result.grades == []

    def test_avg_score_computation(self):
        from app.engine.agentic_rag.retrieval_grader import GradingResult, DocumentGrade
        grades = [
            DocumentGrade("d1", "p1", 8.0, True, "good"),
            DocumentGrade("d2", "p2", 6.0, True, "ok"),
            DocumentGrade("d3", "p3", 2.0, False, "bad"),
        ]
        result = GradingResult(query="test", grades=grades)
        assert abs(result.avg_score - (8.0 + 6.0 + 2.0) / 3) < 0.01
        assert result.relevant_count == 2

    def test_all_relevant(self):
        from app.engine.agentic_rag.retrieval_grader import GradingResult, DocumentGrade
        grades = [
            DocumentGrade("d1", "p1", 9.0, True, "great"),
            DocumentGrade("d2", "p2", 8.0, True, "good"),
        ]
        result = GradingResult(query="test", grades=grades)
        assert result.relevant_count == 2

    def test_needs_rewrite_false_when_has_relevant(self):
        """needs_rewrite is False when at least one doc is relevant."""
        from app.engine.agentic_rag.retrieval_grader import GradingResult, DocumentGrade
        grades = [
            DocumentGrade("d1", "p1", 8.0, True, "good"),
            DocumentGrade("d2", "p2", 2.0, False, "bad"),
        ]
        result = GradingResult(query="test", grades=grades)
        assert result.needs_rewrite is False

    def test_needs_rewrite_true_when_no_relevant_low_score(self):
        """needs_rewrite is True when zero relevant docs and low score."""
        from app.engine.agentic_rag.retrieval_grader import GradingResult, DocumentGrade
        # needs_rewrite does lazy import: from app.core.config import settings
        mock_settings = MagicMock()
        mock_settings.rag_confidence_medium = 0.5
        with patch.dict("sys.modules", {}):
            with patch("app.core.config.settings", mock_settings):
                grades = [
                    DocumentGrade("d1", "p1", 2.0, False, "bad"),
                    DocumentGrade("d2", "p2", 1.0, False, "terrible"),
                ]
                result = GradingResult(query="test", grades=grades)
                # avg_score = 1.5, normalized = 0.15 < 0.5
                assert result.needs_rewrite is True

    def test_needs_rewrite_false_when_no_relevant_high_score(self):
        """needs_rewrite is False when no relevant docs but high avg score."""
        from app.engine.agentic_rag.retrieval_grader import GradingResult, DocumentGrade
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.rag_confidence_medium = 0.5
            grades = [
                DocumentGrade("d1", "p1", 6.0, False, "ok"),
                DocumentGrade("d2", "p2", 6.0, False, "ok"),
            ]
            result = GradingResult(query="test", grades=grades)
            # avg_score = 6.0, normalized = 0.6 >= 0.5
            assert result.needs_rewrite is False


# ============================================================================
# RetrievalGrader initialization
# ============================================================================


class TestRetrievalGraderInit:
    """Test RetrievalGrader initialization."""

    def test_init_no_llm(self):
        """Init with failed LLM falls back to None."""
        with patch("app.engine.agentic_rag.retrieval_grader.get_llm_moderate", side_effect=Exception("No LLM")):
            from app.engine.agentic_rag.retrieval_grader import RetrievalGrader
            grader = RetrievalGrader()
            assert grader._llm is None
            assert grader.is_available() is False

    def test_init_with_llm(self):
        """Init with working LLM."""
        mock_llm = MagicMock()
        with patch("app.engine.agentic_rag.retrieval_grader.get_llm_moderate", return_value=mock_llm):
            from app.engine.agentic_rag.retrieval_grader import RetrievalGrader
            grader = RetrievalGrader()
            assert grader._llm is mock_llm
            assert grader.is_available() is True

    def test_custom_threshold(self):
        """Custom threshold is stored."""
        with patch("app.engine.agentic_rag.retrieval_grader.get_llm_moderate", side_effect=Exception("No LLM")):
            from app.engine.agentic_rag.retrieval_grader import RetrievalGrader
            grader = RetrievalGrader(threshold=8.0)
            assert grader._threshold == 8.0


# ============================================================================
# Rule-based grading (fallback)
# ============================================================================


class TestRuleBasedGrading:
    """Test rule-based fallback grading."""

    @pytest.fixture
    def grader(self):
        with patch("app.engine.agentic_rag.retrieval_grader.get_llm_moderate", side_effect=Exception("No LLM")):
            from app.engine.agentic_rag.retrieval_grader import RetrievalGrader
            return RetrievalGrader()

    def test_high_overlap(self, grader):
        """High keyword overlap gives high score."""
        grade = grader._rule_based_grade(
            "COLREGs Rule 15 crossing",
            "doc1",
            "COLREGs Rule 15 crossing situation requires give-way action"
        )
        assert grade.score > 0
        assert "overlap" in grade.reason.lower()

    def test_no_overlap(self, grader):
        """No keyword overlap gives zero score."""
        grade = grader._rule_based_grade(
            "SOLAS fire safety",
            "doc1",
            "Bermuda triangle mysterious ocean"
        )
        assert grade.score == 0.0
        assert grade.is_relevant is False

    def test_partial_overlap(self, grader):
        """Partial overlap gives moderate score."""
        grade = grader._rule_based_grade(
            "maritime safety regulations port",
            "doc1",
            "port authority safety inspection procedures"
        )
        assert 0 < grade.score <= 10.0

    def test_empty_query(self, grader):
        """Empty query gives zero score."""
        grade = grader._rule_based_grade(
            "",
            "doc1",
            "Some content about maritime regulations"
        )
        assert grade.score == 0.0

    @pytest.mark.asyncio
    async def test_grade_document_falls_back_to_rule(self, grader):
        """grade_document uses rule-based when no LLM."""
        doc = {"id": "doc1", "content": "COLREGs Rule 15 crossing"}
        grade = await grader.grade_document("Rule 15 crossing", doc)
        assert grade.document_id == "doc1"
        assert isinstance(grade.score, float)

    @pytest.mark.asyncio
    async def test_grade_document_uses_node_id(self, grader):
        """Falls back to node_id when id is missing."""
        doc = {"node_id": "node_abc", "content": "some content"}
        grade = await grader.grade_document("query", doc)
        assert grade.document_id == "node_abc"

    @pytest.mark.asyncio
    async def test_grade_document_uses_text_key(self, grader):
        """Falls back to 'text' key when 'content' is missing."""
        doc = {"id": "doc1", "text": "Rule 15 crossing situation"}
        grade = await grader.grade_document("Rule 15", doc)
        assert grade.score > 0


# ============================================================================
# LLM-based single document grading
# ============================================================================


class TestLLMGrading:
    """Test LLM-based grading with mocked LLM."""

    @pytest.fixture(autouse=True)
    def _force_legacy_grading(self, monkeypatch):
        """Sprint 103: default changed to True — force legacy path for these tests."""
        from app.core.config import settings
        monkeypatch.setattr(settings, "enable_structured_outputs", False)

    @pytest.fixture
    def grader_with_llm(self):
        mock_llm = AsyncMock()
        with patch("app.engine.agentic_rag.retrieval_grader.get_llm_moderate", return_value=mock_llm):
            from app.engine.agentic_rag.retrieval_grader import RetrievalGrader
            g = RetrievalGrader()
            return g, mock_llm

    @pytest.mark.asyncio
    async def test_llm_grade_valid_json(self, grader_with_llm):
        """LLM returns valid JSON score."""
        grader, mock_llm = grader_with_llm
        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=(json.dumps({"score": 9.0, "is_relevant": True, "reason": "Direct match"}), None)):
            mock_llm.ainvoke.return_value = MagicMock(content="ignored")
            grade = await grader.grade_document("Rule 15", {"id": "d1", "content": "Rule 15 text"})
            assert grade.score == 9.0
            assert grade.is_relevant is True

    @pytest.mark.asyncio
    async def test_llm_grade_json_in_codeblock(self, grader_with_llm):
        """LLM wraps JSON in markdown code block."""
        grader, mock_llm = grader_with_llm
        json_str = json.dumps({"score": 7.0, "is_relevant": True, "reason": "Related"})
        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=(f"```json\n{json_str}\n```", None)):
            mock_llm.ainvoke.return_value = MagicMock(content="ignored")
            grade = await grader.grade_document("query", {"id": "d1", "content": "content"})
            assert grade.score == 7.0

    @pytest.mark.asyncio
    async def test_llm_grade_failure_falls_back(self, grader_with_llm):
        """LLM failure falls back to rule-based."""
        grader, mock_llm = grader_with_llm
        mock_llm.ainvoke.side_effect = Exception("LLM error")
        grade = await grader.grade_document(
            "Rule 15 crossing",
            {"id": "d1", "content": "Rule 15 crossing situation"}
        )
        # Falls back to rule-based
        assert isinstance(grade.score, (int, float))
        assert "overlap" in grade.reason.lower()


# ============================================================================
# Batch grading
# ============================================================================


class TestBatchGrading:
    """Test batch grading methods."""

    @pytest.fixture
    def grader_no_llm(self):
        with patch("app.engine.agentic_rag.retrieval_grader.get_llm_moderate", side_effect=Exception("No LLM")):
            from app.engine.agentic_rag.retrieval_grader import RetrievalGrader
            return RetrievalGrader()

    @pytest.mark.asyncio
    async def test_batch_empty_documents(self, grader_no_llm):
        """Empty documents list returns empty grades."""
        grades = await grader_no_llm.batch_grade_documents("query", [])
        assert grades == []

    @pytest.mark.asyncio
    async def test_batch_no_llm_uses_rule_based(self, grader_no_llm):
        """Batch grading without LLM uses rule-based for each doc."""
        docs = [
            {"id": "d1", "content": "COLREGs Rule 15"},
            {"id": "d2", "content": "Fire safety SOLAS"},
        ]
        grades = await grader_no_llm.batch_grade_documents("Rule 15 COLREGs", docs)
        assert len(grades) == 2
        # First doc should have higher overlap
        assert grades[0].score > grades[1].score


# ============================================================================
# Batch response parsing
# ============================================================================


class TestBatchResponseParsing:
    """Test _parse_batch_response."""

    @pytest.fixture
    def grader(self):
        with patch("app.engine.agentic_rag.retrieval_grader.get_llm_moderate", side_effect=Exception("No LLM")):
            from app.engine.agentic_rag.retrieval_grader import RetrievalGrader
            return RetrievalGrader()

    def test_parse_valid_json_array(self, grader):
        """Parse valid JSON array response."""
        docs = [
            {"id": "d1", "content": "Content 1"},
            {"id": "d2", "content": "Content 2"},
        ]
        response_data = [
            {"doc_index": 0, "score": 8.0, "is_relevant": True, "reason": "Good"},
            {"doc_index": 1, "score": 3.0, "is_relevant": False, "reason": "Bad"},
        ]
        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=(json.dumps(response_data), None)):
            grades = grader._parse_batch_response("ignored", docs)
            assert len(grades) == 2
            assert grades[0].score == 8.0
            assert grades[0].is_relevant is True
            assert grades[1].score == 3.0

    def test_parse_json_in_codeblock(self, grader):
        """Parse JSON wrapped in code block."""
        docs = [{"id": "d1", "content": "Content"}]
        json_str = json.dumps([{"doc_index": 0, "score": 7.5, "is_relevant": True, "reason": "ok"}])
        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=(f"```json\n{json_str}\n```", None)):
            grades = grader._parse_batch_response("ignored", docs)
            assert len(grades) == 1
            assert grades[0].score == 7.5

    def test_parse_invalid_json_falls_back(self, grader):
        """Invalid JSON falls back to rule-based."""
        docs = [{"id": "d1", "content": "Some content"}]
        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=("not valid json", None)):
            grades = grader._parse_batch_response("ignored", docs)
            assert len(grades) == 1
            # Rule-based fallback
            assert isinstance(grades[0].score, float)

    def test_parse_out_of_range_index_skipped(self, grader):
        """Out-of-range doc_index items are skipped."""
        docs = [{"id": "d1", "content": "Content"}]
        response_data = [
            {"doc_index": 0, "score": 7.0, "is_relevant": True, "reason": "ok"},
            {"doc_index": 5, "score": 9.0, "is_relevant": True, "reason": "phantom"},
        ]
        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=(json.dumps(response_data), None)):
            grades = grader._parse_batch_response("ignored", docs)
            assert len(grades) == 1  # Only doc_index=0 is valid


# ============================================================================
# Feedback generation
# ============================================================================


class TestFeedbackGeneration:
    """Test feedback generation methods."""

    @pytest.fixture
    def grader(self):
        with patch("app.engine.agentic_rag.retrieval_grader.get_llm_moderate", side_effect=Exception("No LLM")):
            from app.engine.agentic_rag.retrieval_grader import RetrievalGrader
            return RetrievalGrader()

    def test_very_low_score_feedback(self, grader):
        """Very low score gets appropriate severity."""
        feedback = grader._build_feedback_direct(2.0, 0, 5, ["Off topic"])
        assert "thấp" in feedback.lower()
        assert "SOLAS" in feedback or "COLREGs" in feedback or "MARPOL" in feedback

    def test_low_score_feedback(self, grader):
        """Low score gets medium severity."""
        feedback = grader._build_feedback_direct(4.0, 0, 5, ["Vague match"])
        assert "thấp" in feedback.lower()

    def test_medium_score_feedback(self, grader):
        """Medium score gets appropriate suggestion."""
        feedback = grader._build_feedback_direct(6.0, 1, 5, ["Partial"])
        assert "trung bình" in feedback.lower()

    def test_unique_issues_dedup(self, grader):
        """Duplicate issues are deduplicated."""
        feedback = grader._build_feedback_direct(
            2.0, 0, 3,
            ["Off topic", "Off topic", "Different issue"]
        )
        # Should contain both unique issues
        assert "Off topic" in feedback
        assert "Different issue" in feedback

    def test_empty_issues(self, grader):
        """Empty issues list uses default message."""
        feedback = grader._build_feedback_direct(3.0, 0, 3, [])
        assert "Documents" in feedback

    @pytest.mark.asyncio
    async def test_generate_feedback_no_llm(self, grader):
        """_generate_feedback without LLM returns simple string."""
        feedback = await grader._generate_feedback("query", 3.0, 0, 5, ["issue"])
        assert "Low relevance" in feedback
        assert "3.0" in feedback


# ============================================================================
# grade_documents (full pipeline)
# ============================================================================


class TestGradeDocumentsPipeline:
    """Test grade_documents orchestration."""

    @pytest.fixture
    def grader_no_llm(self):
        with patch("app.engine.agentic_rag.retrieval_grader.get_llm_moderate", side_effect=Exception("No LLM")):
            from app.engine.agentic_rag.retrieval_grader import RetrievalGrader
            return RetrievalGrader()

    @pytest.mark.asyncio
    async def test_empty_documents(self, grader_no_llm):
        """No documents returns feedback about no documents."""
        result = await grader_no_llm.grade_documents("query", [])
        assert result.grades == []
        assert "No documents" in result.feedback

    @pytest.mark.asyncio
    async def test_with_documents_uses_hybrid(self, grader_no_llm):
        """Documents go through hybrid pre-filter pipeline."""
        mock_evaluator = MagicMock()
        mock_result = MagicMock()
        mock_result.is_high_confidence = True
        mock_result.score = 0.9
        mock_result.bm25_score = 0.8
        mock_result.domain_boost = 0.1
        mock_evaluator.evaluate_batch.return_value = [mock_result]
        mock_evaluator.aggregate_confidence.return_value = 0.85

        mock_judge = AsyncMock()

        with patch("app.engine.agentic_rag.confidence_evaluator.get_hybrid_confidence_evaluator", return_value=mock_evaluator):
            with patch("app.engine.agentic_rag.mini_judge_grader.get_mini_judge_grader", return_value=mock_judge):
                docs = [{"id": "d1", "content": "COLREGs Rule 15"}]
                result = await grader_no_llm.grade_documents("Rule 15", docs)
                assert len(result.grades) == 1
                assert result.grades[0].is_relevant is True
