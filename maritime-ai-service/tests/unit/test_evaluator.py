"""
Tests for Lightweight Evaluation Framework (Sprint 10).

Verifies:
- EvaluationResult dataclass fields and is_acceptable property
- ResponseEvaluator skips when disabled
- ResponseEvaluator skips empty answers
- Score parsing from LLM output
- Weighted average calculation
- Error handling (LLM failure → graceful degradation)
- Evaluator singleton
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from dataclasses import dataclass

from app.engine.evaluation.evaluator import (
    EvaluationResult,
    ResponseEvaluator,
    get_evaluator,
)


class TestEvaluationResult:
    """Test EvaluationResult dataclass."""

    def test_default_values(self):
        """Default result has zero scores."""
        result = EvaluationResult()
        assert result.faithfulness == 0.0
        assert result.answer_relevancy == 0.0
        assert result.context_precision == 0.0
        assert result.overall_score == 0.0
        assert result.details == {}

    def test_is_acceptable_high_score(self):
        """Score >= 0.6 is acceptable."""
        result = EvaluationResult(overall_score=0.75)
        assert result.is_acceptable is True

    def test_is_acceptable_boundary(self):
        """Score exactly 0.6 is acceptable."""
        result = EvaluationResult(overall_score=0.6)
        assert result.is_acceptable is True

    def test_not_acceptable_low_score(self):
        """Score < 0.6 is not acceptable."""
        result = EvaluationResult(overall_score=0.5)
        assert result.is_acceptable is False

    def test_details_dict(self):
        """Details dict stores extra info."""
        result = EvaluationResult(details={"method": "llm_scoring"})
        assert result.details["method"] == "llm_scoring"


class TestResponseEvaluator:
    """Test ResponseEvaluator scoring."""

    @pytest.mark.asyncio
    async def test_skips_when_disabled(self):
        """Evaluation is skipped when enable_evaluation=False."""
        evaluator = ResponseEvaluator()
        with patch("app.engine.evaluation.evaluator.settings") as mock_settings:
            mock_settings.enable_evaluation = False
            result = await evaluator.evaluate(
                query="test query",
                answer="test answer",
            )
        assert result.details.get("skipped") == "evaluation disabled"

    @pytest.mark.asyncio
    async def test_skips_empty_answer(self):
        """Empty answers are skipped."""
        evaluator = ResponseEvaluator()
        with patch("app.engine.evaluation.evaluator.settings") as mock_settings:
            mock_settings.enable_evaluation = True
            result = await evaluator.evaluate(
                query="test query",
                answer="",
            )
        assert result.details.get("skipped") == "empty answer"

    @pytest.mark.asyncio
    async def test_skips_whitespace_answer(self):
        """Whitespace-only answers are skipped."""
        evaluator = ResponseEvaluator()
        with patch("app.engine.evaluation.evaluator.settings") as mock_settings:
            mock_settings.enable_evaluation = True
            result = await evaluator.evaluate(
                query="test query",
                answer="   \n  ",
            )
        assert result.details.get("skipped") == "empty answer"

    @pytest.mark.asyncio
    async def test_successful_evaluation(self):
        """Full evaluation with mocked LLM returns scores."""
        evaluator = ResponseEvaluator()

        mock_response = MagicMock()
        mock_response.content = (
            "faithfulness: 0.8\n"
            "answer_relevancy: 0.9\n"
            "context_precision: 0.7\n"
        )

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        evaluator._llm = mock_llm

        with patch("app.engine.evaluation.evaluator.settings") as mock_settings:
            mock_settings.enable_evaluation = True
            result = await evaluator.evaluate(
                query="What is COLREG rule 5?",
                answer="Rule 5 requires every vessel to maintain a proper lookout.",
                context_chunks=["Rule 5 - Lookout: Every vessel shall maintain a proper lookout."],
            )

        assert result.faithfulness == 0.8
        assert result.answer_relevancy == 0.9
        assert result.context_precision == 0.7
        # Weighted: 0.8*0.4 + 0.9*0.4 + 0.7*0.2 = 0.32 + 0.36 + 0.14 = 0.82
        assert abs(result.overall_score - 0.82) < 0.01

    @pytest.mark.asyncio
    async def test_llm_failure_graceful(self):
        """LLM failure returns zero scores (graceful degradation)."""
        evaluator = ResponseEvaluator()

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM unreachable"))
        evaluator._llm = mock_llm

        with patch("app.engine.evaluation.evaluator.settings") as mock_settings:
            mock_settings.enable_evaluation = True
            result = await evaluator.evaluate(
                query="test",
                answer="test answer",
            )

        # LLM failure is caught inside _score_with_llm → returns zero scores
        assert result.overall_score == 0.0
        assert result.faithfulness == 0.0
        assert result.answer_relevancy == 0.0

    @pytest.mark.asyncio
    async def test_no_context_chunks(self):
        """Evaluation works without context chunks."""
        evaluator = ResponseEvaluator()

        mock_response = MagicMock()
        mock_response.content = (
            "faithfulness: 0.5\n"
            "answer_relevancy: 0.6\n"
            "context_precision: 0.0\n"
        )

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        evaluator._llm = mock_llm

        with patch("app.engine.evaluation.evaluator.settings") as mock_settings:
            mock_settings.enable_evaluation = True
            result = await evaluator.evaluate(
                query="test query",
                answer="test answer",
                context_chunks=None,
            )

        assert result.faithfulness == 0.5
        assert result.context_precision == 0.0


class TestScoreParsing:
    """Test LLM output score parsing."""

    def test_parse_valid_scores(self):
        """Valid score format is parsed correctly."""
        evaluator = ResponseEvaluator()
        content = "faithfulness: 0.8\nanswer_relevancy: 0.9\ncontext_precision: 0.7"
        scores = evaluator._parse_scores(content)

        assert scores["faithfulness"] == 0.8
        assert scores["answer_relevancy"] == 0.9
        assert scores["context_precision"] == 0.7

    def test_parse_clamped_values(self):
        """Values above 1.0 or below 0.0 are clamped."""
        evaluator = ResponseEvaluator()
        content = "faithfulness: 1.5\nanswer_relevancy: -0.3\ncontext_precision: 0.5"
        scores = evaluator._parse_scores(content)

        assert scores["faithfulness"] == 1.0
        assert scores["answer_relevancy"] == 0.0
        assert scores["context_precision"] == 0.5

    def test_parse_with_extra_text(self):
        """Extra text around scores is handled."""
        evaluator = ResponseEvaluator()
        content = (
            "Here are my scores:\n"
            "faithfulness: 0.7\n"
            "answer_relevancy: 0.8\n"
            "context_precision: 0.6\n"
            "Overall the answer is good."
        )
        scores = evaluator._parse_scores(content)
        assert scores["faithfulness"] == 0.7
        assert scores["answer_relevancy"] == 0.8
        assert scores["context_precision"] == 0.6

    def test_parse_invalid_format(self):
        """Invalid format returns 0.0 for missing metrics."""
        evaluator = ResponseEvaluator()
        content = "This is not a valid response"
        scores = evaluator._parse_scores(content)
        assert len(scores) == 0  # No metrics found

    def test_parse_partial_scores(self):
        """Partial scores are handled (missing metrics)."""
        evaluator = ResponseEvaluator()
        content = "faithfulness: 0.9\ncontext_precision: 0.4"
        scores = evaluator._parse_scores(content)
        assert scores["faithfulness"] == 0.9
        assert scores["context_precision"] == 0.4
        assert "answer_relevancy" not in scores


class TestWeightedAverage:
    """Test weighted average calculation."""

    def test_weights_sum_to_one(self):
        """Weights should sum to 1.0."""
        total = sum(ResponseEvaluator.WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_all_perfect_scores(self):
        """All 1.0 scores give 1.0 overall."""
        scores = {
            "faithfulness": 1.0,
            "answer_relevancy": 1.0,
            "context_precision": 1.0,
        }
        overall = sum(
            scores.get(m, 0) * w
            for m, w in ResponseEvaluator.WEIGHTS.items()
        )
        assert abs(overall - 1.0) < 0.001

    def test_all_zero_scores(self):
        """All 0.0 scores give 0.0 overall."""
        scores = {
            "faithfulness": 0.0,
            "answer_relevancy": 0.0,
            "context_precision": 0.0,
        }
        overall = sum(
            scores.get(m, 0) * w
            for m, w in ResponseEvaluator.WEIGHTS.items()
        )
        assert overall == 0.0


class TestEvaluatorSingleton:
    """Test evaluator singleton factory."""

    def test_get_evaluator_returns_instance(self):
        """get_evaluator returns a ResponseEvaluator."""
        evaluator = get_evaluator()
        assert isinstance(evaluator, ResponseEvaluator)

    def test_get_evaluator_singleton(self):
        """get_evaluator returns the same instance."""
        evaluator1 = get_evaluator()
        evaluator2 = get_evaluator()
        assert evaluator1 is evaluator2


class TestEvalPromptBuilding:
    """Test evaluation prompt construction."""

    def test_prompt_with_context(self):
        """Prompt includes context when provided."""
        evaluator = ResponseEvaluator()
        prompt = evaluator._build_eval_prompt(
            query="What is rule 5?",
            answer="Rule 5 is about lookout.",
            context="Rule 5 - Lookout duty",
        )
        assert "QUERY:" in prompt
        assert "CONTEXT:" in prompt
        assert "ANSWER:" in prompt
        assert "faithfulness" in prompt

    def test_prompt_without_context(self):
        """Prompt handles missing context."""
        evaluator = ResponseEvaluator()
        prompt = evaluator._build_eval_prompt(
            query="What is rule 5?",
            answer="Rule 5 is about lookout.",
            context="",
        )
        assert "None provided" in prompt

    def test_prompt_truncates_long_content(self):
        """Long answer/context is truncated to 2000 chars."""
        evaluator = ResponseEvaluator()
        long_answer = "x" * 5000
        prompt = evaluator._build_eval_prompt(
            query="test",
            answer=long_answer,
            context="test context",
        )
        # The prompt itself should contain a truncated version
        # (2000 chars of answer, not full 5000)
        assert len(prompt) < len(long_answer)
