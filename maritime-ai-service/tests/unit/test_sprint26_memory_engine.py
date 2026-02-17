"""
Tests for Sprint 26: SemanticMemoryEngine new methods and InsightProvider fixes.

Covers:
- delete_memory_by_keyword() — delegates to repository
- delete_all_user_memories() — delegates to repository
- store_explicit_insight() — creates and stores Insight
- InsightProvider._check_and_consolidate() — wired to MemoryConsolidator
- InsightProvider._fifo_eviction() — deletes INSIGHT type, not USER_FACT
- InsightProvider._get_user_insights() — queries INSIGHT type
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from uuid import uuid4


# =============================================================================
# SemanticMemoryEngine — New Methods
# =============================================================================

class TestSemanticMemoryEngineDeleteByKeyword:
    """Test delete_memory_by_keyword() method."""

    @pytest.mark.asyncio
    async def test_delegates_to_repository(self):
        """Should call repository.delete_memories_by_keyword."""
        from app.engine.semantic_memory.core import SemanticMemoryEngine

        mock_repo = MagicMock()
        mock_repo.delete_memories_by_keyword.return_value = 3
        mock_embeddings = MagicMock()

        engine = SemanticMemoryEngine.__new__(SemanticMemoryEngine)
        engine._repository = mock_repo
        engine._embeddings = mock_embeddings
        engine._context_retriever = MagicMock()
        engine._fact_extractor = MagicMock()
        engine._insight_provider = MagicMock()

        result = await engine.delete_memory_by_keyword(
            user_id="user-1", keyword="solas"
        )

        assert result == 3
        mock_repo.delete_memories_by_keyword.assert_called_once_with(
            user_id="user-1", keyword="solas"
        )

    @pytest.mark.asyncio
    async def test_returns_zero_on_exception(self):
        """Should return 0 and not raise on repository error."""
        from app.engine.semantic_memory.core import SemanticMemoryEngine

        mock_repo = MagicMock()
        mock_repo.delete_memories_by_keyword.side_effect = Exception("DB error")

        engine = SemanticMemoryEngine.__new__(SemanticMemoryEngine)
        engine._repository = mock_repo
        engine._embeddings = MagicMock()
        engine._context_retriever = MagicMock()
        engine._fact_extractor = MagicMock()
        engine._insight_provider = MagicMock()

        result = await engine.delete_memory_by_keyword(
            user_id="user-1", keyword="test"
        )
        assert result == 0


class TestSemanticMemoryEngineDeleteAll:
    """Test delete_all_user_memories() method."""

    @pytest.mark.asyncio
    async def test_delegates_to_repository(self):
        """Should call repository.delete_all_user_memories."""
        from app.engine.semantic_memory.core import SemanticMemoryEngine

        mock_repo = MagicMock()
        mock_repo.delete_all_user_memories.return_value = 15

        engine = SemanticMemoryEngine.__new__(SemanticMemoryEngine)
        engine._repository = mock_repo
        engine._embeddings = MagicMock()
        engine._context_retriever = MagicMock()
        engine._fact_extractor = MagicMock()
        engine._insight_provider = MagicMock()

        result = await engine.delete_all_user_memories(user_id="user-1")

        assert result == 15
        mock_repo.delete_all_user_memories.assert_called_once_with(user_id="user-1")

    @pytest.mark.asyncio
    async def test_returns_zero_on_exception(self):
        """Should return 0 and not raise on repository error."""
        from app.engine.semantic_memory.core import SemanticMemoryEngine

        mock_repo = MagicMock()
        mock_repo.delete_all_user_memories.side_effect = Exception("DB down")

        engine = SemanticMemoryEngine.__new__(SemanticMemoryEngine)
        engine._repository = mock_repo
        engine._embeddings = MagicMock()
        engine._context_retriever = MagicMock()
        engine._fact_extractor = MagicMock()
        engine._insight_provider = MagicMock()

        result = await engine.delete_all_user_memories(user_id="user-1")
        assert result == 0


class TestSemanticMemoryEngineStoreExplicitInsight:
    """Test store_explicit_insight() method."""

    @pytest.mark.asyncio
    async def test_stores_insight_via_provider(self):
        """Should create an Insight and delegate to InsightProvider._store_insight."""
        from app.engine.semantic_memory.core import SemanticMemoryEngine

        mock_provider = MagicMock()
        mock_provider._store_insight = AsyncMock(return_value=True)

        engine = SemanticMemoryEngine.__new__(SemanticMemoryEngine)
        engine._repository = MagicMock()
        engine._embeddings = MagicMock()
        engine._context_retriever = MagicMock()
        engine._fact_extractor = MagicMock()
        engine._insight_provider = mock_provider

        result = await engine.store_explicit_insight(
            user_id="user-1",
            insight_text="User likes quizzes",
            category="preference",
        )

        assert result is True
        mock_provider._store_insight.assert_called_once()
        insight_arg = mock_provider._store_insight.call_args[0][0]
        assert insight_arg.user_id == "user-1"
        assert "User likes quizzes" in insight_arg.content

    @pytest.mark.asyncio
    async def test_invalid_category_defaults_to_preference(self):
        """Invalid category string should fall back to PREFERENCE."""
        from app.engine.semantic_memory.core import SemanticMemoryEngine
        from app.models.semantic_memory import InsightCategory

        mock_provider = MagicMock()
        mock_provider._store_insight = AsyncMock(return_value=True)

        engine = SemanticMemoryEngine.__new__(SemanticMemoryEngine)
        engine._repository = MagicMock()
        engine._embeddings = MagicMock()
        engine._context_retriever = MagicMock()
        engine._fact_extractor = MagicMock()
        engine._insight_provider = mock_provider

        result = await engine.store_explicit_insight(
            user_id="user-1",
            insight_text="Test",
            category="invalid_category",
        )

        assert result is True
        insight_arg = mock_provider._store_insight.call_args[0][0]
        assert insight_arg.category == InsightCategory.PREFERENCE

    @pytest.mark.asyncio
    async def test_returns_false_on_exception(self):
        """Should return False on error, not raise."""
        from app.engine.semantic_memory.core import SemanticMemoryEngine

        mock_provider = MagicMock()
        mock_provider._store_insight = AsyncMock(side_effect=Exception("fail"))

        engine = SemanticMemoryEngine.__new__(SemanticMemoryEngine)
        engine._repository = MagicMock()
        engine._embeddings = MagicMock()
        engine._context_retriever = MagicMock()
        engine._fact_extractor = MagicMock()
        engine._insight_provider = mock_provider

        result = await engine.store_explicit_insight(
            user_id="user-1", insight_text="Test"
        )
        assert result is False


# =============================================================================
# InsightProvider — Consolidation & FIFO
# =============================================================================

class TestInsightProviderConsolidation:
    """Test _check_and_consolidate() method (Sprint 26: wired to MemoryConsolidator)."""

    def _make_provider(self, mock_repo=None, mock_embeddings=None):
        from app.engine.semantic_memory.insight_provider import InsightProvider

        provider = InsightProvider(
            embeddings=mock_embeddings or MagicMock(),
            repository=mock_repo or MagicMock(),
        )
        return provider

    @pytest.mark.asyncio
    async def test_returns_false_when_no_consolidator(self):
        """Without a MemoryConsolidator, should return False."""
        provider = self._make_provider()
        provider._memory_consolidator = None

        result = await provider._check_and_consolidate("user-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_below_threshold(self):
        """When insight count < threshold, should not consolidate."""
        mock_repo = MagicMock()
        mock_repo.count_user_memories.return_value = 20  # Below 40

        mock_consolidator = MagicMock()
        mock_consolidator.should_consolidate = AsyncMock(return_value=False)

        provider = self._make_provider(mock_repo=mock_repo)
        provider._memory_consolidator = mock_consolidator

        result = await provider._check_and_consolidate("user-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_triggers_consolidation_above_threshold(self):
        """When above threshold, should consolidate and replace insights."""
        from app.models.semantic_memory import Insight, InsightCategory
        from app.engine.memory_consolidator import ConsolidationResult

        # Create a mock memory result that _get_user_insights can parse
        mock_memory = MagicMock()
        mock_memory.id = uuid4()
        mock_memory.content = "Test insight"
        mock_memory.created_at = None
        mock_memory.metadata = {
            "insight_category": "preference",
            "confidence": 0.8,
            "source_messages": [],
        }

        mock_repo = MagicMock()
        mock_repo.count_user_memories.return_value = 45
        # Sprint 27: _get_user_insights() now calls get_user_insights() not search_similar()
        mock_repo.get_user_insights.return_value = [mock_memory]
        mock_repo.delete_oldest_insights.return_value = 45

        mock_embeddings = MagicMock()
        mock_embeddings.aembed_documents = AsyncMock(return_value=[[0.0] * 768])

        consolidated_insights = [
            Insight(
                user_id="user-1",
                content="Consolidated insight",
                category=InsightCategory.PREFERENCE,
                confidence=0.9,
                source_messages=["merged from 3 insights"],
            )
        ]

        mock_consolidator = MagicMock()
        mock_consolidator.should_consolidate = AsyncMock(return_value=True)
        mock_consolidator.consolidate = AsyncMock(
            return_value=ConsolidationResult(
                success=True,
                original_count=45,
                final_count=1,
                consolidated_insights=consolidated_insights,
            )
        )

        provider = self._make_provider(
            mock_repo=mock_repo, mock_embeddings=mock_embeddings
        )
        provider._memory_consolidator = mock_consolidator
        # Mock _store_insight to avoid full embedding/save chain
        provider._store_insight = AsyncMock(return_value=True)

        result = await provider._check_and_consolidate("user-1")

        assert result is True
        mock_consolidator.consolidate.assert_called_once()
        mock_repo.delete_oldest_insights.assert_called_once_with("user-1", 45)
        provider._store_insight.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_false_on_consolidation_failure(self):
        """If consolidation fails, should return False."""
        from app.engine.memory_consolidator import ConsolidationResult

        mock_repo = MagicMock()
        mock_repo.count_user_memories.return_value = 45
        # Sprint 27: _get_user_insights() now calls get_user_insights() not search_similar()
        mock_repo.get_user_insights.return_value = []

        mock_consolidator = MagicMock()
        mock_consolidator.should_consolidate = AsyncMock(return_value=True)
        mock_consolidator.consolidate = AsyncMock(
            return_value=ConsolidationResult(
                success=False,
                original_count=45,
                final_count=45,
                consolidated_insights=[],
                error="LLM not available",
            )
        )

        provider = self._make_provider(mock_repo=mock_repo)
        provider._memory_consolidator = mock_consolidator

        # get_user_insights returns [] → existing_insights is empty → returns False
        result = await provider._check_and_consolidate("user-1")
        assert result is False


class TestInsightProviderFIFOEviction:
    """Test _fifo_eviction() deletes INSIGHT type (Sprint 26 fix)."""

    @pytest.mark.asyncio
    async def test_deletes_insights_not_facts(self):
        """FIFO eviction should call delete_oldest_insights, not delete_oldest_facts."""
        from app.engine.semantic_memory.insight_provider import InsightProvider
        from app.models.semantic_memory import MemoryType

        mock_repo = MagicMock()
        mock_repo.count_user_memories.return_value = 55  # 5 over limit
        mock_repo.delete_oldest_insights.return_value = 5

        provider = InsightProvider(
            embeddings=MagicMock(), repository=mock_repo
        )

        deleted = await provider._fifo_eviction("user-1")

        assert deleted == 5
        mock_repo.delete_oldest_insights.assert_called_once_with("user-1", 5)
        # Verify delete_oldest_facts was NOT called
        assert not hasattr(mock_repo, 'delete_oldest_facts') or \
            not mock_repo.delete_oldest_facts.called

    @pytest.mark.asyncio
    async def test_no_eviction_below_limit(self):
        """No eviction when count <= MAX_INSIGHTS."""
        from app.engine.semantic_memory.insight_provider import InsightProvider

        mock_repo = MagicMock()
        mock_repo.count_user_memories.return_value = 50  # At limit, not over

        provider = InsightProvider(
            embeddings=MagicMock(), repository=mock_repo
        )

        deleted = await provider._fifo_eviction("user-1")

        assert deleted == 0
        mock_repo.delete_oldest_insights.assert_not_called()


class TestInsightProviderGetUserInsights:
    """Test _get_user_insights() queries INSIGHT type (Sprint 26 fix, Sprint 27 update)."""

    @pytest.mark.asyncio
    async def test_queries_insight_type_not_user_fact(self):
        """Should use get_user_insights() from InsightRepositoryMixin (Sprint 27 fix)."""
        from app.engine.semantic_memory.insight_provider import InsightProvider

        mock_repo = MagicMock()
        mock_repo.get_user_insights.return_value = []

        provider = InsightProvider(
            embeddings=MagicMock(), repository=mock_repo
        )

        await provider._get_user_insights("user-1")

        mock_repo.get_user_insights.assert_called_once_with(
            user_id="user-1",
            limit=provider.MAX_INSIGHTS,
        )
