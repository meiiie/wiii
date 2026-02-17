"""
Cache Data Models - SOTA RAG Latency Optimization.

Defines cache entry structures and configuration.

Feature: semantic-cache
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CacheTier(str, Enum):
    """Cache tier enumeration."""
    RESPONSE = "response"      # L1: Full answers
    RETRIEVAL = "retrieval"    # L2: Document sets
    EMBEDDING = "embedding"    # L3: Query vectors


@dataclass
class CacheConfig:
    """
    Configuration for cache behavior.
    
    Thresholds are conservative by default (per expert recommendation).
    """
    # Semantic similarity threshold for cache hits (industry standard: 0.85-0.95)
    similarity_threshold: float = 0.92
    
    # TTL settings (seconds)
    response_ttl: int = 7200       # 2 hours
    retrieval_ttl: int = 1800      # 30 minutes
    embedding_ttl: int = 3600      # 1 hour
    
    # Size limits
    max_response_entries: int = 10000
    max_retrieval_entries: int = 5000
    max_embedding_entries: int = 50000
    
    # Adaptive TTL (Sprint 66: hot queries get longer TTL)
    adaptive_ttl: bool = True
    adaptive_ttl_max_multiplier: float = 3.0  # Max 3x base TTL

    # Feature flags
    enabled: bool = True
    log_cache_operations: bool = True


@dataclass
class CacheEntry:
    """
    A single cache entry with metadata.
    
    Stores embedding for semantic matching and tracks usage.
    """
    # Core data
    key: str                           # Original query or identifier
    embedding: List[float]             # Query embedding for similarity
    value: Any                         # Cached response/documents/embedding
    tier: CacheTier
    user_id: str = ""                  # Sprint 121 RC-6: User isolation for cache
    
    # Timestamps
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    ttl: int = 7200  # Default 2 hours
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    access_count: int = 0
    
    # For L1 response cache: track which documents were used
    document_ids: List[str] = field(default_factory=list)
    
    def is_expired(self, adaptive_ttl: bool = False, max_multiplier: float = 3.0) -> bool:
        """Check if entry has expired based on TTL.

        Args:
            adaptive_ttl: If True, hot queries get longer effective TTL.
            max_multiplier: Maximum TTL multiplier for frequently accessed entries.
        """
        effective_ttl = self.get_effective_ttl(adaptive_ttl, max_multiplier)
        return time.time() - self.created_at > effective_ttl

    def get_effective_ttl(self, adaptive_ttl: bool = False, max_multiplier: float = 3.0) -> float:
        """Calculate effective TTL based on access frequency.

        Adaptive TTL pattern: frequently accessed entries survive longer.
        Formula: base_ttl * min(1 + access_count * 0.25, max_multiplier)

        Examples (base_ttl=7200s=2h):
          - 0 accesses: 7200s (2h)
          - 2 accesses: 10800s (3h)
          - 4 accesses: 14400s (4h)
          - 8+ accesses: 21600s (6h, capped at 3x)
        """
        if not adaptive_ttl or self.access_count == 0:
            return self.ttl
        multiplier = min(1.0 + self.access_count * 0.25, max_multiplier)
        return self.ttl * multiplier

    def touch(self) -> None:
        """Update last access time and increment counter."""
        self.last_accessed = time.time()
        self.access_count += 1

    @property
    def age_seconds(self) -> float:
        """Get age of entry in seconds."""
        return time.time() - self.created_at

    @property
    def remaining_ttl(self) -> float:
        """Get remaining TTL in seconds (without adaptive adjustment)."""
        return max(0, self.ttl - self.age_seconds)


@dataclass
class CacheStats:
    """Statistics for cache performance monitoring."""
    tier: CacheTier
    total_entries: int = 0
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    invalidations: int = 0
    avg_similarity_on_hit: float = 0.0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "tier": self.tier.value,
            "total_entries": self.total_entries,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{self.hit_rate:.2%}",
            "evictions": self.evictions,
            "invalidations": self.invalidations,
            "avg_similarity_on_hit": f"{self.avg_similarity_on_hit:.3f}"
        }


@dataclass
class CacheLookupResult:
    """Result of a cache lookup operation."""
    hit: bool
    entry: Optional[CacheEntry] = None
    similarity: float = 0.0
    tier: Optional[CacheTier] = None
    lookup_time_ms: float = 0.0
    
    @property
    def value(self) -> Any:
        """Get cached value if hit."""
        return self.entry.value if self.entry else None
