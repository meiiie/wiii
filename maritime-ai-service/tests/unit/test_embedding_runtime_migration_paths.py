"""Focused regression tests for embedding-runtime migration paths."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_text_ingestion_uses_shared_embedding_backend():
    """Text ingestion should resolve embeddings from the shared runtime authority."""
    from app.api.v1.knowledge import TextIngestionRequest, ingest_text_document

    chunk = MagicMock()
    chunk.content = "Rule 15 explanation"
    chunk.metadata = {"page_number": 1}
    chunk.content_type = "text"
    chunk.confidence_score = 0.95

    mock_chunker = MagicMock()
    mock_chunker.chunk_page_content = AsyncMock(return_value=[chunk])

    mock_backend = MagicMock()
    mock_backend.aembed_documents = AsyncMock(return_value=[[0.1] * 768])

    mock_dense_repo = MagicMock()
    mock_dense_repo.store_document_chunk = AsyncMock(return_value=True)

    settings_obj = SimpleNamespace(
        enable_text_ingestion=True,
        max_ingestion_size_mb=1,
    )

    with patch("app.core.config.settings", settings_obj), \
         patch("app.services.chunking_service.get_semantic_chunker", return_value=mock_chunker), \
         patch("app.api.v1.knowledge.get_embedding_backend", return_value=mock_backend), \
         patch("app.repositories.dense_search_repository.get_dense_search_repository", return_value=mock_dense_repo):
        response = await ingest_text_document(
            request=MagicMock(),
            auth=MagicMock(),
            body=TextIngestionRequest(
                content="Explain Rule 15 in simple terms.",
                document_id="doc-rule15",
                domain_id="maritime",
                title="Rule 15",
            ),
        )

    assert response.status == "completed"
    mock_backend.aembed_documents.assert_awaited_once()
    mock_dense_repo.store_document_chunk.assert_awaited_once()


def test_lms_enrichment_uses_semantic_embedding_backend():
    """LMS enrichment should construct FactExtractor from the shared semantic backend."""
    import app.integrations.lms.enrichment as mod

    mod._extractor_singleton = None
    mock_backend = MagicMock()
    mock_repo = MagicMock()
    mock_extractor = MagicMock()

    with patch.object(mod, "get_semantic_embedding_backend", return_value=mock_backend), \
         patch("app.engine.semantic_memory.extraction.FactExtractor", return_value=mock_extractor) as mock_fact_cls, \
         patch("app.repositories.semantic_memory_repository.SemanticMemoryRepository", return_value=mock_repo):
        service = mod.LMSEnrichmentService()
        extractor = service._get_extractor()

    assert extractor is mock_extractor
    mock_fact_cls.assert_called_once_with(mock_backend, mock_repo)
    mod._extractor_singleton = None
