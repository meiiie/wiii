"""
Semantic Response Cache - SOTA RAG Latency Optimization.

L1 Cache: Stores full RAG responses with semantic matching.

Features:
- Cosine similarity matching (threshold configurable)
- TTL-based expiration
- LRU eviction when full
- Metrics collection

References:
- HuggingFace Semantic Cache
- AllThingsOpen 2024 - 65x latency reduction

Feature: semantic-cache
"""

import asyncio
import logging
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.cache.models import (
    CacheConfig,
    CacheEntry,
    CacheLookupResult,
    CacheStats,
    CacheTier,
)

logger = logging.getLogger(__name__)


class SemanticResponseCache:
    """
    SOTA 2025: Semantic response caching for RAG.
    
    Instead of exact query matching, uses embedding similarity
    to serve cached responses for semantically similar queries.
    
    Usage:
        cache = SemanticResponseCache()
        
        # Check cache first
        result = await cache.get(query, query_embedding)
        if result.hit:
            return result.value
        
        # Generate response...
        response = await generate_response(query)
        
        # Store in cache
        await cache.set(query, query_embedding, response)
    
    **Feature: semantic-cache**
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        """
        Initialize semantic response cache.
        
        Args:
            config: Optional cache configuration
        """
        self._config = config or CacheConfig()
        
        # Use OrderedDict for LRU eviction
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        
        # Statistics
        self._stats = CacheStats(tier=CacheTier.RESPONSE)
        
        # Lock for async-safe access to OrderedDict
        self._lock = asyncio.Lock()
        
        logger.info(
            "SemanticResponseCache initialized: "
            "threshold=%s, "
            "ttl=%ds, "
            "max_entries=%d",
            self._config.similarity_threshold,
            self._config.response_ttl,
            self._config.max_response_entries,
        )
    
    async def get(
        self,
        query: str,
        query_embedding: List[float],
        user_id: str = "",
        org_id: str = "",
    ) -> CacheLookupResult:
        """
        Find semantically similar cached response.

        Args:
            query: Original query text
            query_embedding: Query embedding vector (768-dim)
            user_id: User ID for isolation — only match entries from same user
            org_id: Organization ID for multi-tenant isolation (Sprint 160)

        Returns:
            CacheLookupResult with hit status and cached value if found
        """
        if not self._config.enabled:
            return CacheLookupResult(hit=False, tier=CacheTier.RESPONSE)

        start_time = time.time()
        best_match: Optional[Tuple[CacheEntry, float]] = None

        # Convert query embedding to numpy for fast computation
        query_vec = np.array(query_embedding)

        async with self._lock:
            # Search for similar entries
            adaptive = self._config.adaptive_ttl
            max_mult = self._config.adaptive_ttl_max_multiplier
            for key, entry in list(self._cache.items()):
                # Skip expired entries (adaptive TTL extends hot entries)
                if entry.is_expired(adaptive_ttl=adaptive, max_multiplier=max_mult):
                    self._cache.pop(key, None)
                    self._stats.evictions += 1
                    continue

                # Sprint 121 RC-6: Skip entries from different users
                if user_id and entry.user_id and entry.user_id != user_id:
                    continue

                # Sprint 160: Skip entries from different organizations
                if org_id and getattr(entry, 'org_id', '') and entry.org_id != org_id:
                    continue

                # Calculate cosine similarity
                similarity = self._cosine_similarity(query_vec, np.array(entry.embedding))

                if similarity >= self._config.similarity_threshold:
                    if best_match is None or similarity > best_match[1]:
                        best_match = (entry, similarity)

            if best_match:
                entry, similarity = best_match
                entry.touch()  # Update access time

                # Move to end for LRU
                self._cache.move_to_end(entry.key)

                self._stats.hits += 1
                self._update_avg_similarity(similarity)

        lookup_time = (time.time() - start_time) * 1000

        if best_match:
            entry, similarity = best_match

            if self._config.log_cache_operations:
                logger.info(
                    "[CACHE] HIT query='%s...' "
                    "similarity=%.3f "
                    "age=%.0fs",
                    query[:50], similarity, entry.age_seconds,
                )

            return CacheLookupResult(
                hit=True,
                entry=entry,
                similarity=similarity,
                tier=CacheTier.RESPONSE,
                lookup_time_ms=lookup_time
            )

        self._stats.misses += 1

        if self._config.log_cache_operations:
            logger.debug("[CACHE] MISS query='%s...'", query[:50])

        return CacheLookupResult(
            hit=False,
            tier=CacheTier.RESPONSE,
            lookup_time_ms=lookup_time
        )
    
    async def set(
        self,
        query: str,
        embedding: List[float],
        response: Any,
        document_ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: str = "",
        org_id: str = "",
    ) -> None:
        """
        Store response with semantic key.

        Args:
            query: Original query text
            embedding: Query embedding vector
            response: Full response to cache
            document_ids: List of document IDs used (for invalidation)
            metadata: Additional metadata
            user_id: User ID for isolation — cached entries are user-scoped
            org_id: Organization ID for multi-tenant isolation (Sprint 160)
        """
        if not self._config.enabled:
            return

        # Sprint 121 RC-6 + Sprint 160: Use org_id:user_id-prefixed key for isolation
        prefix = f"{org_id}:" if org_id else ""
        prefix += f"{user_id}::" if user_id else ""
        cache_key = f"{prefix}{query}"

        async with self._lock:
            # Evict if at capacity
            while len(self._cache) >= self._config.max_response_entries:
                # Remove oldest (first item in OrderedDict)
                oldest_key = next(iter(self._cache))
                self._cache.pop(oldest_key)
                self._stats.evictions += 1
                logger.debug("[CACHE] Evicted LRU entry: %s...", oldest_key[:30])

            # Create entry
            entry = CacheEntry(
                key=cache_key,
                embedding=embedding,
                value=response,
                tier=CacheTier.RESPONSE,
                ttl=self._config.response_ttl,
                document_ids=document_ids or [],
                metadata=metadata or {},
                user_id=user_id,
                org_id=org_id,
            )

            self._cache[cache_key] = entry
            self._stats.total_entries = len(self._cache)

        if self._config.log_cache_operations:
            logger.info(
                "[CACHE] SET query='%s...' "
                "docs=%d "
                "ttl=%ds",
                query[:50], len(entry.document_ids), entry.ttl,
            )
    
    async def invalidate_by_document(self, document_id: str) -> int:
        """
        Invalidate all cache entries that used a specific document.
        
        Called when document content changes.
        
        Args:
            document_id: ID of updated document
            
        Returns:
            Number of entries invalidated
        """
        invalidated = 0

        async with self._lock:
            keys_to_remove = []

            for key, entry in self._cache.items():
                if document_id in entry.document_ids:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                self._cache.pop(key, None)
                invalidated += 1

            self._stats.invalidations += invalidated
            self._stats.total_entries = len(self._cache)
        
        if invalidated > 0:
            logger.info("[CACHE] Invalidated %d entries for doc: %s", invalidated, document_id)
        
        return invalidated
    
    async def clear(self) -> int:
        """
        Clear all cache entries.
        
        Returns:
            Number of entries cleared
        """
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._stats.total_entries = 0
        logger.info("[CACHE] Cleared %d entries", count)
        return count
    
    def get_stats(self) -> CacheStats:
        """Get current cache statistics."""
        self._stats.total_entries = len(self._cache)
        return self._stats
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
    
    def _update_avg_similarity(self, new_similarity: float) -> None:
        """Update running average of similarity on hits."""
        if self._stats.hits == 1:
            self._stats.avg_similarity_on_hit = new_similarity
        else:
            # Exponential moving average
            alpha = 0.1
            self._stats.avg_similarity_on_hit = (
                alpha * new_similarity + 
                (1 - alpha) * self._stats.avg_similarity_on_hit
            )


# Singleton
_semantic_cache: Optional[SemanticResponseCache] = None


def get_semantic_cache(config: Optional[CacheConfig] = None) -> SemanticResponseCache:
    """Get or create SemanticResponseCache singleton."""
    global _semantic_cache
    if _semantic_cache is None:
        _semantic_cache = SemanticResponseCache(config)
    return _semantic_cache
