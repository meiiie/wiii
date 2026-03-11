"""
Tests for GeminiOptimizedEmbeddings coverage.
"""

from unittest.mock import patch

import numpy as np
import pytest

from app.engine.model_catalog import DEFAULT_EMBEDDING_MODEL, get_embedding_dimensions


DEFAULT_DIMENSIONS = get_embedding_dimensions(DEFAULT_EMBEDDING_MODEL)


def _patched_settings(api_key="fake", dimensions=None, model=DEFAULT_EMBEDDING_MODEL):
    return patch(
        "app.engine.gemini_embedding.settings",
        **{
            "google_api_key": api_key,
            "embedding_dimensions": dimensions,
            "embedding_model": model,
        },
    )


class TestGeminiEmbeddingsInit:
    """Test GeminiOptimizedEmbeddings initialization."""

    def test_default_config(self):
        with _patched_settings(api_key="fake-key", dimensions=None):
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings

            embeddings = GeminiOptimizedEmbeddings()
            assert embeddings._dimensions == DEFAULT_DIMENSIONS
            assert embeddings._model_name == DEFAULT_EMBEDDING_MODEL
            assert embeddings._client is None

    def test_custom_config(self):
        with _patched_settings(api_key="fake", dimensions=None):
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings

            embeddings = GeminiOptimizedEmbeddings(
                api_key="custom-key",
                model_name="models/custom",
                dimensions=512,
            )
            assert embeddings._api_key == "custom-key"
            assert embeddings._model_name == "models/custom"
            assert embeddings._dimensions == 512

    def test_non_default_model_uses_catalog_dimensions(self):
        with _patched_settings(api_key="fake", dimensions=DEFAULT_DIMENSIONS):
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings

            embeddings = GeminiOptimizedEmbeddings(model_name="gemini-embedding-2-preview")
            assert embeddings._dimensions == get_embedding_dimensions("gemini-embedding-2-preview")

    def test_no_api_key_warning(self):
        with _patched_settings(api_key=None, dimensions=None):
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings

            embeddings = GeminiOptimizedEmbeddings()
            assert embeddings._api_key is None


class TestNormalize:
    """Test L2 normalization."""

    def _make_embeddings(self):
        with _patched_settings(api_key="fake", dimensions=None):
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings

            return GeminiOptimizedEmbeddings()

    def test_unit_vector(self):
        embeddings = self._make_embeddings()
        result = embeddings._normalize([3.0, 4.0])
        assert abs(result[0] - 0.6) < 0.001
        assert abs(result[1] - 0.8) < 0.001

    def test_already_normalized(self):
        embeddings = self._make_embeddings()
        result = embeddings._normalize([1.0, 0.0, 0.0])
        assert abs(result[0] - 1.0) < 0.001

    def test_zero_vector(self):
        embeddings = self._make_embeddings()
        result = embeddings._normalize([0.0, 0.0, 0.0])
        assert result == [0.0, 0.0, 0.0]

    def test_output_is_unit_length(self):
        embeddings = self._make_embeddings()
        result = embeddings._normalize([1.0, 2.0, 3.0, 4.0, 5.0])
        norm = np.linalg.norm(np.array(result))
        assert abs(norm - 1.0) < 0.0001


class TestEmbedDocuments:
    """Test embed_documents."""

    def _make_embeddings(self):
        with _patched_settings(api_key="fake", dimensions=None):
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings

            return GeminiOptimizedEmbeddings()

    def test_empty_texts(self):
        embeddings = self._make_embeddings()
        assert embeddings.embed_documents([]) == []

    def test_single_document(self):
        embeddings = self._make_embeddings()
        mock_embedding = [0.1] * DEFAULT_DIMENSIONS
        with patch.object(embeddings, "_embed_content", return_value=mock_embedding):
            result = embeddings.embed_documents(["Test document"])
            assert len(result) == 1
            assert len(result[0]) == DEFAULT_DIMENSIONS

    def test_multiple_documents(self):
        embeddings = self._make_embeddings()
        mock_embedding = [0.1] * DEFAULT_DIMENSIONS
        with patch.object(embeddings, "_embed_content", return_value=mock_embedding):
            result = embeddings.embed_documents(["Doc 1", "Doc 2", "Doc 3"])
            assert len(result) == 3

    def test_error_fallback_zero_vector(self):
        embeddings = self._make_embeddings()
        with patch.object(embeddings, "_embed_content", side_effect=Exception("API error")):
            result = embeddings.embed_documents(["Failing doc"])
            assert len(result) == 1
            assert result[0] == [0.0] * DEFAULT_DIMENSIONS


class TestEmbedQuery:
    """Test embed_query."""

    def test_query_uses_retrieval_query_type(self):
        with _patched_settings(api_key="fake", dimensions=None):
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings

            embeddings = GeminiOptimizedEmbeddings()
            mock_embedding = [0.1] * DEFAULT_DIMENSIONS
            with patch.object(embeddings, "_embed_content", return_value=mock_embedding) as mock_embed:
                embeddings.embed_query("What is Rule 15?")
                mock_embed.assert_called_once_with("What is Rule 15?", "RETRIEVAL_QUERY")


class TestEmbedForSimilarity:
    """Test embed_for_similarity."""

    def test_similarity_uses_semantic_type(self):
        with _patched_settings(api_key="fake", dimensions=None):
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings

            embeddings = GeminiOptimizedEmbeddings()
            mock_embedding = [0.1] * DEFAULT_DIMENSIONS
            with patch.object(embeddings, "_embed_content", return_value=mock_embedding) as mock_embed:
                embeddings.embed_for_similarity("Compare this text")
                mock_embed.assert_called_once_with("Compare this text", "SEMANTIC_SIMILARITY")


class TestAsyncWrappers:
    """Test aembed_documents and aembed_query."""

    @pytest.mark.asyncio
    async def test_aembed_documents(self):
        with _patched_settings(api_key="fake", dimensions=None):
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings

            embeddings = GeminiOptimizedEmbeddings()
            mock_embedding = [0.1] * DEFAULT_DIMENSIONS
            with patch.object(embeddings, "embed_documents", return_value=[mock_embedding]):
                result = await embeddings.aembed_documents(["Test"])
                assert len(result) == 1

    @pytest.mark.asyncio
    async def test_aembed_query(self):
        with _patched_settings(api_key="fake", dimensions=None):
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings

            embeddings = GeminiOptimizedEmbeddings()
            mock_embedding = [0.1] * DEFAULT_DIMENSIONS
            with patch.object(embeddings, "embed_query", return_value=mock_embedding):
                result = await embeddings.aembed_query("Test query")
                assert len(result) == DEFAULT_DIMENSIONS


class TestVerification:
    """Test verification methods."""

    def _make_embeddings(self):
        with _patched_settings(api_key="fake", dimensions=None):
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings

            return GeminiOptimizedEmbeddings()

    def test_verify_dimensions_correct(self):
        embeddings = self._make_embeddings()
        assert embeddings.verify_dimensions([0.0] * DEFAULT_DIMENSIONS) is True

    def test_verify_dimensions_wrong(self):
        embeddings = self._make_embeddings()
        assert embeddings.verify_dimensions([0.0] * 512) is False

    def test_verify_normalization_normalized(self):
        embeddings = self._make_embeddings()
        vector = [0.0] * DEFAULT_DIMENSIONS
        vector[0] = 1.0
        assert embeddings.verify_normalization(vector) == True

    def test_verify_normalization_unnormalized(self):
        embeddings = self._make_embeddings()
        assert embeddings.verify_normalization([2.0] * DEFAULT_DIMENSIONS) == False

    def test_dimensions_property(self):
        embeddings = self._make_embeddings()
        assert embeddings.dimensions == DEFAULT_DIMENSIONS

    def test_task_type_constants(self):
        with _patched_settings(api_key="fake", dimensions=None):
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings

            assert GeminiOptimizedEmbeddings.TASK_TYPE_DOCUMENT == "RETRIEVAL_DOCUMENT"
            assert GeminiOptimizedEmbeddings.TASK_TYPE_QUERY == "RETRIEVAL_QUERY"
            assert GeminiOptimizedEmbeddings.TASK_TYPE_SIMILARITY == "SEMANTIC_SIMILARITY"
