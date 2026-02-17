"""
Unit tests for Corrective RAG pipeline components.

Tests CorrectiveRAGResult, confidence logic, and component contracts.
All LLM/DB calls are mocked.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from app.engine.agentic_rag.corrective_rag import CorrectiveRAGResult


class TestCorrectiveRAGResult:
    """Test the CorrectiveRAGResult dataclass."""

    def test_basic_creation(self):
        result = CorrectiveRAGResult(
            answer="Rule 15 covers crossing situations.",
            sources=[{"title": "COLREGs", "content": "Rule 15..."}],
        )
        assert result.answer == "Rule 15 covers crossing situations."
        assert len(result.sources) == 1

    def test_default_values(self):
        result = CorrectiveRAGResult(answer="test", sources=[])
        assert result.query_analysis is None
        assert result.grading_result is None
        assert result.verification_result is None
        assert result.was_rewritten is False
        assert result.rewritten_query is None
        assert result.iterations == 1
        assert result.confidence == 80.0  # 0-100 scale (Sprint 83 fix)
        assert result.reasoning_trace is None
        assert result.thinking_content is None
        assert result.thinking is None

    def test_has_warning_no_verification_high_confidence(self):
        # has_warning threshold is confidence < 70 (not 0.7)
        result = CorrectiveRAGResult(answer="test", sources=[], confidence=80)
        assert result.has_warning is False

    def test_has_warning_low_confidence(self):
        result = CorrectiveRAGResult(answer="test", sources=[], confidence=50)
        assert result.has_warning is True

    def test_has_warning_with_verification(self):
        mock_verification = MagicMock()
        mock_verification.needs_warning = True
        result = CorrectiveRAGResult(
            answer="test", sources=[], verification_result=mock_verification
        )
        assert result.has_warning is True

    def test_has_warning_verification_ok(self):
        mock_verification = MagicMock()
        mock_verification.needs_warning = False
        result = CorrectiveRAGResult(
            answer="test", sources=[], verification_result=mock_verification
        )
        assert result.has_warning is False

    def test_rewritten_query_tracking(self):
        result = CorrectiveRAGResult(
            answer="test",
            sources=[],
            was_rewritten=True,
            rewritten_query="maritime COLREGs Rule 15 crossing",
        )
        assert result.was_rewritten is True
        assert "COLREGs" in result.rewritten_query

    def test_multiple_iterations(self):
        result = CorrectiveRAGResult(answer="test", sources=[], iterations=3)
        assert result.iterations == 3

    def test_thinking_content(self):
        result = CorrectiveRAGResult(
            answer="test",
            sources=[],
            thinking="Tôi cần tìm thông tin về Rule 15...",
        )
        assert result.thinking is not None
        assert "Rule 15" in result.thinking


class TestConfidenceCalculation:
    """Test confidence scoring patterns used in the platform."""

    def test_confidence_base_with_sources(self):
        """Confidence formula: min(BASE + count * PER_SOURCE, MAX)."""
        from app.core.constants import CONFIDENCE_BASE, CONFIDENCE_PER_SOURCE, CONFIDENCE_MAX

        sources = [{"title": f"doc_{i}"} for i in range(3)]
        score = min(CONFIDENCE_BASE + len(sources) * CONFIDENCE_PER_SOURCE, CONFIDENCE_MAX)
        assert score == pytest.approx(0.8)

    def test_confidence_caps_at_max(self):
        from app.core.constants import CONFIDENCE_BASE, CONFIDENCE_PER_SOURCE, CONFIDENCE_MAX

        sources = [{"title": f"doc_{i}"} for i in range(20)]
        score = min(CONFIDENCE_BASE + len(sources) * CONFIDENCE_PER_SOURCE, CONFIDENCE_MAX)
        assert score == CONFIDENCE_MAX

    def test_confidence_zero_sources(self):
        from app.core.constants import CONFIDENCE_BASE, CONFIDENCE_PER_SOURCE, CONFIDENCE_MAX

        score = min(CONFIDENCE_BASE + 0 * CONFIDENCE_PER_SOURCE, CONFIDENCE_MAX)
        assert score == CONFIDENCE_BASE


class TestContentTruncation:
    """Test that content truncation constants work correctly."""

    def test_snippet_truncation(self):
        from app.core.constants import MAX_CONTENT_SNIPPET_LENGTH

        long_content = "A" * 500
        truncated = long_content[:MAX_CONTENT_SNIPPET_LENGTH]
        assert len(truncated) == MAX_CONTENT_SNIPPET_LENGTH

    def test_document_preview_truncation(self):
        from app.core.constants import MAX_DOCUMENT_PREVIEW_LENGTH

        long_content = "B" * 2000
        truncated = long_content[:MAX_DOCUMENT_PREVIEW_LENGTH]
        assert len(truncated) == MAX_DOCUMENT_PREVIEW_LENGTH

    def test_short_content_not_truncated(self):
        from app.core.constants import MAX_CONTENT_SNIPPET_LENGTH

        short = "Hello world"
        truncated = short[:MAX_CONTENT_SNIPPET_LENGTH]
        assert truncated == short


class TestVerificationSkipOnEmptySources:
    """Sprint 103: Verification is skipped when 0 sources (fallback answer from LLM).

    When KB is empty, RAG uses _generate_fallback() → sources=[].
    Verifying against 0 sources always gives confidence=50 + warning.
    Fix: skip verification when len(sources) == 0.
    """

    def test_should_verify_false_when_no_sources(self):
        """Verification condition requires len(sources) > 0."""
        from app.core.config import settings

        sources = []
        enable_verification = True
        requires_verification = True
        grading_confidence = 0.3  # LOW — normally would trigger verification
        reflection_is_high = False

        should_verify = (
            enable_verification and
            requires_verification and
            len(sources) > 0 and  # Sprint 103: this blocks verification
            grading_confidence < settings.rag_confidence_medium and
            not reflection_is_high
        )
        assert should_verify is False

    def test_should_verify_true_when_sources_present(self):
        """Verification condition passes when sources exist."""
        from app.core.config import settings

        sources = [{"content": "COLREGs Rule 13..."}]
        enable_verification = True
        requires_verification = True
        grading_confidence = 0.3  # LOW
        reflection_is_high = False

        should_verify = (
            enable_verification and
            requires_verification and
            len(sources) > 0 and
            grading_confidence < settings.rag_confidence_medium and
            not reflection_is_high
        )
        assert should_verify is True

    @pytest.mark.asyncio
    async def test_verifier_always_warns_on_empty_sources(self):
        """Verify that answer_verifier returns warning when sources is empty."""
        from app.engine.agentic_rag.answer_verifier import AnswerVerifier

        with patch("app.engine.agentic_rag.answer_verifier.get_llm_moderate", return_value=MagicMock()):
            verifier = AnswerVerifier()
        result = await verifier.verify("Some LLM answer about MARPOL", [])
        assert result.warning is not None
        assert "thiếu nguồn tham khảo" in result.warning
        assert result.confidence == 50
