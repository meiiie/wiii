"""
LMS Connector Registry — Singleton Registry for LMS Connector Adapters

Sprint 155b: Multi-LMS Plugin Architecture

Pattern: Mirrors SearchPlatformRegistry (app/engine/search_platforms/registry.py).
Connectors register themselves; webhook handler queries this registry by source ID.
"""

import logging
import threading
from typing import Dict, List, Optional

from app.integrations.lms.base import LMSConnectorAdapter

logger = logging.getLogger(__name__)

_registry_instance: Optional["LMSConnectorRegistry"] = None
_registry_lock = threading.Lock()


class LMSConnectorRegistry:
    """Singleton registry for LMS connector adapters."""

    def __init__(self):
        self._connectors: Dict[str, LMSConnectorAdapter] = {}

    def register(self, adapter: LMSConnectorAdapter) -> None:
        """Register an LMS connector adapter."""
        config = adapter.get_config()
        connector_id = config.id
        if connector_id in self._connectors:
            logger.debug("Overwriting LMS connector: '%s'", connector_id)
        self._connectors[connector_id] = adapter
        logger.info(
            "Registered LMS connector: %s (%s) at %s",
            config.display_name, config.backend_type.value, config.base_url or "N/A",
        )

    def get(self, connector_id: str) -> Optional[LMSConnectorAdapter]:
        """Get connector by ID."""
        return self._connectors.get(connector_id)

    def get_all_enabled(self) -> List[LMSConnectorAdapter]:
        """Get all connectors whose config.enabled is True."""
        return [a for a in self._connectors.values() if a.get_config().enabled]

    def list_ids(self) -> List[str]:
        """List all registered connector IDs."""
        return list(self._connectors.keys())

    def clear(self) -> None:
        """Clear all registered connectors (for testing)."""
        self._connectors.clear()

    def __len__(self) -> int:
        return len(self._connectors)


def get_lms_connector_registry() -> LMSConnectorRegistry:
    """Get or create the singleton LMSConnectorRegistry."""
    global _registry_instance
    if _registry_instance is None:
        with _registry_lock:
            if _registry_instance is None:
                _registry_instance = LMSConnectorRegistry()
    return _registry_instance
