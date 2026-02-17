"""
Channel Registry — Singleton registry for channel adapters.

Manages registered channel adapters, enabling dynamic routing
of incoming messages to the correct adapter.
"""

import logging
from typing import Dict, List, Optional

from app.channels.base import ChannelAdapter

logger = logging.getLogger(__name__)


class ChannelRegistry:
    """
    Singleton registry for channel adapters.

    Adapters are registered at startup and looked up by channel_type
    when incoming messages arrive via the webhook endpoint.
    """

    _instance: Optional["ChannelRegistry"] = None
    _adapters: Dict[str, ChannelAdapter] = {}

    def __new__(cls) -> "ChannelRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._adapters = {}
        return cls._instance

    def register(self, adapter: ChannelAdapter) -> None:
        """
        Register a channel adapter.

        Args:
            adapter: ChannelAdapter instance to register
        """
        channel_type = adapter.channel_type
        if channel_type in self._adapters:
            logger.warning(
                "[CHANNEL_REGISTRY] Overwriting adapter for '%s'",
                channel_type,
            )
        self._adapters[channel_type] = adapter
        logger.info("[CHANNEL_REGISTRY] Registered adapter: %s", channel_type)

    def get(self, channel_type: str) -> Optional[ChannelAdapter]:
        """
        Get a registered adapter by channel type.

        Args:
            channel_type: The channel type identifier

        Returns:
            ChannelAdapter or None if not registered
        """
        return self._adapters.get(channel_type)

    def list_all(self) -> List[str]:
        """List all registered channel types."""
        return list(self._adapters.keys())

    def is_registered(self, channel_type: str) -> bool:
        """Check if a channel type has a registered adapter."""
        return channel_type in self._adapters

    def unregister(self, channel_type: str) -> bool:
        """
        Remove a registered adapter.

        Returns:
            True if the adapter was removed, False if not found
        """
        if channel_type in self._adapters:
            del self._adapters[channel_type]
            logger.info("[CHANNEL_REGISTRY] Unregistered adapter: %s", channel_type)
            return True
        return False

    def clear(self) -> None:
        """Remove all registered adapters."""
        self._adapters.clear()
        logger.info("[CHANNEL_REGISTRY] All adapters cleared")

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        cls._instance = None
        cls._adapters = {}
