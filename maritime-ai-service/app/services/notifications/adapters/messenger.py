"""
Messenger Notification Adapter (CallMeBot)

Sprint 171b: Extracted from NotificationDispatcher._notify_messenger()
Sends notifications via Facebook Messenger using CallMeBot API.

Setup: User sends "create apikey" to CallMeBot on Messenger to get their API key.
API: GET https://api.callmebot.com/facebook/send.php?apikey=KEY&text=MESSAGE
"""

import json
import logging
from typing import Optional

from app.services.notifications.base import (
    ChannelConfig,
    NotificationChannelAdapter,
    NotificationResult,
)

logger = logging.getLogger(__name__)


class MessengerAdapter(NotificationChannelAdapter):
    """Delivers notifications via Facebook Messenger using CallMeBot API."""

    def get_config(self) -> ChannelConfig:
        return ChannelConfig(
            id="messenger",
            display_name="Facebook Messenger (CallMeBot)",
            enabled=True,
            requires_config=True,
        )

    def validate_config(self) -> bool:
        from app.core.config import settings
        return bool(settings.living_agent_callmebot_api_key)

    async def send(
        self,
        user_id: str,
        message: str,
        metadata: Optional[dict] = None,
    ) -> NotificationResult:
        try:
            from app.core.config import settings

            api_key = settings.living_agent_callmebot_api_key
            if not api_key:
                return NotificationResult(
                    delivered=False,
                    channel="messenger",
                    detail="CallMeBot API key not configured (LIVING_AGENT_CALLMEBOT_API_KEY)",
                )

            # Parse message if it's a JSON payload
            try:
                payload = json.loads(message)
                text = payload.get("content") or payload.get("description", message)
            except (json.JSONDecodeError, TypeError):
                text = message

            import httpx
            from urllib.parse import quote

            url = (
                f"https://api.callmebot.com/facebook/send.php"
                f"?apikey={quote(api_key)}"
                f"&text={quote(text[:4000])}"
            )

            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url)

            if response.status_code == 200:
                logger.info("[NOTIFY] Messenger notification sent via CallMeBot")
                return NotificationResult(
                    delivered=True,
                    channel="messenger",
                    detail="Sent via CallMeBot",
                )
            else:
                detail = f"CallMeBot API error: {response.status_code} — {response.text[:200]}"
                logger.warning("[NOTIFY] %s", detail)
                return NotificationResult(delivered=False, channel="messenger", detail=detail)

        except Exception as e:
            logger.error("[NOTIFY] Messenger notification failed: %s", e)
            return NotificationResult(
                delivered=False,
                channel="messenger",
                detail=str(e),
            )
