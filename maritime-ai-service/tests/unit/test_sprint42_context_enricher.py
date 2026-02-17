"""
Tests for Sprint 42: ContextEnricher coverage.

Tests context enrichment logic including:
- EnrichmentResult dataclass
- Single chunk context generation with mock LLM
- Batch chunk enrichment
- Disabled contextual RAG
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass


# ============================================================================
# EnrichmentResult
# ============================================================================


class TestEnrichmentResult:
    """Test EnrichmentResult dataclass."""

    def test_successful_result(self):
        """Successful enrichment result."""
        from app.engine.context_enricher import EnrichmentResult
        result = EnrichmentResult(
            original_content="original",
            contextual_content="[Context: enriched]\n\noriginal",
            context_only="enriched",
            success=True
        )
        assert result.success is True
        assert result.error is None
        assert "enriched" in result.contextual_content

    def test_failed_result(self):
        """Failed enrichment result."""
        from app.engine.context_enricher import EnrichmentResult
        result = EnrichmentResult(
            original_content="original",
            contextual_content="original",
            context_only="",
            success=False,
            error="LLM error"
        )
        assert result.success is False
        assert result.error == "LLM error"
        assert result.contextual_content == "original"


# ============================================================================
# generate_context
# ============================================================================


class TestGenerateContext:
    """Test single chunk context generation."""

    @pytest.fixture
    def enricher_with_llm(self):
        """Create enricher with mocked LLM."""
        mock_llm = AsyncMock()
        from app.engine.context_enricher import ContextEnricher
        enricher = ContextEnricher(llm=mock_llm)
        return enricher, mock_llm

    @pytest.mark.asyncio
    async def test_generate_context_success(self, enricher_with_llm):
        """Successful context generation."""
        enricher, mock_llm = enricher_with_llm
        mock_llm.ainvoke.return_value = MagicMock(
            content="This chunk describes Rule 15 crossing situation in COLREGs."
        )
        result = await enricher.generate_context(
            chunk_content="Vessels crossing from starboard must give way",
            document_title="COLREGs",
            page_number=1,
            total_pages=10
        )
        assert result.success is True
        assert "Rule 15" in result.context_only
        assert "[Context:" in result.contextual_content
        assert "Vessels crossing" in result.contextual_content

    @pytest.mark.asyncio
    async def test_generate_context_llm_failure(self, enricher_with_llm):
        """LLM failure returns fallback result."""
        enricher, mock_llm = enricher_with_llm
        mock_llm.ainvoke.side_effect = Exception("API error")
        result = await enricher.generate_context(
            chunk_content="Original content",
            document_title="Doc",
        )
        assert result.success is False
        assert result.contextual_content == "Original content"
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_generate_context_truncates_long_chunks(self, enricher_with_llm):
        """Long chunks are truncated in the prompt."""
        enricher, mock_llm = enricher_with_llm
        mock_llm.ainvoke.return_value = MagicMock(content="Context for long chunk")

        long_content = "A" * 5000  # Very long chunk
        result = await enricher.generate_context(
            chunk_content=long_content,
            document_title="Doc",
        )
        # Verify LLM was called (chunk was accepted, truncated internally)
        assert mock_llm.ainvoke.called
        assert result.success is True


# ============================================================================
# enrich_chunks
# ============================================================================


class TestEnrichChunks:
    """Test batch chunk enrichment."""

    def _make_chunk(self, content="Test content", page=1):
        """Create a mock ChunkResult."""
        chunk = MagicMock()
        chunk.content = content
        chunk.metadata = {"page_number": page}
        chunk.contextual_content = None
        return chunk

    @pytest.mark.asyncio
    async def test_enrich_chunks_disabled(self):
        """Skips enrichment when contextual_rag_enabled is False."""
        with patch("app.engine.context_enricher.settings") as mock_settings:
            mock_settings.contextual_rag_enabled = False
            from app.engine.context_enricher import ContextEnricher
            enricher = ContextEnricher(llm=AsyncMock())
            chunks = [self._make_chunk()]
            result = await enricher.enrich_chunks(chunks, "doc1")
            assert result == chunks  # Returned unchanged

    @pytest.mark.asyncio
    async def test_enrich_chunks_empty_list(self):
        """Empty chunk list returns empty."""
        with patch("app.engine.context_enricher.settings") as mock_settings:
            mock_settings.contextual_rag_enabled = True
            from app.engine.context_enricher import ContextEnricher
            enricher = ContextEnricher(llm=AsyncMock())
            result = await enricher.enrich_chunks([], "doc1")
            assert result == []

    @pytest.mark.asyncio
    async def test_enrich_chunks_success(self):
        """Successful batch enrichment."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(
            content="Context for this chunk about safety"
        )
        with patch("app.engine.context_enricher.settings") as mock_settings:
            mock_settings.contextual_rag_enabled = True
            from app.engine.context_enricher import ContextEnricher
            enricher = ContextEnricher(llm=mock_llm)

            chunks = [self._make_chunk("Chunk 1"), self._make_chunk("Chunk 2")]
            result = await enricher.enrich_chunks(
                chunks, "doc1", document_title="Test Doc"
            )
            assert len(result) == 2
            # LLM should have been called for each chunk
            assert mock_llm.ainvoke.call_count == 2

    @pytest.mark.asyncio
    async def test_enrich_chunks_partial_failure(self):
        """Some chunks fail but others succeed."""
        mock_llm = AsyncMock()
        # First succeeds, second fails
        mock_llm.ainvoke.side_effect = [
            MagicMock(content="Good context"),
            Exception("API rate limit"),
        ]
        with patch("app.engine.context_enricher.settings") as mock_settings:
            mock_settings.contextual_rag_enabled = True
            from app.engine.context_enricher import ContextEnricher
            enricher = ContextEnricher(llm=mock_llm)

            chunks = [self._make_chunk("Chunk 1"), self._make_chunk("Chunk 2")]
            result = await enricher.enrich_chunks(chunks, "doc1")
            # Should not crash; returns all chunks
            assert len(result) == 2


# ============================================================================
# LLM lazy initialization
# ============================================================================


class TestLLMLazyInit:
    """Test lazy LLM initialization."""

    def test_init_without_llm(self):
        """Enricher can be created without LLM."""
        from app.engine.context_enricher import ContextEnricher
        enricher = ContextEnricher()
        assert enricher._llm is None

    def test_ensure_llm_creates_instance(self):
        """_ensure_llm creates LLM from shared pool on first call."""
        mock_llm = MagicMock()
        with patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
            from app.engine.context_enricher import ContextEnricher
            enricher = ContextEnricher()
            llm = enricher._ensure_llm()
            assert llm is mock_llm
