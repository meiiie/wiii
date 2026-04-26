"""
Tests for Sprint 27: Zero-vector NaN fix and get_memories_by_type().

Covers:
- InsightProvider._get_user_insights() uses get_user_insights() (not search_similar)
- SemanticMemoryRepository.get_memories_by_type() new method
- core.py count_session_tokens() uses get_memories_by_type()
- core.py _get_session_messages() uses get_memories_by_type()
- Corrective RAG cache confidence threshold fix (>= 70, not >= 0.7)
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime

from app.models.semantic_memory import MemoryType, InsightCategory


# =============================================================================
# InsightProvider._get_user_insights() — Zero-vector NaN fix
# =============================================================================

class TestInsightProviderGetUserInsightsFixed:
    """Sprint 27: _get_user_insights() should use get_user_insights() not search_similar()."""

    @pytest.mark.asyncio
    async def test_uses_get_user_insights_not_search_similar(self):
        """Should call get_user_insights() instead of search_similar() with zero-vector."""
        from app.engine.semantic_memory.insight_provider import InsightProvider

        mock_repo = MagicMock()
        mock_repo.get_user_insights.return_value = []
        mock_repo.search_similar = MagicMock()  # Should NOT be called

        provider = InsightProvider(embeddings=MagicMock(), repository=mock_repo)

        result = await provider._get_user_insights("user-1")

        assert result == []
        mock_repo.get_user_insights.assert_called_once_with(
            user_id="user-1",
            limit=provider.MAX_INSIGHTS,
        )
        mock_repo.search_similar.assert_not_called()

    @pytest.mark.asyncio
    async def test_converts_memories_to_insights(self):
        """Should convert SemanticMemorySearchResult to Insight objects."""
        from app.engine.semantic_memory.insight_provider import InsightProvider

        mock_memory = MagicMock()
        mock_memory.id = uuid4()
        mock_memory.content = "User prefers quizzes"
        mock_memory.created_at = datetime.now()
        mock_memory.metadata = {
            "insight_category": "preference",
            "confidence": 0.8,
            "source_messages": ["I like quizzes"],
        }

        mock_repo = MagicMock()
        mock_repo.get_user_insights.return_value = [mock_memory]

        provider = InsightProvider(embeddings=MagicMock(), repository=mock_repo)

        result = await provider._get_user_insights("user-1")

        assert len(result) == 1
        assert result[0].content == "User prefers quizzes"
        assert result[0].category == InsightCategory.PREFERENCE
        assert result[0].user_id == "user-1"

    @pytest.mark.asyncio
    async def test_skips_invalid_memories(self):
        """Should skip memories without insight_category metadata."""
        from app.engine.semantic_memory.insight_provider import InsightProvider

        mock_memory_valid = MagicMock()
        mock_memory_valid.id = uuid4()
        mock_memory_valid.content = "Valid insight"
        mock_memory_valid.created_at = datetime.now()
        mock_memory_valid.metadata = {
            "insight_category": "preference",
            "confidence": 0.9,
            "source_messages": [],
        }

        mock_memory_invalid = MagicMock()
        mock_memory_invalid.id = uuid4()
        mock_memory_invalid.content = "No category"
        mock_memory_invalid.created_at = datetime.now()
        mock_memory_invalid.metadata = {}  # Missing insight_category

        mock_repo = MagicMock()
        mock_repo.get_user_insights.return_value = [mock_memory_valid, mock_memory_invalid]

        provider = InsightProvider(embeddings=MagicMock(), repository=mock_repo)

        result = await provider._get_user_insights("user-1")

        assert len(result) == 1
        assert result[0].content == "Valid insight"

    @pytest.mark.asyncio
    async def test_returns_empty_on_exception(self):
        """Should return [] on repository error."""
        from app.engine.semantic_memory.insight_provider import InsightProvider

        mock_repo = MagicMock()
        mock_repo.get_user_insights.side_effect = Exception("DB error")

        provider = InsightProvider(embeddings=MagicMock(), repository=mock_repo)

        result = await provider._get_user_insights("user-1")

        assert result == []


# =============================================================================
# SemanticMemoryRepository.get_memories_by_type()
# =============================================================================

class TestGetMemoriesByType:
    """Sprint 27: New method to retrieve memories by type without cosine similarity."""

    def test_method_exists(self):
        """get_memories_by_type should exist on SemanticMemoryRepository."""
        from app.repositories.semantic_memory_repository import SemanticMemoryRepository
        repo = SemanticMemoryRepository.__new__(SemanticMemoryRepository)
        assert hasattr(repo, "get_memories_by_type")
        assert callable(repo.get_memories_by_type)

    def test_queries_by_type_without_cosine(self):
        """Should query by memory_type without cosine distance."""
        from app.repositories.semantic_memory_repository import SemanticMemoryRepository

        mock_row = MagicMock()
        mock_row.id = uuid4()
        mock_row.content = "Test message"
        mock_row.memory_type = MemoryType.MESSAGE.value
        mock_row.importance = 0.5
        mock_row.metadata = {}
        mock_row.created_at = datetime.now()

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        repo = SemanticMemoryRepository.__new__(SemanticMemoryRepository)
        repo._initialized = True
        repo._session_factory = MagicMock(return_value=mock_session)
        repo.TABLE_NAME = "semantic_memories"

        results = repo.get_memories_by_type(
            user_id="user-1",
            memory_type=MemoryType.MESSAGE,
        )

        assert len(results) == 1
        assert results[0].content == "Test message"
        assert results[0].memory_type == MemoryType.MESSAGE

        # Verify SQL was called with correct params
        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert params["user_id"] == "user-1"
        assert params["memory_type"] == MemoryType.MESSAGE.value

    def test_with_session_filter(self):
        """Should filter by session_id when provided."""
        from app.repositories.semantic_memory_repository import SemanticMemoryRepository

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        repo = SemanticMemoryRepository.__new__(SemanticMemoryRepository)
        repo._initialized = True
        repo._session_factory = MagicMock(return_value=mock_session)
        repo.TABLE_NAME = "semantic_memories"

        repo.get_memories_by_type(
            user_id="user-1",
            memory_type=MemoryType.MESSAGE,
            session_id="session-abc",
        )

        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert params["session_id"] == "session-abc"

    def test_returns_empty_on_exception(self):
        """Should return [] on error."""
        from app.repositories.semantic_memory_repository import SemanticMemoryRepository

        repo = SemanticMemoryRepository.__new__(SemanticMemoryRepository)
        repo._initialized = True
        repo._session_factory = MagicMock(side_effect=Exception("DB error"))

        results = repo.get_memories_by_type(
            user_id="user-1",
            memory_type=MemoryType.MESSAGE,
        )

        assert results == []


# =============================================================================
# core.py — Session methods use get_memories_by_type
# =============================================================================

class TestCoreSessionMethodsFixed:
    """Sprint 27: count_session_tokens and _get_session_messages use get_memories_by_type."""

    def _make_engine(self, mock_repo=None):
        from app.engine.semantic_memory.core import SemanticMemoryEngine

        engine = SemanticMemoryEngine.__new__(SemanticMemoryEngine)
        engine._repository = mock_repo or MagicMock()
        engine._embeddings = MagicMock()
        engine._context_retriever = MagicMock()
        engine._fact_extractor = MagicMock()
        engine._insight_provider = MagicMock()
        engine._llm = None
        engine._initialized = False
        return engine

    def test_count_session_tokens_uses_get_memories_by_type(self):
        """count_session_tokens should call get_memories_by_type with session_id."""
        mock_msg = MagicMock()
        mock_msg.content = "Hello world"
        mock_msg.metadata = {}

        mock_repo = MagicMock()
        mock_repo.get_memories_by_type.return_value = [mock_msg]
        mock_repo.search_similar = MagicMock()  # Should NOT be called

        engine = self._make_engine(mock_repo)

        result = engine.count_session_tokens("user-1", "session-abc")

        assert result > 0
        mock_repo.get_memories_by_type.assert_called_once_with(
            user_id="user-1",
            memory_type=MemoryType.MESSAGE,
            session_id="session-abc",
        )
        mock_repo.search_similar.assert_not_called()

    def test_get_session_messages_uses_get_memories_by_type(self):
        """_get_session_messages should use get_memories_by_type with session_id."""
        mock_msg1 = MagicMock()
        mock_msg1.content = "First message"
        mock_msg1.created_at = datetime(2026, 1, 1, 10, 0, 0)

        mock_msg2 = MagicMock()
        mock_msg2.content = "Second message"
        mock_msg2.created_at = datetime(2026, 1, 1, 10, 5, 0)

        mock_repo = MagicMock()
        # get_memories_by_type returns DESC order
        mock_repo.get_memories_by_type.return_value = [mock_msg2, mock_msg1]
        mock_repo.search_similar = MagicMock()  # Should NOT be called

        engine = self._make_engine(mock_repo)

        result = engine._get_session_messages("user-1", "session-abc")

        # Should be sorted ASC (chronological)
        assert len(result) == 2
        assert result[0].content == "First message"
        assert result[1].content == "Second message"

        mock_repo.get_memories_by_type.assert_called_once_with(
            user_id="user-1",
            memory_type=MemoryType.MESSAGE,
            session_id="session-abc",
        )
        mock_repo.search_similar.assert_not_called()

    def test_count_session_tokens_returns_zero_on_error(self):
        """Should return 0 on exception."""
        mock_repo = MagicMock()
        mock_repo.get_memories_by_type.side_effect = Exception("DB error")

        engine = self._make_engine(mock_repo)

        result = engine.count_session_tokens("user-1", "session-abc")
        assert result == 0


# =============================================================================
# Corrective RAG cache confidence threshold fix
# =============================================================================

class TestCorrectedCacheConfidenceThreshold:
    """Sprint 27: Cache threshold uses >= 70 (0-100 scale), not >= 0.7."""

    @pytest.mark.asyncio
    async def test_threshold_is_70_not_0_7(self):
        """Cache storage should use the 0-100 confidence scale."""
        from app.engine.agentic_rag.corrective_rag_runtime_support import (
            store_cache_response_impl,
        )

        cache_manager = MagicMock()
        cache_manager.set = AsyncMock()

        common_kwargs = {
            "cache_enabled": True,
            "cache_manager": cache_manager,
            "query_embedding": [0.1, 0.2],
            "query": "test",
            "answer": "answer",
            "sources": [{"document_id": "doc-1"}],
            "thinking": None,
            "iterations": 1,
            "was_rewritten": False,
            "context": {"user_id": "user-1", "organization_id": "org-1"},
        }

        await store_cache_response_impl(confidence=0.7, **common_kwargs)
        cache_manager.set.assert_not_called()

        await store_cache_response_impl(confidence=70, **common_kwargs)
        cache_manager.set.assert_awaited_once()
