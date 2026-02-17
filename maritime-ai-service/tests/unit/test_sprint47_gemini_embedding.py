"""
Tests for Sprint 47: GeminiOptimizedEmbeddings coverage.

Tests embedding service including:
- Init (defaults, custom, no API key)
- _normalize (L2 normalization, zero vector)
- embed_documents (empty, single, error fallback)
- embed_query
- aembed_documents, aembed_query (async wrappers)
- embed_for_similarity
- verify_dimensions, verify_normalization
- dimensions property
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch, AsyncMock


# ============================================================================
# Initialization
# ============================================================================


class TestGeminiEmbeddingsInit:
    """Test GeminiOptimizedEmbeddings initialization."""

    def test_default_config(self):
        with patch("app.engine.gemini_embedding.settings") as mock_settings:
            mock_settings.google_api_key = "fake-key"
            mock_settings.embedding_dimensions = None
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings
            emb = GeminiOptimizedEmbeddings()
            assert emb._dimensions == 768
            assert emb._model_name == "models/gemini-embedding-001"
            assert emb._client is None  # Lazy init

    def test_custom_config(self):
        with patch("app.engine.gemini_embedding.settings") as mock_settings:
            mock_settings.google_api_key = "fake"
            mock_settings.embedding_dimensions = None
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings
            emb = GeminiOptimizedEmbeddings(
                api_key="custom-key",
                model_name="models/custom",
                dimensions=512
            )
            assert emb._api_key == "custom-key"
            assert emb._model_name == "models/custom"
            assert emb._dimensions == 512

    def test_no_api_key_warning(self):
        with patch("app.engine.gemini_embedding.settings") as mock_settings:
            mock_settings.google_api_key = None
            mock_settings.embedding_dimensions = None
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings
            emb = GeminiOptimizedEmbeddings()
            assert emb._api_key is None


# ============================================================================
# _normalize
# ============================================================================


class TestNormalize:
    """Test L2 normalization."""

    def _make_emb(self):
        with patch("app.engine.gemini_embedding.settings") as mock_settings:
            mock_settings.google_api_key = "fake"
            mock_settings.embedding_dimensions = None
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings
            return GeminiOptimizedEmbeddings()

    def test_unit_vector(self):
        emb = self._make_emb()
        result = emb._normalize([3.0, 4.0])
        # Expected: [0.6, 0.8]
        assert abs(result[0] - 0.6) < 0.001
        assert abs(result[1] - 0.8) < 0.001

    def test_already_normalized(self):
        emb = self._make_emb()
        result = emb._normalize([1.0, 0.0, 0.0])
        assert abs(result[0] - 1.0) < 0.001

    def test_zero_vector(self):
        emb = self._make_emb()
        result = emb._normalize([0.0, 0.0, 0.0])
        # Should return original zero vector
        assert result == [0.0, 0.0, 0.0]

    def test_output_is_unit_length(self):
        emb = self._make_emb()
        result = emb._normalize([1.0, 2.0, 3.0, 4.0, 5.0])
        norm = np.linalg.norm(np.array(result))
        assert abs(norm - 1.0) < 0.0001


# ============================================================================
# embed_documents
# ============================================================================


class TestEmbedDocuments:
    """Test embed_documents."""

    def _make_emb(self):
        with patch("app.engine.gemini_embedding.settings") as mock_settings:
            mock_settings.google_api_key = "fake"
            mock_settings.embedding_dimensions = None
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings
            return GeminiOptimizedEmbeddings()

    def test_empty_texts(self):
        emb = self._make_emb()
        result = emb.embed_documents([])
        assert result == []

    def test_single_document(self):
        emb = self._make_emb()
        mock_embedding = [0.1] * 768
        with patch.object(emb, '_embed_content', return_value=mock_embedding):
            result = emb.embed_documents(["Test document"])
            assert len(result) == 1
            assert len(result[0]) == 768

    def test_multiple_documents(self):
        emb = self._make_emb()
        mock_embedding = [0.1] * 768
        with patch.object(emb, '_embed_content', return_value=mock_embedding):
            result = emb.embed_documents(["Doc 1", "Doc 2", "Doc 3"])
            assert len(result) == 3

    def test_error_fallback_zero_vector(self):
        emb = self._make_emb()
        with patch.object(emb, '_embed_content', side_effect=Exception("API error")):
            result = emb.embed_documents(["Failing doc"])
            assert len(result) == 1
            assert result[0] == [0.0] * 768


# ============================================================================
# embed_query
# ============================================================================


class TestEmbedQuery:
    """Test embed_query."""

    def test_query_uses_retrieval_query_type(self):
        with patch("app.engine.gemini_embedding.settings") as mock_settings:
            mock_settings.google_api_key = "fake"
            mock_settings.embedding_dimensions = None
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings
            emb = GeminiOptimizedEmbeddings()
            mock_embedding = [0.1] * 768
            with patch.object(emb, '_embed_content', return_value=mock_embedding) as mock_embed:
                emb.embed_query("What is Rule 15?")
                mock_embed.assert_called_once_with("What is Rule 15?", "RETRIEVAL_QUERY")


# ============================================================================
# embed_for_similarity
# ============================================================================


class TestEmbedForSimilarity:
    """Test embed_for_similarity."""

    def test_similarity_uses_semantic_type(self):
        with patch("app.engine.gemini_embedding.settings") as mock_settings:
            mock_settings.google_api_key = "fake"
            mock_settings.embedding_dimensions = None
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings
            emb = GeminiOptimizedEmbeddings()
            mock_embedding = [0.1] * 768
            with patch.object(emb, '_embed_content', return_value=mock_embedding) as mock_embed:
                emb.embed_for_similarity("Compare this text")
                mock_embed.assert_called_once_with("Compare this text", "SEMANTIC_SIMILARITY")


# ============================================================================
# async wrappers
# ============================================================================


class TestAsyncWrappers:
    """Test aembed_documents and aembed_query."""

    @pytest.mark.asyncio
    async def test_aembed_documents(self):
        with patch("app.engine.gemini_embedding.settings") as mock_settings:
            mock_settings.google_api_key = "fake"
            mock_settings.embedding_dimensions = None
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings
            emb = GeminiOptimizedEmbeddings()
            mock_embedding = [0.1] * 768
            with patch.object(emb, 'embed_documents', return_value=[mock_embedding]):
                result = await emb.aembed_documents(["Test"])
                assert len(result) == 1

    @pytest.mark.asyncio
    async def test_aembed_query(self):
        with patch("app.engine.gemini_embedding.settings") as mock_settings:
            mock_settings.google_api_key = "fake"
            mock_settings.embedding_dimensions = None
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings
            emb = GeminiOptimizedEmbeddings()
            mock_embedding = [0.1] * 768
            with patch.object(emb, 'embed_query', return_value=mock_embedding):
                result = await emb.aembed_query("Test query")
                assert len(result) == 768


# ============================================================================
# verify_dimensions, verify_normalization, dimensions property
# ============================================================================


class TestVerification:
    """Test verification methods."""

    def _make_emb(self):
        with patch("app.engine.gemini_embedding.settings") as mock_settings:
            mock_settings.google_api_key = "fake"
            mock_settings.embedding_dimensions = None
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings
            return GeminiOptimizedEmbeddings()

    def test_verify_dimensions_correct(self):
        emb = self._make_emb()
        assert emb.verify_dimensions([0.0] * 768) is True

    def test_verify_dimensions_wrong(self):
        emb = self._make_emb()
        assert emb.verify_dimensions([0.0] * 512) is False

    def test_verify_normalization_normalized(self):
        emb = self._make_emb()
        # Unit vector
        v = [0.0] * 768
        v[0] = 1.0
        assert emb.verify_normalization(v) == True  # np.bool_ compatible

    def test_verify_normalization_unnormalized(self):
        emb = self._make_emb()
        assert emb.verify_normalization([2.0] * 768) == False  # np.bool_ compatible

    def test_dimensions_property(self):
        emb = self._make_emb()
        assert emb.dimensions == 768

    def test_task_type_constants(self):
        with patch("app.engine.gemini_embedding.settings") as mock_settings:
            mock_settings.google_api_key = "fake"
            mock_settings.embedding_dimensions = None
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings
            assert GeminiOptimizedEmbeddings.TASK_TYPE_DOCUMENT == "RETRIEVAL_DOCUMENT"
            assert GeminiOptimizedEmbeddings.TASK_TYPE_QUERY == "RETRIEVAL_QUERY"
            assert GeminiOptimizedEmbeddings.TASK_TYPE_SIMILARITY == "SEMANTIC_SIMILARITY"
