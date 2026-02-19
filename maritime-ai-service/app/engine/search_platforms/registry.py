"""
Search Platform Registry — Singleton Registry for Platform Adapters

Sprint 149: "Cắm & Chạy" — Plugin Architecture for Product Search

Pattern: Same as app/domains/registry.py (DomainRegistry singleton).
Adapters register themselves; tools/product_search_tools.py queries this registry.
"""

import logging
import threading
from typing import Dict, List, Optional

from app.engine.search_platforms.base import SearchPlatformAdapter

logger = logging.getLogger(__name__)

_registry_instance: Optional["SearchPlatformRegistry"] = None
_registry_lock = threading.Lock()


class SearchPlatformRegistry:
    """Singleton registry for search platform adapters."""

    def __init__(self):
        self._adapters: Dict[str, SearchPlatformAdapter] = {}

    def register(self, adapter: SearchPlatformAdapter) -> None:
        """Register a platform adapter."""
        config = adapter.get_config()
        platform_id = config.id
        if platform_id in self._adapters:
            logger.debug("Overwriting adapter for platform '%s'", platform_id)
        self._adapters[platform_id] = adapter
        logger.debug("Registered search platform: %s (%s)", config.display_name, config.backend.value)

    def get(self, platform_id: str) -> Optional[SearchPlatformAdapter]:
        """Get adapter by platform ID."""
        return self._adapters.get(platform_id)

    def get_all_enabled(self) -> List[SearchPlatformAdapter]:
        """Get all adapters whose config.enabled is True."""
        return [a for a in self._adapters.values() if a.get_config().enabled]

    def list_ids(self) -> List[str]:
        """List all registered platform IDs."""
        return list(self._adapters.keys())

    def clear(self) -> None:
        """Clear all registered adapters (for testing)."""
        self._adapters.clear()

    def __len__(self) -> int:
        return len(self._adapters)


def get_search_platform_registry() -> SearchPlatformRegistry:
    """Get or create the singleton SearchPlatformRegistry."""
    global _registry_instance
    if _registry_instance is None:
        with _registry_lock:
            if _registry_instance is None:
                _registry_instance = SearchPlatformRegistry()
    return _registry_instance
