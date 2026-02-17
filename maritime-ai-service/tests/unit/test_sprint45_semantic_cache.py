"""
Tests for Sprint 45: SemanticResponseCache coverage.

Tests L1 semantic response cache including:
- Cache get/set with cosine similarity matching
- TTL expiration
- LRU eviction
- Document invalidation
- Cache stats and metrics
- Disabled cache behavior
"""

import time
import pytest
import numpy as np
from unittest.mock import patch

from app.cache.models import CacheConfig, CacheEntry, CacheLookupResult, CacheStats, CacheTier


# ============================================================================
# Cache models (CacheEntry, CacheStats, CacheLookupResult)
# ============================================================================


class TestCacheEntry:
    """Test CacheEntry dataclass."""

    def test_default_entry(self):
        entry = CacheEntry(
            key="query", embedding=[1.0, 0.0], value="answer",
            tier=CacheTier.RESPONSE
        )
        assert entry.access_count == 0
        assert entry.document_ids == []
        assert not entry.is_expired()

    def test_expired_entry(self):
        import time
        entry = CacheEntry(
            key="q", embedding=[1.0], value="a",
            tier=CacheTier.RESPONSE, ttl=0
        )
        # TTL=0 means immediately expired — small sleep ensures time delta > 0
        time.sleep(0.01)
        assert entry.is_expired()

    def test_touch_updates_access(self):
        entry = CacheEntry(
            key="q", embedding=[1.0], value="a",
            tier=CacheTier.RESPONSE
        )
        old_access = entry.last_accessed
        entry.touch()
        assert entry.access_count == 1
        assert entry.last_accessed >= old_access

    def test_age_seconds(self):
        entry = CacheEntry(
            key="q", embedding=[1.0], value="a",
            tier=CacheTier.RESPONSE
        )
        assert entry.age_seconds >= 0
        assert entry.age_seconds < 1  # Just created

    def test_remaining_ttl(self):
        entry = CacheEntry(
            key="q", embedding=[1.0], value="a",
            tier=CacheTier.RESPONSE, ttl=3600
        )
        assert entry.remaining_ttl > 3599
        assert entry.remaining_ttl <= 3600


class TestCacheStats:
    """Test CacheStats."""

    def test_hit_rate_zero(self):
        stats = CacheStats(tier=CacheTier.RESPONSE)
        assert stats.hit_rate == 0.0

    def test_hit_rate_calculation(self):
        stats = CacheStats(tier=CacheTier.RESPONSE, hits=3, misses=7)
        assert abs(stats.hit_rate - 0.3) < 0.01

    def test_to_dict(self):
        stats = CacheStats(tier=CacheTier.RESPONSE, hits=5, misses=5)
        d = stats.to_dict()
        assert d["tier"] == "response"
        assert d["hit_rate"] == "50.00%"


class TestCacheLookupResult:
    """Test CacheLookupResult."""

    def test_miss_result(self):
        result = CacheLookupResult(hit=False, tier=CacheTier.RESPONSE)
        assert result.value is None

    def test_hit_result(self):
        entry = CacheEntry(
            key="q", embedding=[1.0], value="cached answer",
            tier=CacheTier.RESPONSE
        )
        result = CacheLookupResult(hit=True, entry=entry, similarity=0.99)
        assert result.value == "cached answer"


# ============================================================================
# SemanticResponseCache initialization
# ============================================================================


class TestSemanticCacheInit:
    """Test cache initialization."""

    def test_default_config(self):
        from app.cache.semantic_cache import SemanticResponseCache
        cache = SemanticResponseCache()
        assert cache._config.enabled is True
        assert cache._config.similarity_threshold == 0.92

    def test_custom_config(self):
        from app.cache.semantic_cache import SemanticResponseCache
        config = CacheConfig(similarity_threshold=0.90, max_response_entries=100)
        cache = SemanticResponseCache(config=config)
        assert cache._config.similarity_threshold == 0.90
        assert cache._config.max_response_entries == 100

    def test_empty_stats(self):
        from app.cache.semantic_cache import SemanticResponseCache
        cache = SemanticResponseCache()
        stats = cache.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.total_entries == 0


# ============================================================================
# Cosine similarity
# ============================================================================


class TestCosineSimilarity:
    """Test _cosine_similarity."""

    @pytest.fixture
    def cache(self):
        from app.cache.semantic_cache import SemanticResponseCache
        return SemanticResponseCache()

    def test_identical_vectors(self, cache):
        a = np.array([1.0, 2.0, 3.0])
        assert abs(cache._cosine_similarity(a, a) - 1.0) < 0.001

    def test_orthogonal_vectors(self, cache):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert abs(cache._cosine_similarity(a, b)) < 0.001

    def test_zero_vector(self, cache):
        a = np.array([0.0, 0.0])
        b = np.array([1.0, 2.0])
        assert cache._cosine_similarity(a, b) == 0.0


# ============================================================================
# Cache get (miss, hit, expiration)
# ============================================================================


class TestCacheGet:
    """Test cache.get() lookup."""

    @pytest.fixture
    def cache(self):
        from app.cache.semantic_cache import SemanticResponseCache
        config = CacheConfig(similarity_threshold=0.95, log_cache_operations=False)
        return SemanticResponseCache(config=config)

    @pytest.mark.asyncio
    async def test_get_empty_cache_miss(self, cache):
        result = await cache.get("query", [1.0, 0.0, 0.0])
        assert result.hit is False
        assert cache.get_stats().misses == 1

    @pytest.mark.asyncio
    async def test_get_after_set_hit(self, cache):
        embedding = [1.0, 0.0, 0.0]
        await cache.set("test query", embedding, "cached answer")

        result = await cache.get("test query", embedding)
        assert result.hit is True
        assert result.value == "cached answer"
        assert result.similarity >= 0.95
        assert cache.get_stats().hits == 1

    @pytest.mark.asyncio
    async def test_get_similar_query_hit(self, cache):
        """Semantically similar query should hit."""
        emb1 = [1.0, 0.0, 0.0]
        emb2 = [0.99, 0.01, 0.0]  # Very similar
        await cache.set("original query", emb1, "answer")

        result = await cache.get("similar query", emb2)
        assert result.hit is True

    @pytest.mark.asyncio
    async def test_get_dissimilar_query_miss(self, cache):
        """Dissimilar query should miss."""
        emb1 = [1.0, 0.0, 0.0]
        emb2 = [0.0, 1.0, 0.0]  # Orthogonal
        await cache.set("original query", emb1, "answer")

        result = await cache.get("different query", emb2)
        assert result.hit is False

    @pytest.mark.asyncio
    async def test_get_expired_entry_evicted(self, cache):
        """Expired entries are evicted during get."""
        # Create entry with 0 TTL
        entry = CacheEntry(
            key="expired query",
            embedding=[1.0, 0.0, 0.0],
            value="old answer",
            tier=CacheTier.RESPONSE,
            ttl=0,
            created_at=time.time() - 10  # Created 10s ago
        )
        cache._cache["expired query"] = entry

        result = await cache.get("expired query", [1.0, 0.0, 0.0])
        assert result.hit is False
        assert "expired query" not in cache._cache

    @pytest.mark.asyncio
    async def test_get_disabled_cache(self):
        from app.cache.semantic_cache import SemanticResponseCache
        config = CacheConfig(enabled=False)
        cache = SemanticResponseCache(config=config)
        result = await cache.get("query", [1.0])
        assert result.hit is False


# ============================================================================
# Cache set (basic, LRU eviction)
# ============================================================================


class TestCacheSet:
    """Test cache.set() storage."""

    @pytest.fixture
    def cache(self):
        from app.cache.semantic_cache import SemanticResponseCache
        config = CacheConfig(max_response_entries=3, log_cache_operations=False)
        return SemanticResponseCache(config=config)

    @pytest.mark.asyncio
    async def test_set_basic(self, cache):
        await cache.set("query1", [1.0], "answer1")
        assert len(cache._cache) == 1
        assert cache.get_stats().total_entries == 1

    @pytest.mark.asyncio
    async def test_set_with_document_ids(self, cache):
        await cache.set("query1", [1.0], "answer1", document_ids=["d1", "d2"])
        entry = cache._cache["query1"]
        assert entry.document_ids == ["d1", "d2"]

    @pytest.mark.asyncio
    async def test_set_with_metadata(self, cache):
        await cache.set("query1", [1.0], "answer1", metadata={"source": "test"})
        entry = cache._cache["query1"]
        assert entry.metadata["source"] == "test"

    @pytest.mark.asyncio
    async def test_lru_eviction(self, cache):
        """Oldest entry evicted when at capacity (max=3)."""
        await cache.set("q1", [1.0], "a1")
        await cache.set("q2", [2.0], "a2")
        await cache.set("q3", [3.0], "a3")
        # Cache full with 3 entries
        assert len(cache._cache) == 3

        # Adding 4th evicts oldest (q1)
        await cache.set("q4", [4.0], "a4")
        assert len(cache._cache) == 3
        assert "q1" not in cache._cache
        assert "q4" in cache._cache
        assert cache.get_stats().evictions >= 1

    @pytest.mark.asyncio
    async def test_set_disabled(self):
        from app.cache.semantic_cache import SemanticResponseCache
        config = CacheConfig(enabled=False)
        cache = SemanticResponseCache(config=config)
        await cache.set("query", [1.0], "answer")
        assert len(cache._cache) == 0


# ============================================================================
# Document invalidation
# ============================================================================


class TestDocumentInvalidation:
    """Test invalidate_by_document."""

    @pytest.fixture
    def cache(self):
        from app.cache.semantic_cache import SemanticResponseCache
        config = CacheConfig(log_cache_operations=False)
        return SemanticResponseCache(config=config)

    @pytest.mark.asyncio
    async def test_invalidate_matching_doc(self, cache):
        await cache.set("q1", [1.0], "a1", document_ids=["doc1", "doc2"])
        await cache.set("q2", [2.0], "a2", document_ids=["doc3"])

        count = await cache.invalidate_by_document("doc1")
        assert count == 1
        assert "q1" not in cache._cache
        assert "q2" in cache._cache

    @pytest.mark.asyncio
    async def test_invalidate_no_match(self, cache):
        await cache.set("q1", [1.0], "a1", document_ids=["doc1"])
        count = await cache.invalidate_by_document("nonexistent")
        assert count == 0
        assert len(cache._cache) == 1

    @pytest.mark.asyncio
    async def test_invalidate_multiple(self, cache):
        await cache.set("q1", [1.0], "a1", document_ids=["docX"])
        await cache.set("q2", [2.0], "a2", document_ids=["docX"])
        await cache.set("q3", [3.0], "a3", document_ids=["docY"])

        count = await cache.invalidate_by_document("docX")
        assert count == 2
        assert len(cache._cache) == 1


# ============================================================================
# Cache clear
# ============================================================================


class TestCacheClear:
    """Test cache.clear()."""

    @pytest.mark.asyncio
    async def test_clear_all(self):
        from app.cache.semantic_cache import SemanticResponseCache
        config = CacheConfig(log_cache_operations=False)
        cache = SemanticResponseCache(config=config)

        await cache.set("q1", [1.0], "a1")
        await cache.set("q2", [2.0], "a2")
        count = await cache.clear()
        assert count == 2
        assert len(cache._cache) == 0
        assert cache.get_stats().total_entries == 0

    @pytest.mark.asyncio
    async def test_clear_empty(self):
        from app.cache.semantic_cache import SemanticResponseCache
        cache = SemanticResponseCache()
        count = await cache.clear()
        assert count == 0


# ============================================================================
# Stats and EMA similarity tracking
# ============================================================================


class TestStatsTracking:
    """Test statistics tracking."""

    @pytest.mark.asyncio
    async def test_hit_miss_tracking(self):
        from app.cache.semantic_cache import SemanticResponseCache
        config = CacheConfig(log_cache_operations=False)
        cache = SemanticResponseCache(config=config)

        emb = [1.0, 0.0, 0.0]
        await cache.set("q1", emb, "a1")

        # Hit
        await cache.get("q1", emb)
        # Miss
        await cache.get("q2", [0.0, 1.0, 0.0])

        stats = cache.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.hit_rate == 0.5

    def test_ema_similarity_first_hit(self):
        from app.cache.semantic_cache import SemanticResponseCache
        cache = SemanticResponseCache()
        cache._stats.hits = 1
        cache._update_avg_similarity(0.98)
        assert cache._stats.avg_similarity_on_hit == 0.98

    def test_ema_similarity_subsequent(self):
        from app.cache.semantic_cache import SemanticResponseCache
        cache = SemanticResponseCache()
        cache._stats.hits = 2
        cache._stats.avg_similarity_on_hit = 0.95
        cache._update_avg_similarity(0.99)
        # EMA: 0.1 * 0.99 + 0.9 * 0.95 = 0.099 + 0.855 = 0.954
        assert abs(cache._stats.avg_similarity_on_hit - 0.954) < 0.001
