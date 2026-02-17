"""
Tests for Sprint 45: CacheInvalidationManager coverage.

Tests cache coherence including:
- DocumentVersion tracking
- Handler registration and invocation
- Content hash comparison (skip unchanged)
- Document update and delete invalidation
- Embedding model version transitions
- Health status reporting
- Error handling in handlers
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================================
# DocumentVersion
# ============================================================================


class TestDocumentVersion:
    """Test DocumentVersion dataclass."""

    def test_basic_creation(self):
        from app.cache.invalidation import DocumentVersion
        dv = DocumentVersion(document_id="doc1", content_hash="abc123")
        assert dv.document_id == "doc1"
        assert dv.content_hash == "abc123"
        assert dv.last_updated > 0
        assert dv.embedding_version is None

    def test_with_embedding_version(self):
        from app.cache.invalidation import DocumentVersion
        dv = DocumentVersion(
            document_id="doc1",
            content_hash="abc123",
            embedding_version="v2"
        )
        assert dv.embedding_version == "v2"


# ============================================================================
# CacheInvalidationManager init
# ============================================================================


class TestInvalidationManagerInit:
    """Test manager initialization."""

    def test_default_init(self):
        from app.cache.invalidation import CacheInvalidationManager
        mgr = CacheInvalidationManager()
        assert mgr._document_versions == {}
        assert mgr._handlers == {}
        assert mgr._invalidation_count == 0
        assert mgr._last_invalidation_time is None
        assert mgr._embedding_model_version is None


# ============================================================================
# Handler registration
# ============================================================================


class TestHandlerRegistration:
    """Test register_handler."""

    def test_register_handler(self):
        from app.cache.invalidation import CacheInvalidationManager
        mgr = CacheInvalidationManager()
        handler = AsyncMock(return_value=0)
        mgr.register_handler("response", handler)
        assert "response" in mgr._handlers

    def test_register_multiple_handlers(self):
        from app.cache.invalidation import CacheInvalidationManager
        mgr = CacheInvalidationManager()
        mgr.register_handler("response", AsyncMock())
        mgr.register_handler("retrieval", AsyncMock())
        assert len(mgr._handlers) == 2


# ============================================================================
# Content hash
# ============================================================================


class TestContentHash:
    """Test _compute_hash."""

    def test_deterministic(self):
        from app.cache.invalidation import CacheInvalidationManager
        mgr = CacheInvalidationManager()
        h1 = mgr._compute_hash("test content")
        h2 = mgr._compute_hash("test content")
        assert h1 == h2

    def test_different_content(self):
        from app.cache.invalidation import CacheInvalidationManager
        mgr = CacheInvalidationManager()
        h1 = mgr._compute_hash("content A")
        h2 = mgr._compute_hash("content B")
        assert h1 != h2

    def test_hash_length(self):
        from app.cache.invalidation import CacheInvalidationManager
        mgr = CacheInvalidationManager()
        h = mgr._compute_hash("any content")
        assert len(h) == 16  # First 16 chars of SHA256


# ============================================================================
# on_document_updated
# ============================================================================


class TestOnDocumentUpdated:
    """Test document update invalidation."""

    @pytest.fixture
    def mgr(self):
        from app.cache.invalidation import CacheInvalidationManager
        return CacheInvalidationManager()

    @pytest.mark.asyncio
    async def test_new_document(self, mgr):
        """First update always triggers invalidation."""
        handler = AsyncMock(return_value=3)
        mgr.register_handler("response", handler)

        results = await mgr.on_document_updated("doc1", "new content")
        assert results["response"] == 3
        handler.assert_called_once_with("doc1")
        assert mgr._invalidation_count == 3

    @pytest.mark.asyncio
    async def test_unchanged_content_skips(self, mgr):
        """Same content hash skips invalidation."""
        handler = AsyncMock(return_value=1)
        mgr.register_handler("response", handler)

        # First update
        await mgr.on_document_updated("doc1", "content")
        handler.reset_mock()

        # Same content again
        results = await mgr.on_document_updated("doc1", "content")
        assert results == {}  # Skipped
        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_changed_content_triggers(self, mgr):
        """Changed content triggers invalidation."""
        handler = AsyncMock(return_value=2)
        mgr.register_handler("response", handler)

        await mgr.on_document_updated("doc1", "old content")
        handler.reset_mock()

        results = await mgr.on_document_updated("doc1", "new content")
        assert results["response"] == 2
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_multi_tier_invalidation(self, mgr):
        """Multiple tiers all get called."""
        h1 = AsyncMock(return_value=2)
        h2 = AsyncMock(return_value=1)
        mgr.register_handler("response", h1)
        mgr.register_handler("retrieval", h2)

        results = await mgr.on_document_updated("doc1", "content")
        assert results["response"] == 2
        assert results["retrieval"] == 1
        assert mgr._invalidation_count == 3

    @pytest.mark.asyncio
    async def test_handler_error(self, mgr):
        """Handler error returns -1 for that tier."""
        handler = AsyncMock(side_effect=Exception("DB error"))
        mgr.register_handler("broken", handler)

        results = await mgr.on_document_updated("doc1", "content")
        assert results["broken"] == -1

    @pytest.mark.asyncio
    async def test_updates_version_tracking(self, mgr):
        """Version tracking updated after invalidation."""
        mgr.register_handler("response", AsyncMock(return_value=0))
        await mgr.on_document_updated("doc1", "content")
        assert "doc1" in mgr._document_versions
        assert mgr._last_invalidation_time is not None


# ============================================================================
# on_document_deleted
# ============================================================================


class TestOnDocumentDeleted:
    """Test document deletion invalidation."""

    @pytest.fixture
    def mgr(self):
        from app.cache.invalidation import CacheInvalidationManager
        return CacheInvalidationManager()

    @pytest.mark.asyncio
    async def test_delete_calls_handlers(self, mgr):
        handler = AsyncMock(return_value=5)
        mgr.register_handler("response", handler)

        results = await mgr.on_document_deleted("doc1")
        assert results["response"] == 5

    @pytest.mark.asyncio
    async def test_delete_removes_version(self, mgr):
        """Deletion removes version tracking entry."""
        mgr.register_handler("response", AsyncMock(return_value=0))
        await mgr.on_document_updated("doc1", "content")
        assert "doc1" in mgr._document_versions

        await mgr.on_document_deleted("doc1")
        assert "doc1" not in mgr._document_versions

    @pytest.mark.asyncio
    async def test_delete_handler_error(self, mgr):
        handler = AsyncMock(side_effect=Exception("error"))
        mgr.register_handler("broken", handler)
        results = await mgr.on_document_deleted("doc1")
        assert results["broken"] == -1


# ============================================================================
# on_embeddings_refreshed
# ============================================================================


class TestOnEmbeddingsRefreshed:
    """Test embedding model version change."""

    @pytest.fixture
    def mgr(self):
        from app.cache.invalidation import CacheInvalidationManager
        return CacheInvalidationManager()

    @pytest.mark.asyncio
    async def test_new_version_clears_cache(self, mgr):
        clear_handler = AsyncMock()
        result = await mgr.on_embeddings_refreshed("v2", clear_handler)
        assert result is True
        clear_handler.assert_called_once()
        assert mgr._embedding_model_version == "v2"

    @pytest.mark.asyncio
    async def test_same_version_skips(self, mgr):
        mgr._embedding_model_version = "v1"
        clear_handler = AsyncMock()
        result = await mgr.on_embeddings_refreshed("v1", clear_handler)
        assert result is False
        clear_handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_handler_still_updates(self, mgr):
        result = await mgr.on_embeddings_refreshed("v2", None)
        assert result is True
        assert mgr._embedding_model_version == "v2"

    @pytest.mark.asyncio
    async def test_handler_error_returns_false(self, mgr):
        clear_handler = AsyncMock(side_effect=Exception("fail"))
        result = await mgr.on_embeddings_refreshed("v2", clear_handler)
        assert result is False


# ============================================================================
# invalidate_all and get_health
# ============================================================================


class TestInvalidateAllAndHealth:
    """Test full invalidation and health reporting."""

    def test_get_health_initial(self):
        from app.cache.invalidation import CacheInvalidationManager
        mgr = CacheInvalidationManager()
        health = mgr.get_health()
        assert health["tracked_documents"] == 0
        assert health["registered_handlers"] == []
        assert health["total_invalidations"] == 0
        assert health["embedding_model_version"] is None

    @pytest.mark.asyncio
    async def test_get_health_after_operations(self):
        from app.cache.invalidation import CacheInvalidationManager
        mgr = CacheInvalidationManager()
        mgr.register_handler("response", AsyncMock(return_value=1))
        await mgr.on_document_updated("doc1", "content")

        health = mgr.get_health()
        assert health["tracked_documents"] == 1
        assert "response" in health["registered_handlers"]
        assert health["total_invalidations"] == 1
        assert health["last_invalidation"] is not None

    @pytest.mark.asyncio
    async def test_invalidate_all_clears_versions(self):
        from app.cache.invalidation import CacheInvalidationManager
        mgr = CacheInvalidationManager()
        mgr._document_versions["doc1"] = MagicMock()
        mgr._document_versions["doc2"] = MagicMock()

        await mgr.invalidate_all()
        assert len(mgr._document_versions) == 0
