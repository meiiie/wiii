"""
Notification Dispatcher — Multi-channel notification routing for Wiii.

Sprint 20: Proactive Agent Activation.
Routes notifications to users via their preferred channel (WebSocket, Telegram).
Used by the scheduled task executor to deliver task results.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """
    Routes notifications to users based on channel preference.

    Supports WebSocket (push to connected sessions) and Telegram (bot API).
    Falls back gracefully when a channel is unavailable.
    """

    async def notify_user(
        self,
        user_id: str,
        message: str,
        channel: str = "websocket",
        metadata: Optional[dict] = None,
    ) -> dict:
        """
        Dispatch a notification to a user.

        Args:
            user_id: Target user ID
            message: Notification content
            channel: Delivery channel ("websocket" or "telegram")
            metadata: Additional metadata to include in the notification

        Returns:
            {"delivered": bool, "channel": str, "detail": str}
        """
        if channel == "websocket":
            return await self._notify_websocket(user_id, message, metadata)
        elif channel == "telegram":
            return await self._notify_telegram(user_id, message, metadata)
        else:
            logger.warning("[NOTIFY] Unknown channel '%s' for user %s", channel, user_id)
            return {
                "delivered": False,
                "channel": channel,
                "detail": f"Unknown channel: {channel}",
            }

    async def notify_task_result(self, task: dict, result: dict) -> dict:
        """
        Format and send a scheduled task result to its owner.

        Args:
            task: Scheduled task dict from repository
            result: Execution result dict with "mode" and "response"

        Returns:
            Delivery status dict
        """
        user_id = task.get("user_id", "")
        channel = task.get("channel", "websocket")

        payload = json.dumps(
            {
                "type": "scheduled_task",
                "task_id": task.get("id", ""),
                "description": task.get("description", ""),
                "content": result.get("response", ""),
                "mode": result.get("mode", "notification"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
        )

        return await self.notify_user(
            user_id=user_id,
            message=payload,
            channel=channel,
            metadata={"task_id": task.get("id")},
        )

    async def _notify_websocket(
        self, user_id: str, message: str, metadata: Optional[dict] = None
    ) -> dict:
        """Send notification via WebSocket to all user sessions."""
        try:
            from app.api.v1.websocket import manager

            if not manager.is_user_online(user_id):
                logger.info("[NOTIFY] User %s is offline, WS notification queued", user_id)
                return {
                    "delivered": False,
                    "channel": "websocket",
                    "detail": "User offline",
                }

            sent = await manager.send_to_user(user_id, message)
            logger.info("[NOTIFY] WS notification sent to user %s (%d sessions)", user_id, sent)
            return {
                "delivered": True,
                "channel": "websocket",
                "detail": f"Sent to {sent} sessions",
            }

        except Exception as e:
            logger.error("[NOTIFY] WS notification failed for user %s: %s", user_id, e)
            return {
                "delivered": False,
                "channel": "websocket",
                "detail": str(e),
            }

    async def _notify_telegram(
        self, user_id: str, message: str, metadata: Optional[dict] = None
    ) -> dict:
        """Send notification via Telegram bot API."""
        try:
            from app.core.config import settings

            if not settings.telegram_bot_token:
                return {
                    "delivered": False,
                    "channel": "telegram",
                    "detail": "Telegram bot token not configured",
                }

            # Parse message if it's a JSON payload, extract content for Telegram
            try:
                payload = json.loads(message)
                text = payload.get("content") or payload.get("description", message)
            except (json.JSONDecodeError, TypeError):
                text = message

            # Use httpx to call Telegram Bot API
            import httpx

            url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    url,
                    json={
                        "chat_id": user_id,
                        "text": text,
                        "parse_mode": "Markdown",
                    },
                )

            if response.status_code == 200:
                logger.info("[NOTIFY] Telegram notification sent to user %s", user_id)
                return {
                    "delivered": True,
                    "channel": "telegram",
                    "detail": "Sent via Telegram Bot API",
                }
            else:
                detail = f"Telegram API error: {response.status_code}"
                logger.warning("[NOTIFY] %s", detail)
                return {"delivered": False, "channel": "telegram", "detail": detail}

        except Exception as e:
            logger.error("[NOTIFY] Telegram notification failed for user %s: %s", user_id, e)
            return {
                "delivered": False,
                "channel": "telegram",
                "detail": str(e),
            }


# =============================================================================
# Singleton
# =============================================================================

_dispatcher: Optional[NotificationDispatcher] = None


def get_notification_dispatcher() -> NotificationDispatcher:
    """Get or create the NotificationDispatcher singleton."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = NotificationDispatcher()
    return _dispatcher
