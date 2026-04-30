"""
Unit tests for QueryRewriter domain-aware logic.

Tests:
- _get_domain_keywords() with/without domain plugin
- _rule_based_rewrite() with/without keywords
- _add_domain_keywords() expansion logic
- Fallback behavior when LLM unavailable
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engine.agentic_rag.query_rewriter import QueryRewriter


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def rewriter():
    """Create QueryRewriter with mocked LLM (tests rule-based only)."""
    with patch("app.engine.agentic_rag.query_rewriter.get_llm_light", return_value=None), \
         patch("app.engine.agentic_rag.runtime_llm_socket.get_llm_for_provider", return_value=None):
        qr = QueryRewriter()
        qr._llm = None
        qr._resolve_runtime_llm = MagicMock(return_value=None)
        return qr


def _mock_domain_plugin(keywords):
    """Create a mock domain plugin with given keywords."""
    mock_plugin = MagicMock()
    mock_plugin.get_config.return_value.routing_keywords = keywords
    return mock_plugin


# =============================================================================
# Tests: _get_domain_keywords
# =============================================================================

class TestGetDomainKeywords:
    def test_returns_keywords_from_plugin(self, rewriter):
        plugin = _mock_domain_plugin(["colregs", "solas", "marpol"])
        with patch("app.domains.registry.get_domain_registry") as mock_reg:
            mock_reg.return_value.get.return_value = plugin
            keywords = rewriter._get_domain_keywords()
        assert keywords == ["colregs", "solas", "marpol"]

    def test_returns_empty_when_no_plugin(self, rewriter):
        with patch("app.domains.registry.get_domain_registry") as mock_reg:
            mock_reg.return_value.get.return_value = None
            keywords = rewriter._get_domain_keywords()
        assert keywords == []

    def test_returns_empty_when_registry_fails(self, rewriter):
        with patch("app.domains.registry.get_domain_registry", side_effect=Exception("boom")):
            keywords = rewriter._get_domain_keywords()
        assert keywords == []

    def test_returns_empty_when_keywords_is_none(self, rewriter):
        plugin = _mock_domain_plugin(None)
        with patch("app.domains.registry.get_domain_registry") as mock_reg:
            mock_reg.return_value.get.return_value = plugin
            keywords = rewriter._get_domain_keywords()
        assert keywords == []


# =============================================================================
# Tests: _rule_based_rewrite
# =============================================================================

class TestRuleBasedRewrite:
    def test_prepends_keyword_when_none_in_query(self, rewriter):
        with patch.object(rewriter, "_get_domain_keywords", return_value=["maritime", "colregs"]):
            result = rewriter._rule_based_rewrite("What is Rule 5?")
        assert result == "maritime What is Rule 5?"

    def test_no_change_when_keyword_already_present(self, rewriter):
        with patch.object(rewriter, "_get_domain_keywords", return_value=["colregs", "solas"]):
            result = rewriter._rule_based_rewrite("COLREGs Rule 5 explained")
        assert result == "COLREGs Rule 5 explained"

    def test_case_insensitive_match(self, rewriter):
        with patch.object(rewriter, "_get_domain_keywords", return_value=["COLREGS"]):
            result = rewriter._rule_based_rewrite("colregs rule 5")
        assert result == "colregs rule 5"  # Already has keyword

    def test_no_change_when_no_keywords(self, rewriter):
        with patch.object(rewriter, "_get_domain_keywords", return_value=[]):
            result = rewriter._rule_based_rewrite("What is Rule 5?")
        assert result == "What is Rule 5?"

    def test_uses_first_keyword_for_prepend(self, rewriter):
        with patch.object(rewriter, "_get_domain_keywords", return_value=["maritime", "navigation"]):
            result = rewriter._rule_based_rewrite("some general question")
        assert result.startswith("maritime ")


# =============================================================================
# Tests: _add_domain_keywords
# =============================================================================

class TestAddDomainKeywords:
    def test_appends_keyword_when_not_present(self, rewriter):
        with patch.object(rewriter, "_get_domain_keywords", return_value=["maritime", "vessel"]):
            result = rewriter._add_domain_keywords("What is Rule 5?")
        assert "maritime" in result
        assert result.startswith("What is Rule 5?")

    def test_no_change_when_keyword_present(self, rewriter):
        with patch.object(rewriter, "_get_domain_keywords", return_value=["colregs"]):
            result = rewriter._add_domain_keywords("COLREGs Rule 5")
        assert result == "COLREGs Rule 5"

    def test_adds_only_one_keyword(self, rewriter):
        with patch.object(rewriter, "_get_domain_keywords", return_value=["maritime", "vessel", "navigation"]):
            result = rewriter._add_domain_keywords("something else")
        # Should only add first non-present keyword
        added_count = sum(1 for kw in ["maritime", "vessel", "navigation"] if kw in result.lower())
        assert added_count == 1

    def test_no_change_when_no_keywords(self, rewriter):
        with patch.object(rewriter, "_get_domain_keywords", return_value=[]):
            result = rewriter._add_domain_keywords("What is Rule 5?")
        assert result == "What is Rule 5?"


# =============================================================================
# Tests: Async fallback behavior
# =============================================================================

class TestAsyncFallback:
    @pytest.mark.asyncio
    async def test_rewrite_falls_back_when_no_llm(self, rewriter):
        with patch.object(rewriter, "_get_domain_keywords", return_value=["maritime"]):
            result = await rewriter.rewrite("general question")
        assert "maritime" in result

    @pytest.mark.asyncio
    async def test_expand_falls_back_when_no_llm(self, rewriter):
        with patch.object(rewriter, "_get_domain_keywords", return_value=["maritime"]):
            result = await rewriter.expand("general question")
        assert "maritime" in result

    @pytest.mark.asyncio
    async def test_decompose_returns_original_when_no_llm(self, rewriter):
        result = await rewriter.decompose("complex multi-part question")
        assert result == ["complex multi-part question"]

    def test_is_available_false_without_llm(self, rewriter):
        assert rewriter.is_available() is False


class TestRuntimeSocket:
    @pytest.mark.asyncio
    async def test_rewrite_prefers_runtime_socket_llm(self):
        mock_runtime_llm = AsyncMock()
        mock_runtime_llm.ainvoke.return_value = MagicMock(content="rewritten query")

        with patch(
            "app.engine.multi_agent.openai_stream_runtime."
            "_create_openai_compatible_stream_client_impl",
            return_value=None,
        ), \
             patch("app.engine.agentic_rag.runtime_llm_socket.get_llm_for_provider", return_value=mock_runtime_llm), \
             patch("app.services.output_processor.extract_thinking_from_response", return_value=("rewritten query", None)):
            rewriter = QueryRewriter()
            rewriter._llm = None
            result = await rewriter.rewrite("old query", "documents were weak")

        assert result == "rewritten query"
        mock_runtime_llm.ainvoke.assert_awaited()


# =============================================================================
# Tests: Singleton
# =============================================================================

class TestSingleton:
    def test_get_query_rewriter_returns_instance(self):
        from app.engine.agentic_rag.query_rewriter import get_query_rewriter
        rewriter = get_query_rewriter()
        assert isinstance(rewriter, QueryRewriter)
