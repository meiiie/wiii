"""
Tests for Sprint 39: QueryAnalyzer rule-based analysis + str(e) leak fixes.

Covers:
- QueryComplexity enum
- QueryAnalysis dataclass
- _rule_based_analysis() pure logic: complexity, topics, multi-step, verification
- str(e) not leaked in HTTP-facing API responses
"""

import pytest
from unittest.mock import patch, MagicMock

from app.engine.agentic_rag.query_analyzer import (
    QueryAnalysis,
    QueryComplexity,
)


# ============================================================================
# QueryComplexity enum
# ============================================================================


class TestQueryComplexity:
    def test_values(self):
        assert QueryComplexity.SIMPLE == "simple"
        assert QueryComplexity.MODERATE == "moderate"
        assert QueryComplexity.COMPLEX == "complex"

    def test_from_string(self):
        assert QueryComplexity("simple") == QueryComplexity.SIMPLE
        assert QueryComplexity("complex") == QueryComplexity.COMPLEX


# ============================================================================
# QueryAnalysis dataclass
# ============================================================================


class TestQueryAnalysis:
    def test_defaults(self):
        qa = QueryAnalysis(
            original_query="test",
            complexity=QueryComplexity.SIMPLE,
        )
        assert qa.requires_multi_step is False
        assert qa.requires_verification is False
        assert qa.is_domain_related is True
        assert qa.suggested_sub_queries == []
        assert qa.detected_topics == []
        assert qa.confidence == 0.8

    def test_str_representation(self):
        qa = QueryAnalysis(
            original_query="test",
            complexity=QueryComplexity.COMPLEX,
            requires_multi_step=True,
        )
        s = str(qa)
        assert "complex" in s
        assert "True" in s


# ============================================================================
# _rule_based_analysis() pure logic
# ============================================================================


class TestRuleBasedAnalysis:
    @pytest.fixture
    def analyzer(self):
        """Create analyzer with LLM disabled (uses rule-based path)."""
        with patch("app.engine.agentic_rag.query_analyzer.get_llm_light", return_value=None):
            from app.engine.agentic_rag.query_analyzer import QueryAnalyzer
            a = QueryAnalyzer()
            a._llm = None  # Force rule-based
        return a

    # Simple queries
    def test_simple_query(self, analyzer):
        result = analyzer._rule_based_analysis("Rule 15 là gì?")
        assert result.complexity == QueryComplexity.SIMPLE
        assert result.requires_multi_step is False

    def test_simple_english(self, analyzer):
        result = analyzer._rule_based_analysis("What is SOLAS?")
        assert result.complexity == QueryComplexity.SIMPLE

    # Moderate queries
    def test_moderate_why(self, analyzer):
        result = analyzer._rule_based_analysis("Tại sao Rule 15 quan trọng?")
        assert result.complexity == QueryComplexity.MODERATE
        assert result.requires_verification is True

    def test_moderate_how(self, analyzer):
        result = analyzer._rule_based_analysis("How does Rule 15 work?")
        assert result.complexity == QueryComplexity.MODERATE

    def test_moderate_explain(self, analyzer):
        result = analyzer._rule_based_analysis("Giải thích quy tắc 15")
        assert result.complexity == QueryComplexity.MODERATE

    def test_moderate_difference(self, analyzer):
        result = analyzer._rule_based_analysis("Khác nhau giữa Rule 15 và 17")
        assert result.complexity == QueryComplexity.MODERATE

    # Complex queries
    def test_complex_compare(self, analyzer):
        result = analyzer._rule_based_analysis("So sánh Rule 15 và Rule 17")
        assert result.complexity == QueryComplexity.COMPLEX
        assert result.requires_multi_step is True
        assert result.requires_verification is True

    def test_complex_analyze(self, analyzer):
        result = analyzer._rule_based_analysis("Analyze all crossing rules")
        assert result.complexity == QueryComplexity.COMPLEX

    def test_complex_list_all(self, analyzer):
        result = analyzer._rule_based_analysis("Liệt kê tất cả quy tắc")
        assert result.complexity == QueryComplexity.COMPLEX

    def test_complex_synthesize(self, analyzer):
        result = analyzer._rule_based_analysis("Tổng hợp các điều về an toàn")
        assert result.complexity == QueryComplexity.COMPLEX

    # Topic detection
    def test_detects_colregs(self, analyzer):
        result = analyzer._rule_based_analysis("COLREGs rule 15")
        assert "COLREGs" in result.detected_topics

    def test_detects_solas(self, analyzer):
        result = analyzer._rule_based_analysis("SOLAS chapter V")
        assert "SOLAS" in result.detected_topics

    def test_detects_marpol(self, analyzer):
        result = analyzer._rule_based_analysis("MARPOL annex VI")
        assert "MARPOL" in result.detected_topics

    def test_detects_vietnamese_keywords(self, analyzer):
        result = analyzer._rule_based_analysis("Quy tắc 15 của luật hàng hải")
        assert len(result.detected_topics) >= 2  # "Rules" + "Law"

    def test_no_domain_keywords(self, analyzer):
        result = analyzer._rule_based_analysis("Hello, how are you?")
        assert result.is_domain_related is False
        assert len(result.detected_topics) == 0

    # Confidence
    def test_rule_based_confidence(self, analyzer):
        result = analyzer._rule_based_analysis("test")
        assert result.confidence == 0.7  # Lower than LLM-based

    # Original query preserved
    def test_preserves_original(self, analyzer):
        query = "What is Rule 15?"
        result = analyzer._rule_based_analysis(query)
        assert result.original_query == query

    # Complex overrides moderate
    def test_complex_overrides_moderate(self, analyzer):
        """If query matches both complex and moderate, complex wins."""
        result = analyzer._rule_based_analysis("Phân tích tại sao Rule 15 quan trọng")
        assert result.complexity == QueryComplexity.COMPLEX


# ============================================================================
# str(e) not leaked in API responses — regression tests
# ============================================================================


class TestNoStrELeaks:
    """Verify str(e) is not used in any HTTP-facing response in app/api/."""

    @pytest.mark.parametrize("filepath", [
        "app/api/v1/chat_stream.py",
        "app/api/v1/knowledge.py",
        "app/api/v1/webhook.py",
        "app/api/v1/websocket.py",
        "app/api/v1/health.py",
    ])
    def test_no_str_e_in_response_body(self, filepath):
        """API files should not expose str(e) in response bodies."""
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Patterns that leak exceptions to clients
        # Allow: logger.error(f"...{e}") — that's safe (server-side only)
        # Deny: format_sse("error", {"message": f"...{str(e)}"})
        # Deny: raise HTTPException(detail=f"...{str(e)}")
        # Deny: "reason": str(e)
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Skip logger lines
            if stripped.startswith("logger."):
                continue
            # Check for str(e) in remaining lines
            if "str(e)" in stripped:
                # Allow admin.py internal job state and debug-only
                if "debug" in stripped.lower():
                    continue
                if "_ingestion_jobs" in stripped:
                    continue
                pytest.fail(
                    f"{filepath}:{i} leaks str(e) to client: {stripped}"
                )
