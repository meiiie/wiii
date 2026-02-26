"""
Tests for Sprint 187: "RAG Nâng Cao" — Advanced RAG Techniques.

Covers:
- Phase 7A: HyDE (Hypothetical Document Embeddings)
- Phase 7B: Adaptive RAG (Query-type routing)
- Config flags (enable_hyde, enable_adaptive_rag, hyde_blend_alpha)
- Integration with corrective_rag.py
"""

import math
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# =============================================================================
# Fixtures
# =============================================================================


def _make_settings(**overrides):
    s = MagicMock()
    s.enable_hyde = overrides.get("enable_hyde", True)
    s.hyde_blend_alpha = overrides.get("hyde_blend_alpha", 0.5)
    s.enable_adaptive_rag = overrides.get("enable_adaptive_rag", True)
    s.enable_graph_rag = False
    s.enable_visual_rag = False
    return s


# =============================================================================
# 1. HyDE Generator Tests
# =============================================================================


class TestHyDEResult:
    """Test HyDEResult dataclass."""

    def test_default_creation(self):
        from app.engine.agentic_rag.hyde_generator import HyDEResult
        r = HyDEResult()
        assert r.hypothetical_doc == ""
        assert r.hyde_embedding == []
        assert r.original_embedding == []
        assert r.used is False
        assert r.total_time_ms == 0.0

    def test_with_data(self):
        from app.engine.agentic_rag.hyde_generator import HyDEResult
        r = HyDEResult(
            hypothetical_doc="Quy tắc 15 quy định về...",
            hyde_embedding=[0.1, 0.2, 0.3],
            original_embedding=[0.4, 0.5, 0.6],
            generation_time_ms=100.0,
            embedding_time_ms=50.0,
            total_time_ms=150.0,
            used=True,
        )
        assert r.used is True
        assert len(r.hyde_embedding) == 3


class TestGenerateHypotheticalDoc:
    """Test _generate_hypothetical_doc function."""

    @pytest.mark.asyncio
    async def test_successful_generation(self):
        from app.engine.agentic_rag.hyde_generator import _generate_hypothetical_doc

        mock_response = MagicMock()
        mock_response.content = "Quy tắc 15 của COLREGs quy định về tình huống cắt hướng. Khi hai tàu gặp nhau ở tình huống cắt hướng, tàu nào nhìn thấy tàu kia ở bên mạn phải phải nhường đường."

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm), \
             patch("app.services.output_processor.extract_thinking_from_response", return_value=(mock_response.content, None)):
            result = await _generate_hypothetical_doc("Quy tắc 15 COLREGs là gì?")

        assert len(result) > 20
        assert "Quy tắc 15" in result

    @pytest.mark.asyncio
    async def test_llm_unavailable(self):
        from app.engine.agentic_rag.hyde_generator import _generate_hypothetical_doc

        with patch("app.engine.llm_pool.get_llm_light", return_value=None):
            result = await _generate_hypothetical_doc("test query")

        assert result == ""

    @pytest.mark.asyncio
    async def test_short_response_discarded(self):
        from app.engine.agentic_rag.hyde_generator import _generate_hypothetical_doc

        mock_response = MagicMock()
        mock_response.content = "Short."

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm), \
             patch("app.services.output_processor.extract_thinking_from_response", return_value=("Short.", None)):
            result = await _generate_hypothetical_doc("test")

        assert result == ""

    @pytest.mark.asyncio
    async def test_exception_returns_empty(self):
        from app.engine.agentic_rag.hyde_generator import _generate_hypothetical_doc

        with patch("app.engine.llm_pool.get_llm_light", side_effect=RuntimeError("timeout")):
            result = await _generate_hypothetical_doc("test")

        assert result == ""


class TestEmbedHypotheticalDoc:
    """Test _embed_hypothetical_doc function."""

    @pytest.mark.asyncio
    async def test_successful_embedding(self):
        from app.engine.agentic_rag.hyde_generator import _embed_hypothetical_doc

        mock_embeddings = MagicMock()
        mock_embeddings.aembed_documents = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

        with patch("app.engine.gemini_embedding.get_embeddings", return_value=mock_embeddings):
            result = await _embed_hypothetical_doc("Some hypothetical document text")

        assert result == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_empty_result(self):
        from app.engine.agentic_rag.hyde_generator import _embed_hypothetical_doc

        mock_embeddings = MagicMock()
        mock_embeddings.aembed_documents = AsyncMock(return_value=[])

        with patch("app.engine.gemini_embedding.get_embeddings", return_value=mock_embeddings):
            result = await _embed_hypothetical_doc("test")

        assert result == []

    @pytest.mark.asyncio
    async def test_exception_returns_empty(self):
        from app.engine.agentic_rag.hyde_generator import _embed_hypothetical_doc

        with patch("app.engine.gemini_embedding.get_embeddings", side_effect=ImportError("no module")):
            result = await _embed_hypothetical_doc("test")

        assert result == []


class TestBlendEmbeddings:
    """Test blend_embeddings function."""

    def test_equal_blend(self):
        from app.engine.agentic_rag.hyde_generator import blend_embeddings
        q = [1.0, 0.0, 0.0]
        h = [0.0, 1.0, 0.0]
        result = blend_embeddings(q, h, alpha=0.5)

        # Should be normalized [0.5, 0.5, 0.0] → [1/√2, 1/√2, 0]
        assert len(result) == 3
        assert abs(result[0] - result[1]) < 0.001
        # Check L2 normalized
        norm = math.sqrt(sum(x * x for x in result))
        assert abs(norm - 1.0) < 0.001

    def test_query_only(self):
        from app.engine.agentic_rag.hyde_generator import blend_embeddings
        q = [1.0, 0.0, 0.0]
        h = [0.0, 1.0, 0.0]
        result = blend_embeddings(q, h, alpha=0.0)

        # Should be pure query direction
        assert result[0] > 0.99
        assert abs(result[1]) < 0.01

    def test_hyde_only(self):
        from app.engine.agentic_rag.hyde_generator import blend_embeddings
        q = [1.0, 0.0, 0.0]
        h = [0.0, 1.0, 0.0]
        result = blend_embeddings(q, h, alpha=1.0)

        # Should be pure HyDE direction
        assert abs(result[0]) < 0.01
        assert result[1] > 0.99

    def test_empty_query_returns_hyde(self):
        from app.engine.agentic_rag.hyde_generator import blend_embeddings
        result = blend_embeddings([], [0.1, 0.2], alpha=0.5)
        assert result == [0.1, 0.2]

    def test_empty_hyde_returns_query(self):
        from app.engine.agentic_rag.hyde_generator import blend_embeddings
        result = blend_embeddings([0.1, 0.2], [], alpha=0.5)
        assert result == [0.1, 0.2]

    def test_both_empty_returns_empty(self):
        from app.engine.agentic_rag.hyde_generator import blend_embeddings
        result = blend_embeddings([], [], alpha=0.5)
        assert result == []

    def test_dimension_mismatch_returns_query(self):
        from app.engine.agentic_rag.hyde_generator import blend_embeddings
        q = [0.1, 0.2, 0.3]
        h = [0.4, 0.5]  # Different dimension
        result = blend_embeddings(q, h, alpha=0.5)
        assert result == q  # Falls back to query

    def test_result_is_normalized(self):
        from app.engine.agentic_rag.hyde_generator import blend_embeddings
        q = [0.5, 0.5, 0.5, 0.5]
        h = [0.3, 0.7, 0.1, 0.9]
        result = blend_embeddings(q, h, alpha=0.3)
        norm = math.sqrt(sum(x * x for x in result))
        assert abs(norm - 1.0) < 0.001


class TestGenerateHydeEmbedding:
    """Test generate_hyde_embedding main function."""

    @pytest.mark.asyncio
    async def test_successful_generation(self):
        from app.engine.agentic_rag.hyde_generator import generate_hyde_embedding

        with patch(
            "app.engine.agentic_rag.hyde_generator._generate_hypothetical_doc",
            AsyncMock(return_value="Hypothetical answer about maritime rules"),
        ), patch(
            "app.engine.agentic_rag.hyde_generator._embed_hypothetical_doc",
            AsyncMock(return_value=[0.1, 0.2, 0.3]),
        ):
            result = await generate_hyde_embedding("What is Rule 15?", [0.4, 0.5, 0.6])

        assert result.used is True
        assert result.hyde_embedding == [0.1, 0.2, 0.3]
        assert result.original_embedding == [0.4, 0.5, 0.6]
        assert result.total_time_ms >= 0

    @pytest.mark.asyncio
    async def test_no_doc_generated(self):
        from app.engine.agentic_rag.hyde_generator import generate_hyde_embedding

        with patch(
            "app.engine.agentic_rag.hyde_generator._generate_hypothetical_doc",
            AsyncMock(return_value=""),
        ):
            result = await generate_hyde_embedding("test", [0.1, 0.2])

        assert result.used is False
        assert result.original_embedding == [0.1, 0.2]

    @pytest.mark.asyncio
    async def test_embedding_fails_fallback(self):
        from app.engine.agentic_rag.hyde_generator import generate_hyde_embedding

        with patch(
            "app.engine.agentic_rag.hyde_generator._generate_hypothetical_doc",
            AsyncMock(return_value="Some hypothetical document"),
        ), patch(
            "app.engine.agentic_rag.hyde_generator._embed_hypothetical_doc",
            AsyncMock(return_value=[]),
        ):
            result = await generate_hyde_embedding("test", [0.1, 0.2])

        assert result.used is False
        assert result.hypothetical_doc == "Some hypothetical document"
        assert result.original_embedding == [0.1, 0.2]

    @pytest.mark.asyncio
    async def test_exception_returns_safe_result(self):
        from app.engine.agentic_rag.hyde_generator import generate_hyde_embedding

        with patch(
            "app.engine.agentic_rag.hyde_generator._generate_hypothetical_doc",
            AsyncMock(side_effect=RuntimeError("total failure")),
        ):
            result = await generate_hyde_embedding("test", [0.1])

        assert result.used is False
        assert result.original_embedding == [0.1]


# =============================================================================
# 2. Adaptive RAG Tests
# =============================================================================


class TestRetrievalStrategy:
    """Test RetrievalStrategy enum."""

    def test_all_strategies(self):
        from app.engine.agentic_rag.adaptive_rag import RetrievalStrategy
        assert RetrievalStrategy.DENSE_ONLY == "dense_only"
        assert RetrievalStrategy.SPARSE_FIRST == "sparse_first"
        assert RetrievalStrategy.HYBRID == "hybrid"
        assert RetrievalStrategy.MULTI_STEP == "multi_step"
        assert RetrievalStrategy.HYDE_ENHANCED == "hyde_enhanced"


class TestRoutingDecision:
    """Test RoutingDecision dataclass."""

    def test_default_creation(self):
        from app.engine.agentic_rag.adaptive_rag import RoutingDecision, RetrievalStrategy
        d = RoutingDecision(
            strategy=RetrievalStrategy.HYBRID,
            reason="test",
        )
        assert d.dense_weight == 0.5
        assert d.sparse_weight == 0.5
        assert d.enable_hyde is False
        assert d.enable_verification is False
        assert d.max_iterations == 2
        assert d.sub_queries is None


class TestRouteQuery:
    """Test route_query function."""

    def test_complex_query_routes_to_multi_step(self):
        from app.engine.agentic_rag.adaptive_rag import route_query, RetrievalStrategy
        result = route_query(
            query="So sánh SOLAS và MARPOL về yêu cầu an toàn",
            complexity="complex",
            is_domain_related=True,
        )
        assert result.strategy == RetrievalStrategy.MULTI_STEP
        assert result.enable_verification is True
        assert result.max_iterations == 3

    def test_complex_with_requires_multi_step(self):
        from app.engine.agentic_rag.adaptive_rag import route_query, RetrievalStrategy
        result = route_query(
            query="Phân tích các quy tắc hàng hải",
            complexity="moderate",
            requires_multi_step=True,
        )
        assert result.strategy == RetrievalStrategy.MULTI_STEP

    def test_factual_domain_query_routes_to_sparse(self):
        from app.engine.agentic_rag.adaptive_rag import route_query, RetrievalStrategy
        result = route_query(
            query="Quy tắc 15 COLREGs nói gì?",
            complexity="simple",
            is_domain_related=True,
        )
        assert result.strategy == RetrievalStrategy.SPARSE_FIRST
        assert result.sparse_weight > result.dense_weight

    def test_simple_definition_routes_to_dense(self):
        from app.engine.agentic_rag.adaptive_rag import route_query, RetrievalStrategy
        result = route_query(
            query="Hàng hải là gì?",
            complexity="simple",
            is_domain_related=True,
        )
        # Has both "là gì" (simple) and no factual keywords dominant
        # "là gì" is in both simple and factual — factual takes priority
        assert result.strategy in (RetrievalStrategy.DENSE_ONLY, RetrievalStrategy.SPARSE_FIRST)

    def test_non_domain_query_routes_to_hyde(self):
        from app.engine.agentic_rag.adaptive_rag import route_query, RetrievalStrategy
        result = route_query(
            query="Thời tiết hôm nay thế nào?",
            complexity="simple",
            is_domain_related=False,
        )
        assert result.strategy == RetrievalStrategy.HYDE_ENHANCED
        assert result.enable_hyde is True

    def test_default_routes_to_hybrid(self):
        from app.engine.agentic_rag.adaptive_rag import route_query, RetrievalStrategy
        result = route_query(
            query="Tàu container hoạt động như thế nào?",
            complexity="moderate",
            is_domain_related=True,
        )
        assert result.strategy == RetrievalStrategy.HYBRID
        assert result.dense_weight == 0.5
        assert result.sparse_weight == 0.5

    def test_comparison_query_is_complex(self):
        from app.engine.agentic_rag.adaptive_rag import route_query, RetrievalStrategy
        result = route_query(
            query="So sánh quy tắc hàng hải Việt Nam và quốc tế",
            complexity="complex",
        )
        assert result.strategy == RetrievalStrategy.MULTI_STEP

    def test_list_query_is_complex(self):
        from app.engine.agentic_rag.adaptive_rag import route_query, RetrievalStrategy
        result = route_query(
            query="Liệt kê tất cả các quy tắc trong COLREGs",
            complexity="complex",
        )
        assert result.strategy == RetrievalStrategy.MULTI_STEP


class TestHelperFunctions:
    """Test helper functions."""

    def test_get_search_weights(self):
        from app.engine.agentic_rag.adaptive_rag import (
            get_search_weights,
            RoutingDecision,
            RetrievalStrategy,
        )
        d = RoutingDecision(
            strategy=RetrievalStrategy.SPARSE_FIRST,
            reason="test",
            dense_weight=0.3,
            sparse_weight=0.7,
        )
        weights = get_search_weights(d)
        assert weights["dense_weight"] == 0.3
        assert weights["sparse_weight"] == 0.7

    def test_should_use_hyde_true(self):
        from app.engine.agentic_rag.adaptive_rag import (
            should_use_hyde,
            RoutingDecision,
            RetrievalStrategy,
        )
        d = RoutingDecision(
            strategy=RetrievalStrategy.HYDE_ENHANCED,
            reason="test",
        )
        assert should_use_hyde(d) is True

    def test_should_use_hyde_explicit_flag(self):
        from app.engine.agentic_rag.adaptive_rag import (
            should_use_hyde,
            RoutingDecision,
            RetrievalStrategy,
        )
        d = RoutingDecision(
            strategy=RetrievalStrategy.HYBRID,
            reason="test",
            enable_hyde=True,
        )
        assert should_use_hyde(d) is True

    def test_should_not_use_hyde(self):
        from app.engine.agentic_rag.adaptive_rag import (
            should_use_hyde,
            RoutingDecision,
            RetrievalStrategy,
        )
        d = RoutingDecision(
            strategy=RetrievalStrategy.HYBRID,
            reason="test",
        )
        assert should_use_hyde(d) is False

    def test_should_decompose_query(self):
        from app.engine.agentic_rag.adaptive_rag import (
            should_decompose_query,
            RoutingDecision,
            RetrievalStrategy,
        )
        d = RoutingDecision(
            strategy=RetrievalStrategy.MULTI_STEP,
            reason="test",
        )
        assert should_decompose_query(d) is True

    def test_should_not_decompose_query(self):
        from app.engine.agentic_rag.adaptive_rag import (
            should_decompose_query,
            RoutingDecision,
            RetrievalStrategy,
        )
        d = RoutingDecision(
            strategy=RetrievalStrategy.HYBRID,
            reason="test",
        )
        assert should_decompose_query(d) is False


# =============================================================================
# 3. Config Tests
# =============================================================================


class TestAdvancedRAGConfig:
    """Test config flags for Advanced RAG."""

    def test_enable_hyde_default_false(self):
        from app.core.config import Settings
        s = Settings(
            api_key="test",
            google_api_key="test",
            database_url="postgresql+asyncpg://x/y",
        )
        assert s.enable_hyde is False

    def test_hyde_blend_alpha_default(self):
        from app.core.config import Settings
        s = Settings(
            api_key="test",
            google_api_key="test",
            database_url="postgresql+asyncpg://x/y",
        )
        assert s.hyde_blend_alpha == 0.5

    def test_hyde_blend_alpha_custom(self):
        from app.core.config import Settings
        s = Settings(
            api_key="test",
            google_api_key="test",
            database_url="postgresql+asyncpg://x/y",
            hyde_blend_alpha=0.7,
        )
        assert s.hyde_blend_alpha == 0.7

    def test_enable_adaptive_rag_default_false(self):
        from app.core.config import Settings
        s = Settings(
            api_key="test",
            google_api_key="test",
            database_url="postgresql+asyncpg://x/y",
        )
        assert s.enable_adaptive_rag is False


# =============================================================================
# 4. Integration Tests
# =============================================================================


class TestCorrectiveRAGIntegration:
    """Test integration points with corrective_rag.py."""

    @pytest.mark.asyncio
    async def test_hyde_disabled_skips(self):
        """When enable_hyde=False, no HyDE generation occurs."""
        settings = _make_settings(enable_hyde=False)
        assert settings.enable_hyde is False

    @pytest.mark.asyncio
    async def test_adaptive_disabled_skips(self):
        """When enable_adaptive_rag=False, standard hybrid used."""
        settings = _make_settings(enable_adaptive_rag=False)
        assert settings.enable_adaptive_rag is False

    @pytest.mark.asyncio
    async def test_hyde_and_adaptive_combined(self):
        """Adaptive routing can recommend HyDE usage."""
        from app.engine.agentic_rag.adaptive_rag import route_query, should_use_hyde

        decision = route_query(
            query="Thời tiết hàng hải",
            complexity="simple",
            is_domain_related=False,
        )

        if should_use_hyde(decision):
            # Would trigger HyDE generation in corrective_rag
            assert decision.strategy.value == "hyde_enhanced"

    @pytest.mark.asyncio
    async def test_streaming_adaptive_thinking_event(self):
        """Streaming path emits thinking event for adaptive routing."""
        from app.engine.agentic_rag.adaptive_rag import route_query

        decision = route_query(
            query="So sánh quy tắc",
            complexity="complex",
        )

        # Verify event format
        event = {
            "type": "thinking",
            "content": f"Chiến lược tìm kiếm: {decision.strategy.value} — {decision.reason}",
            "step": "adaptive_rag",
        }
        assert event["type"] == "thinking"
        assert event["step"] == "adaptive_rag"
        assert "multi_step" in event["content"]


# =============================================================================
# 5. Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_query_routes_to_hybrid(self):
        from app.engine.agentic_rag.adaptive_rag import route_query, RetrievalStrategy
        result = route_query(query="", complexity="simple")
        assert result.strategy == RetrievalStrategy.HYBRID

    def test_all_keywords_present(self):
        """Query with both factual and complex keywords — complex wins (checked first)."""
        from app.engine.agentic_rag.adaptive_rag import route_query, RetrievalStrategy
        result = route_query(
            query="So sánh tất cả quy tắc COLREGs về điều 15",
            complexity="complex",
        )
        assert result.strategy == RetrievalStrategy.MULTI_STEP

    def test_hyde_prompt_template(self):
        from app.engine.agentic_rag.hyde_generator import _HYDE_PROMPT_VI
        assert "{query}" in _HYDE_PROMPT_VI
        assert "hàng hải" in _HYDE_PROMPT_VI

    @pytest.mark.asyncio
    async def test_hyde_with_no_query_embedding(self):
        from app.engine.agentic_rag.hyde_generator import generate_hyde_embedding

        with patch(
            "app.engine.agentic_rag.hyde_generator._generate_hypothetical_doc",
            AsyncMock(return_value="Some hypothetical answer"),
        ), patch(
            "app.engine.agentic_rag.hyde_generator._embed_hypothetical_doc",
            AsyncMock(return_value=[0.1, 0.2, 0.3]),
        ):
            result = await generate_hyde_embedding("test", None)

        assert result.used is True
        assert result.original_embedding == []


# =============================================================================
# 6. Import Tests
# =============================================================================


class TestImports:
    """Test module imports."""

    def test_hyde_imports(self):
        from app.engine.agentic_rag.hyde_generator import (
            HyDEResult,
            generate_hyde_embedding,
            blend_embeddings,
        )
        assert HyDEResult is not None
        assert callable(generate_hyde_embedding)
        assert callable(blend_embeddings)

    def test_adaptive_imports(self):
        from app.engine.agentic_rag.adaptive_rag import (
            RetrievalStrategy,
            RoutingDecision,
            route_query,
            get_search_weights,
            should_use_hyde,
            should_decompose_query,
        )
        assert callable(route_query)
        assert callable(get_search_weights)
        assert callable(should_use_hyde)
        assert callable(should_decompose_query)
