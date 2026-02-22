"""
Notification Channel Adapter — Abstract Base Class + Data Models

Sprint 171b: Plugin Architecture for Notification Channels

Pattern: Mirrors app/engine/search_platforms/base.py (Sprint 149).
Each channel implements NotificationChannelAdapter to normalize delivery.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ChannelConfig:
    """Configuration for a notification channel adapter."""
    id: str                        # e.g. "websocket", "telegram", "messenger"
    display_name: str              # e.g. "WebSocket", "Telegram Bot"
    enabled: bool = True
    requires_config: bool = False  # True if external credentials needed


@dataclass
class NotificationResult:
    """Standardized result from a notification delivery attempt."""
    delivered: bool
    channel: str
    detail: str = ""

    def to_dict(self) -> dict:
        """Convert to dict for backward compatibility with existing API."""
        return {
            "delivered": self.delivered,
            "channel": self.channel,
            "detail": self.detail,
        }


class NotificationChannelAdapter(ABC):
    """
    Abstract base class for notification channel adapters.

    Subclasses must implement:
    - get_config() -> ChannelConfig
    - send(user_id, message, metadata) -> NotificationResult
    """

    @abstractmethod
    def get_config(self) -> ChannelConfig:
        """Return channel configuration."""
        ...

    @abstractmethod
    async def send(
        self,
        user_id: str,
        message: str,
        metadata: Optional[dict] = None,
    ) -> NotificationResult:
        """
        Deliver a notification to a user.

        Args:
            user_id: Target user ID
            message: Notification content (may be raw text or JSON payload)
            metadata: Additional metadata

        Returns:
            NotificationResult with delivery status
        """
        ...

    def validate_config(self) -> bool:
        """Check if required config is available.

        Override for channels needing credentials.
        """
        return True
