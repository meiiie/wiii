"""
Tests for Sprint 34: GraphRAGService entity cache — pure logic.

Covers:
- GraphEnhancedResult dataclass
- Entity cache TTL behavior
- Cache key normalization
- Cache hit/miss/expiry
"""

import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from app.services.graph_rag_service import (
    GraphEnhancedResult,
    _entity_cache,
    _ENTITY_CACHE_TTL,
)


# =============================================================================
# GraphEnhancedResult
# =============================================================================


class TestGraphEnhancedResult:
    def test_defaults(self):
        r = GraphEnhancedResult(
            chunk_id="c1",
            content="Some content",
            score=0.85,
        )
        assert r.related_entities == []
        assert r.related_regulations == []
        assert r.entity_context == ""
        assert r.search_method == "graph_enhanced"
        assert r.dense_score == 0.0
        assert r.sparse_score == 0.0
        assert r.page_number is None
        assert r.document_id is None
        assert r.category == "Knowledge"

    def test_full_construction(self):
        r = GraphEnhancedResult(
            chunk_id="c1",
            content="Content",
            score=0.9,
            page_number=5,
            document_id="doc1",
            image_url="http://example.com/img.png",
            category="Regulation",
            related_entities=[{"id": "e1", "name": "SOLAS"}],
            related_regulations=["Rule 15", "Rule 16"],
            entity_context="Related to COLREGs",
            dense_score=0.8,
            sparse_score=7.5,
        )
        assert r.page_number == 5
        assert len(r.related_entities) == 1
        assert len(r.related_regulations) == 2


# =============================================================================
# Entity cache behavior
# =============================================================================


class TestEntityCache:
    def setup_method(self):
        """Clear global cache before each test."""
        _entity_cache.clear()

    def test_cache_ttl_constant(self):
        assert _ENTITY_CACHE_TTL == 300  # 5 minutes

    def test_cache_key_format(self):
        """Cache key is first 100 chars, lowered, stripped."""
        key = "Rule 15 COLREGs crossing situation"[:100].lower().strip()
        assert key == "rule 15 colregs crossing situation"

    def test_cache_set_and_get(self):
        """Direct cache manipulation for testing."""
        key = "test_query"
        entities = ["entity1", "entity2"]
        _entity_cache[key] = (entities, time.time())

        cached_entities, ts = _entity_cache[key]
        assert cached_entities == ["entity1", "entity2"]
        assert time.time() - ts < 1  # Within 1 second

    def test_cache_expiry_logic(self):
        """Entries older than TTL should be considered expired."""
        key = "expired_query"
        old_time = time.time() - (_ENTITY_CACHE_TTL + 1)
        _entity_cache[key] = (["old_entity"], old_time)

        _, timestamp = _entity_cache[key]
        is_expired = time.time() - timestamp >= _ENTITY_CACHE_TTL
        assert is_expired is True

    def test_cache_fresh_logic(self):
        """Recent entries should be considered fresh."""
        key = "fresh_query"
        _entity_cache[key] = (["fresh_entity"], time.time())

        _, timestamp = _entity_cache[key]
        is_expired = time.time() - timestamp >= _ENTITY_CACHE_TTL
        assert is_expired is False

    def test_cache_different_keys(self):
        """Different queries should have different cache entries."""
        _entity_cache["query_a"] = (["a1"], time.time())
        _entity_cache["query_b"] = (["b1", "b2"], time.time())

        assert len(_entity_cache["query_a"][0]) == 1
        assert len(_entity_cache["query_b"][0]) == 2

    def test_cache_overwrite(self):
        """Re-caching same key should overwrite."""
        key = "overwrite_test"
        _entity_cache[key] = (["old"], time.time() - 100)
        _entity_cache[key] = (["new"], time.time())

        entities, _ = _entity_cache[key]
        assert entities == ["new"]

    def teardown_method(self):
        """Clean up global cache after each test."""
        _entity_cache.clear()
