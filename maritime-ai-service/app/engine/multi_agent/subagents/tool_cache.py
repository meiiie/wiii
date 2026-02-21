"""Request-scoped tool cache — avoid duplicate API calls within a request.

When multiple subagents or iterative search rounds call the same tool with
identical arguments, the cache returns the previous result instantly.

Usage::

    cache = RequestScopedToolCache()
    result = cache.get("tool_search_shopee", {"query": "laptop"})
    if result is None:
        result = tool.invoke(args)
        cache.set("tool_search_shopee", {"query": "laptop"}, result)
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RequestScopedToolCache:
    """In-memory cache for tool results within a single request lifetime.

    Thread-safe for single-request use (not shared across requests).
    The cache is created at request start and garbage-collected at request end.
    """

    def __init__(self, max_entries: int = 100) -> None:
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_entries = max_entries
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _make_key(tool_name: str, args: Dict[str, Any]) -> str:
        """Deterministic cache key from tool name + args."""
        args_json = json.dumps(args, sort_keys=True, ensure_ascii=False)
        args_hash = hashlib.md5(args_json.encode()).hexdigest()[:12]
        return f"{tool_name}:{args_hash}"

    def get(self, tool_name: str, args: Dict[str, Any]) -> Optional[Any]:
        """Look up cached result.  Returns ``None`` on miss."""
        key = self._make_key(tool_name, args)
        entry = self._cache.get(key)
        if entry is not None:
            self._hits += 1
            logger.debug("Tool cache HIT: %s", key)
            return entry["result"]
        self._misses += 1
        return None

    def set(self, tool_name: str, args: Dict[str, Any], result: Any) -> None:
        """Store tool result in cache."""
        if len(self._cache) >= self._max_entries:
            # Evict oldest entry
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        key = self._make_key(tool_name, args)
        self._cache[key] = {
            "result": result,
            "timestamp": time.monotonic(),
        }

    def invalidate(self, tool_name: str, args: Dict[str, Any]) -> bool:
        """Remove a specific entry.  Returns ``True`` if it existed."""
        key = self._make_key(tool_name, args)
        return self._cache.pop(key, None) is not None

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        """Cache hit rate (0.0–1.0).  Returns 0.0 if no lookups."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        return {
            "size": self.size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate, 3),
        }
