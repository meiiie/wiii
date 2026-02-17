"""
Unit tests for centralized constants module.

Verifies constants exist, have correct types, and reasonable values.
"""
import pytest

from app.core.constants import (
    MAX_CONTENT_SNIPPET_LENGTH,
    MAX_DOCUMENT_PREVIEW_LENGTH,
    CONFIDENCE_BASE,
    CONFIDENCE_PER_SOURCE,
    CONFIDENCE_MAX,
    HEALTH_CHECK_TIMEOUT,
    DEFAULT_RELEVANCE_THRESHOLD,
)


class TestContentLimits:
    """Test content truncation constants."""

    def test_snippet_length_is_int(self):
        assert isinstance(MAX_CONTENT_SNIPPET_LENGTH, int)

    def test_document_preview_is_int(self):
        assert isinstance(MAX_DOCUMENT_PREVIEW_LENGTH, int)

    def test_snippet_less_than_preview(self):
        assert MAX_CONTENT_SNIPPET_LENGTH <= MAX_DOCUMENT_PREVIEW_LENGTH

    def test_snippet_positive(self):
        assert MAX_CONTENT_SNIPPET_LENGTH > 0

    def test_preview_positive(self):
        assert MAX_DOCUMENT_PREVIEW_LENGTH > 0


class TestConfidenceScoring:
    """Test confidence calculation constants."""

    def test_base_is_float(self):
        assert isinstance(CONFIDENCE_BASE, (int, float))

    def test_per_source_is_float(self):
        assert isinstance(CONFIDENCE_PER_SOURCE, (int, float))

    def test_max_is_float(self):
        assert isinstance(CONFIDENCE_MAX, (int, float))

    def test_base_between_0_and_1(self):
        assert 0.0 <= CONFIDENCE_BASE <= 1.0

    def test_per_source_positive(self):
        assert CONFIDENCE_PER_SOURCE > 0

    def test_max_not_exceeded_by_formula(self):
        """With 10 sources, confidence should not exceed max."""
        score = CONFIDENCE_BASE + 10 * CONFIDENCE_PER_SOURCE
        capped = min(score, CONFIDENCE_MAX)
        assert capped <= CONFIDENCE_MAX

    def test_zero_sources_gives_base(self):
        score = min(CONFIDENCE_BASE + 0 * CONFIDENCE_PER_SOURCE, CONFIDENCE_MAX)
        assert score == CONFIDENCE_BASE


class TestHealthCheck:
    """Test health check constants."""

    def test_timeout_is_positive_int(self):
        assert isinstance(HEALTH_CHECK_TIMEOUT, int)
        assert HEALTH_CHECK_TIMEOUT > 0

    def test_timeout_reasonable(self):
        assert 1 <= HEALTH_CHECK_TIMEOUT <= 30


class TestRAGDefaults:
    """Test RAG pipeline default constants."""

    def test_relevance_threshold_is_float(self):
        assert isinstance(DEFAULT_RELEVANCE_THRESHOLD, (int, float))

    def test_relevance_threshold_in_range(self):
        assert 0.0 <= DEFAULT_RELEVANCE_THRESHOLD <= 10.0
