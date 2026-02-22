"""
Notification Channels — Sprint 171b: Plugin Architecture

Plugin architecture for notification delivery channels.
Auto-registers adapters based on config flags.

Usage:
    from app.services.notifications import init_notification_channels, get_notification_channel_registry

    # Initialize at startup or on first use (lazy)
    init_notification_channels()

    # Get a specific adapter
    registry = get_notification_channel_registry()
    adapter = registry.get("telegram")
    if adapter:
        result = await adapter.send(user_id, message)
"""

import logging

from app.services.notifications.base import (
    ChannelConfig,
    NotificationChannelAdapter,
    NotificationResult,
)
from app.services.notifications.registry import (
    NotificationChannelRegistry,
    get_notification_channel_registry,
)

logger = logging.getLogger(__name__)


def init_notification_channels() -> NotificationChannelRegistry:
    """
    Initialize and register all enabled notification channel adapters.

    Reads feature flags from config to determine which channels to enable.

    Returns:
        The populated NotificationChannelRegistry singleton.
    """
    from app.core.config import settings

    registry = get_notification_channel_registry()
    registry.clear()

    if settings.enable_websocket:
        from app.services.notifications.adapters.websocket import WebSocketAdapter
        registry.register(WebSocketAdapter())

    if settings.enable_telegram and settings.telegram_bot_token:
        from app.services.notifications.adapters.telegram import TelegramAdapter
        registry.register(TelegramAdapter())

    if settings.living_agent_callmebot_api_key:
        from app.services.notifications.adapters.messenger import MessengerAdapter
        registry.register(MessengerAdapter())

    logger.info(
        "Notification channels initialized: %d adapters (%s)",
        len(registry),
        ", ".join(registry.list_ids()) or "none",
    )
    return registry


__all__ = [
    "ChannelConfig",
    "NotificationChannelAdapter",
    "NotificationResult",
    "NotificationChannelRegistry",
    "get_notification_channel_registry",
    "init_notification_channels",
]
