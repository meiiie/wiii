"""
Notification Channel Registry — Singleton Registry for Channel Adapters

Sprint 171b: Plugin Architecture for Notification Channels

Pattern: Same as app/engine/search_platforms/registry.py (Sprint 149).
Adapters register themselves; notification_dispatcher queries this registry.
"""

import logging
import threading
from typing import Dict, List, Optional

from app.services.notifications.base import NotificationChannelAdapter

logger = logging.getLogger(__name__)

_registry_instance: Optional["NotificationChannelRegistry"] = None
_registry_lock = threading.Lock()


class NotificationChannelRegistry:
    """Singleton registry for notification channel adapters."""

    def __init__(self):
        self._adapters: Dict[str, NotificationChannelAdapter] = {}

    def register(self, adapter: NotificationChannelAdapter) -> None:
        """Register a channel adapter."""
        config = adapter.get_config()
        channel_id = config.id
        if channel_id in self._adapters:
            logger.debug("Overwriting adapter for channel '%s'", channel_id)
        self._adapters[channel_id] = adapter
        logger.debug("Registered notification channel: %s", config.display_name)

    def get(self, channel_id: str) -> Optional[NotificationChannelAdapter]:
        """Get adapter by channel ID."""
        return self._adapters.get(channel_id)

    def get_all_enabled(self) -> List[NotificationChannelAdapter]:
        """Get all adapters whose config.enabled is True."""
        return [a for a in self._adapters.values() if a.get_config().enabled]

    def list_ids(self) -> List[str]:
        """List all registered channel IDs."""
        return list(self._adapters.keys())

    def clear(self) -> None:
        """Clear all registered adapters (for testing / re-init)."""
        self._adapters.clear()

    def __len__(self) -> int:
        return len(self._adapters)


def get_notification_channel_registry() -> NotificationChannelRegistry:
    """Get or create the singleton NotificationChannelRegistry."""
    global _registry_instance
    if _registry_instance is None:
        with _registry_lock:
            if _registry_instance is None:
                _registry_instance = NotificationChannelRegistry()
    return _registry_instance
