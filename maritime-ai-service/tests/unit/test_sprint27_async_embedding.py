"""
Tests for Sprint 27: Async embedding methods (blocking I/O fix).

Covers:
- GeminiOptimizedEmbeddings.aembed_documents() uses asyncio.to_thread
- GeminiOptimizedEmbeddings.aembed_query() uses asyncio.to_thread
- InsightProvider._store_insight() uses aembed_documents (not sync)
- InsightProvider._update_insight_with_evolution() uses aembed_documents
- SemanticMemoryEngine.store_interaction() uses aembed_documents
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime


# =============================================================================
# GeminiOptimizedEmbeddings — Async Methods
# =============================================================================

class TestAsyncEmbeddingMethods:
    """Sprint 27: Verify async wrappers exist and use asyncio.to_thread."""

    def test_aembed_documents_exists(self):
        """aembed_documents should be an async method."""
        from app.engine.gemini_embedding import GeminiOptimizedEmbeddings
        import inspect

        emb = GeminiOptimizedEmbeddings.__new__(GeminiOptimizedEmbeddings)
        assert hasattr(emb, "aembed_documents")
        assert inspect.iscoroutinefunction(emb.aembed_documents)

    def test_aembed_query_exists(self):
        """aembed_query should be an async method."""
        from app.engine.gemini_embedding import GeminiOptimizedEmbeddings
        import inspect

        emb = GeminiOptimizedEmbeddings.__new__(GeminiOptimizedEmbeddings)
        assert hasattr(emb, "aembed_query")
        assert inspect.iscoroutinefunction(emb.aembed_query)

    @pytest.mark.asyncio
    async def test_aembed_documents_delegates_to_sync(self):
        """aembed_documents should call embed_documents via asyncio.to_thread."""
        from app.engine.gemini_embedding import GeminiOptimizedEmbeddings

        emb = GeminiOptimizedEmbeddings.__new__(GeminiOptimizedEmbeddings)
        emb._api_key = "test"
        emb._model_name = "test"
        emb._dimensions = 768

        expected = [[0.1] * 768]
        emb.embed_documents = MagicMock(return_value=expected)

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = expected
            result = await emb.aembed_documents(["test text"])

        mock_thread.assert_called_once_with(emb.embed_documents, ["test text"])
        assert result == expected

    @pytest.mark.asyncio
    async def test_aembed_query_delegates_to_sync(self):
        """aembed_query should call embed_query via asyncio.to_thread."""
        from app.engine.gemini_embedding import GeminiOptimizedEmbeddings

        emb = GeminiOptimizedEmbeddings.__new__(GeminiOptimizedEmbeddings)
        emb._api_key = "test"
        emb._model_name = "test"
        emb._dimensions = 768

        expected = [0.1] * 768
        emb.embed_query = MagicMock(return_value=expected)

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = expected
            result = await emb.aembed_query("test query")

        mock_thread.assert_called_once_with(emb.embed_query, "test query")
        assert result == expected


# =============================================================================
# InsightProvider — Uses async embeddings
# =============================================================================

class TestInsightProviderAsyncEmbeddings:
    """Sprint 27: InsightProvider methods should use aembed_documents."""

    @pytest.mark.asyncio
    async def test_store_insight_uses_async_embedding(self):
        """_store_insight should call aembed_documents, not embed_documents."""
        from app.engine.semantic_memory.insight_provider import InsightProvider
        from app.models.semantic_memory import Insight, InsightCategory

        mock_embeddings = MagicMock()
        mock_embeddings.aembed_documents = AsyncMock(return_value=[[0.1] * 768])
        mock_embeddings.embed_documents = MagicMock()  # Should NOT be called

        mock_repo = MagicMock()

        provider = InsightProvider(embeddings=mock_embeddings, repository=mock_repo)

        insight = Insight(
            user_id="user-1",
            content="Test insight",
            category=InsightCategory.PREFERENCE,
            confidence=0.8,
            source_messages=["test"],
        )

        await provider._store_insight(insight)

        mock_embeddings.aembed_documents.assert_called_once_with(["Test insight"])
        mock_embeddings.embed_documents.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_insight_uses_async_embedding(self):
        """_update_insight_with_evolution should call aembed_documents."""
        from app.engine.semantic_memory.insight_provider import InsightProvider
        from app.models.semantic_memory import Insight, InsightCategory
        from uuid import uuid4

        mock_embeddings = MagicMock()
        mock_embeddings.aembed_documents = AsyncMock(return_value=[[0.2] * 768])
        mock_embeddings.embed_documents = MagicMock()  # Should NOT be called

        mock_repo = MagicMock()
        mock_repo.update_fact.return_value = True

        provider = InsightProvider(embeddings=mock_embeddings, repository=mock_repo)

        new_insight = Insight(
            user_id="user-1",
            content="Updated view",
            category=InsightCategory.PREFERENCE,
            confidence=0.9,
            source_messages=["update"],
        )

        existing_insight = Insight(
            id=uuid4(),
            user_id="user-1",
            content="Old view",
            category=InsightCategory.PREFERENCE,
            confidence=0.7,
            source_messages=["old"],
        )

        await provider._update_insight_with_evolution(new_insight, existing_insight)

        mock_embeddings.aembed_documents.assert_called_once_with(["Updated view"])
        mock_embeddings.embed_documents.assert_not_called()


# =============================================================================
# SemanticMemoryEngine.store_interaction — Uses async embeddings
# =============================================================================

class TestStoreInteractionAsyncEmbeddings:
    """Sprint 27: store_interaction should use aembed_documents."""

    @pytest.mark.asyncio
    async def test_store_interaction_uses_async_embedding(self):
        """store_interaction should call aembed_documents, not embed_documents."""
        from app.engine.semantic_memory.core import SemanticMemoryEngine

        mock_embeddings = MagicMock()
        mock_embeddings.aembed_documents = AsyncMock(return_value=[[0.1] * 768])
        mock_embeddings.embed_documents = MagicMock()  # Should NOT be called

        mock_repo = MagicMock()
        mock_repo.save_memory.return_value = MagicMock()

        engine = SemanticMemoryEngine.__new__(SemanticMemoryEngine)
        engine._embeddings = mock_embeddings
        engine._repository = mock_repo
        engine._context_retriever = MagicMock()
        engine._fact_extractor = MagicMock()
        engine._fact_extractor.extract_and_store_facts = AsyncMock(return_value=[])
        engine._insight_provider = MagicMock()

        result = await engine.store_interaction(
            user_id="user-1",
            message="Hello",
            response="Hi there!",
            extract_facts=False,
        )

        assert result is True
        # Should call aembed_documents twice (message + response)
        assert mock_embeddings.aembed_documents.call_count == 2
        mock_embeddings.embed_documents.assert_not_called()
