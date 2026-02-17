"""
Tests for NotificationDispatcher — Multi-channel notification routing.

Sprint 20: Proactive Agent Activation.

Verifies:
- WebSocket notification delivery (user online/offline)
- Telegram notification delivery (with/without token)
- Task result formatting
- Unknown channel handling
- Vietnamese message content
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.notification_dispatcher import (
    NotificationDispatcher,
    get_notification_dispatcher,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def dispatcher():
    """Fresh NotificationDispatcher instance."""
    return NotificationDispatcher()


@pytest.fixture
def sample_task():
    """Sample scheduled task dict."""
    return {
        "id": "task-abc-12345678",
        "user_id": "user-1",
        "domain_id": "maritime",
        "description": "Nhắc ôn tập COLREGs Rule 13",
        "schedule_type": "once",
        "channel": "websocket",
        "extra_data": {},
    }


@pytest.fixture
def sample_result():
    """Sample execution result."""
    return {
        "mode": "notification",
        "response": "Đã đến giờ ôn tập COLREGs Rule 13 — Overtaking!",
    }


# =============================================================================
# WebSocket notifications
# =============================================================================

class TestWebSocketNotification:

    @pytest.mark.asyncio
    async def test_notify_user_online(self, dispatcher):
        """Delivers notification when user is online."""
        mock_manager = MagicMock()
        mock_manager.is_user_online.return_value = True
        mock_manager.send_to_user = AsyncMock(return_value=2)

        # Lazy import inside _notify_websocket → patch at source module
        with patch("app.api.v1.websocket.manager", mock_manager):
            result = await dispatcher._notify_websocket("user-1", "hello")

        assert result["delivered"] is True
        assert result["channel"] == "websocket"
        assert "2 sessions" in result["detail"]

    @pytest.mark.asyncio
    async def test_notify_user_offline(self, dispatcher):
        """Handles offline user gracefully."""
        mock_manager = MagicMock()
        mock_manager.is_user_online.return_value = False

        with patch("app.api.v1.websocket.manager", mock_manager):
            result = await dispatcher._notify_websocket("user-1", "hello")

        assert result["delivered"] is False
        assert "offline" in result["detail"].lower()

    @pytest.mark.asyncio
    async def test_notify_websocket_exception(self, dispatcher):
        """Handles WebSocket errors gracefully."""
        with patch(
            "app.api.v1.websocket.manager",
            side_effect=RuntimeError("Connection pool full"),
        ):
            result = await dispatcher._notify_websocket("user-1", "hello")

        assert result["delivered"] is False
        assert result["channel"] == "websocket"

    @pytest.mark.asyncio
    async def test_notify_user_via_channel_websocket(self, dispatcher):
        """notify_user routes to WebSocket correctly."""
        dispatcher._notify_websocket = AsyncMock(
            return_value={"delivered": True, "channel": "websocket", "detail": "ok"}
        )

        result = await dispatcher.notify_user("user-1", "test", channel="websocket")

        assert result["delivered"] is True
        dispatcher._notify_websocket.assert_called_once()


# =============================================================================
# Telegram notifications
# =============================================================================

class TestTelegramNotification:

    @pytest.mark.asyncio
    async def test_notify_telegram_no_token(self, dispatcher):
        """Returns not delivered when bot token is not configured."""
        mock_settings = MagicMock()
        mock_settings.telegram_bot_token = None

        with patch("app.core.config.settings", mock_settings):
            result = await dispatcher._notify_telegram("user-1", "test")

        assert result["delivered"] is False
        assert "not configured" in result["detail"]

    @pytest.mark.asyncio
    async def test_notify_telegram_success(self, dispatcher):
        """Delivers via Telegram Bot API successfully."""
        mock_settings = MagicMock()
        mock_settings.telegram_bot_token = "bot-token-123"

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("app.core.config.settings", mock_settings), \
             patch("httpx.AsyncClient", return_value=mock_client):
            result = await dispatcher._notify_telegram("user-1", "Hello!")

        assert result["delivered"] is True
        assert result["channel"] == "telegram"

    @pytest.mark.asyncio
    async def test_notify_telegram_api_error(self, dispatcher):
        """Handles Telegram API error response."""
        mock_settings = MagicMock()
        mock_settings.telegram_bot_token = "bot-token-123"

        mock_response = MagicMock()
        mock_response.status_code = 403

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("app.core.config.settings", mock_settings), \
             patch("httpx.AsyncClient", return_value=mock_client):
            result = await dispatcher._notify_telegram("user-1", "test")

        assert result["delivered"] is False
        assert "403" in result["detail"]

    @pytest.mark.asyncio
    async def test_notify_telegram_json_payload(self, dispatcher):
        """Extracts content from JSON payload for Telegram text."""
        mock_settings = MagicMock()
        mock_settings.telegram_bot_token = "bot-token-123"

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        payload = json.dumps({"content": "Đã đến giờ ôn tập!", "type": "scheduled_task"})

        with patch("app.core.config.settings", mock_settings), \
             patch("httpx.AsyncClient", return_value=mock_client):
            await dispatcher._notify_telegram("user-1", payload)

        # Verify the text sent is the extracted content, not raw JSON
        call_args = mock_client.post.call_args
        sent_text = call_args[1]["json"]["text"]
        assert sent_text == "Đã đến giờ ôn tập!"

    @pytest.mark.asyncio
    async def test_notify_user_via_channel_telegram(self, dispatcher):
        """notify_user routes to Telegram correctly."""
        dispatcher._notify_telegram = AsyncMock(
            return_value={"delivered": True, "channel": "telegram", "detail": "ok"}
        )

        result = await dispatcher.notify_user("user-1", "test", channel="telegram")

        assert result["delivered"] is True
        dispatcher._notify_telegram.assert_called_once()


# =============================================================================
# Unknown channel
# =============================================================================

class TestUnknownChannel:

    @pytest.mark.asyncio
    async def test_unknown_channel(self, dispatcher):
        """Unknown channel returns not delivered."""
        result = await dispatcher.notify_user("user-1", "test", channel="carrier_pigeon")

        assert result["delivered"] is False
        assert "Unknown channel" in result["detail"]


# =============================================================================
# Task result formatting
# =============================================================================

class TestNotifyTaskResult:

    @pytest.mark.asyncio
    async def test_task_result_format(self, dispatcher, sample_task, sample_result):
        """notify_task_result formats payload correctly."""
        sent_payloads = []

        async def mock_notify(user_id, message, channel="websocket", metadata=None):
            sent_payloads.append(json.loads(message))
            return {"delivered": True, "channel": channel, "detail": "ok"}

        dispatcher.notify_user = mock_notify

        await dispatcher.notify_task_result(sample_task, sample_result)

        assert len(sent_payloads) == 1
        payload = sent_payloads[0]
        assert payload["type"] == "scheduled_task"
        assert payload["task_id"] == "task-abc-12345678"
        assert payload["description"] == "Nhắc ôn tập COLREGs Rule 13"
        assert payload["content"] == sample_result["response"]
        assert payload["mode"] == "notification"
        assert "timestamp" in payload

    @pytest.mark.asyncio
    async def test_task_result_uses_task_channel(self, dispatcher, sample_task, sample_result):
        """notify_task_result uses the task's channel preference."""
        sample_task["channel"] = "telegram"
        calls = []

        async def mock_notify(user_id, message, channel="websocket", metadata=None):
            calls.append(channel)
            return {"delivered": True, "channel": channel, "detail": "ok"}

        dispatcher.notify_user = mock_notify
        await dispatcher.notify_task_result(sample_task, sample_result)

        assert calls[0] == "telegram"

    @pytest.mark.asyncio
    async def test_task_result_vietnamese_content(self, dispatcher):
        """Vietnamese content is preserved (ensure_ascii=False)."""
        task = {"id": "t1", "user_id": "u1", "description": "Ôn tập Luật Giao thông", "channel": "websocket"}
        result = {"mode": "agent", "response": "Theo Điều 12 Luật GTĐB..."}
        sent = []

        async def mock_notify(user_id, message, channel="websocket", metadata=None):
            sent.append(message)
            return {"delivered": True, "channel": channel, "detail": "ok"}

        dispatcher.notify_user = mock_notify
        await dispatcher.notify_task_result(task, result)

        payload = json.loads(sent[0])
        assert "Ôn tập" in payload["description"]
        assert "Điều 12" in payload["content"]


# =============================================================================
# Singleton
# =============================================================================

class TestSingleton:

    def test_get_notification_dispatcher_singleton(self):
        """Singleton returns same instance."""
        import app.services.notification_dispatcher as mod
        mod._dispatcher = None  # Reset

        d1 = get_notification_dispatcher()
        d2 = get_notification_dispatcher()
        assert d1 is d2

        mod._dispatcher = None  # Clean up
