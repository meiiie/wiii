"""
WebSocket Notification Adapter

Sprint 171b: Extracted from NotificationDispatcher._notify_websocket()
Sends notifications to connected user sessions via WebSocket ConnectionManager.
"""

import logging
from typing import Optional

from app.services.notifications.base import (
    ChannelConfig,
    NotificationChannelAdapter,
    NotificationResult,
)

logger = logging.getLogger(__name__)


class WebSocketAdapter(NotificationChannelAdapter):
    """Delivers notifications via WebSocket to all active user sessions."""

    def get_config(self) -> ChannelConfig:
        return ChannelConfig(
            id="websocket",
            display_name="WebSocket",
            enabled=True,
            requires_config=False,
        )

    async def send(
        self,
        user_id: str,
        message: str,
        metadata: Optional[dict] = None,
    ) -> NotificationResult:
        try:
            from app.api.v1.websocket import manager

            if not manager.is_user_online(user_id):
                logger.info("[NOTIFY] User %s is offline, WS notification queued", user_id)
                return NotificationResult(
                    delivered=False,
                    channel="websocket",
                    detail="User offline",
                )

            sent = await manager.send_to_user(user_id, message)
            logger.info("[NOTIFY] WS notification sent to user %s (%d sessions)", user_id, sent)
            return NotificationResult(
                delivered=True,
                channel="websocket",
                detail=f"Sent to {sent} sessions",
            )

        except Exception as e:
            logger.error("[NOTIFY] WS notification failed for user %s: %s", user_id, e)
            return NotificationResult(
                delivered=False,
                channel="websocket",
                detail=str(e),
            )
