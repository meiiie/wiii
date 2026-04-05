"""Regression tests for provider-agnostic embeddings in CRAG and HyDE paths."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_query_embedding_impl_uses_shared_backend():
    """CRAG query embeddings should come from the shared embedding authority."""
    from app.engine.agentic_rag.corrective_rag_runtime_support import (
        get_query_embedding_impl,
    )

    backend = MagicMock()
    backend.provider = "openai"
    backend.model_name = "text-embedding-3-small"
    backend.aembed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])

    with patch(
        "app.engine.embedding_runtime.get_embedding_backend",
        return_value=backend,
    ):
        result = await get_query_embedding_impl("rule 15")

    assert result == [0.1, 0.2, 0.3]
    backend.aembed_query.assert_awaited_once_with("rule 15")


@pytest.mark.asyncio
async def test_get_document_embedding_impl_uses_shared_backend():
    """HyDE document embeddings should reuse the shared embedding authority."""
    from app.engine.agentic_rag.corrective_rag_runtime_support import (
        get_document_embedding_impl,
    )

    backend = MagicMock()
    backend.provider = "openai"
    backend.model_name = "text-embedding-3-small"
    backend.aembed_documents = AsyncMock(return_value=[[0.4, 0.5, 0.6]])

    with patch(
        "app.engine.embedding_runtime.get_embedding_backend",
        return_value=backend,
    ):
        result = await get_document_embedding_impl("hypothetical doc")

    assert result == [0.4, 0.5, 0.6]
    backend.aembed_documents.assert_awaited_once_with(["hypothetical doc"])


@pytest.mark.asyncio
async def test_store_cache_response_impl_skips_when_embedding_unavailable():
    """CRAG should not write semantic cache entries when no query vector is available."""
    from app.engine.agentic_rag.corrective_rag_runtime_support import (
        store_cache_response_impl,
    )

    cache_manager = MagicMock()
    cache_manager.set = AsyncMock()

    with patch(
        "app.engine.agentic_rag.corrective_rag_runtime_support.get_query_embedding_impl",
        AsyncMock(return_value=None),
    ):
        await store_cache_response_impl(
            cache_enabled=True,
            cache_manager=cache_manager,
            confidence=95,
            query_embedding=None,
            query="Rule 15 la gi?",
            answer="Rule 15 noi ve tinh huong cat huong.",
            sources=[{"document_id": "doc-1"}],
            thinking="dang truy xuat tri nho",
            iterations=1,
            was_rewritten=False,
            context={"user_id": "u1", "organization_id": "org-1"},
        )

    cache_manager.set.assert_not_called()
