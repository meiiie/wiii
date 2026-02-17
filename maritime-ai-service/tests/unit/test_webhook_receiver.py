"""
Tests for generic webhook receiver endpoint.

Sprint 12: Multi-Channel Gateway.
Tests webhook routing, unknown channel handling, adapter lookup.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx

from app.api.v1.webhook import router
from app.channels.registry import ChannelRegistry
from app.channels.base import ChannelMessage, ChannelAdapter


@pytest.fixture
def app():
    """Create a test FastAPI app with the webhook router."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture(autouse=True)
def reset_registry():
    ChannelRegistry.reset()
    yield
    ChannelRegistry.reset()


def _make_adapter(channel_type: str, parse_result: ChannelMessage = None, format_result=None):
    """Create a mock adapter for testing."""
    adapter = MagicMock(spec=ChannelAdapter)
    adapter.channel_type = channel_type
    if parse_result:
        adapter.parse_incoming.return_value = parse_result
    else:
        adapter.parse_incoming.return_value = ChannelMessage(
            text="test", sender_id="u-1", channel_id="c-1", channel_type=channel_type
        )
    adapter.format_outgoing.return_value = format_result or {"ok": True}
    return adapter


# ============================================================================
# Webhook Receiver Tests
# ============================================================================


class TestWebhookReceiver:
    """Test the generic webhook endpoint."""

    @pytest.mark.asyncio
    async def test_unknown_channel_returns_404(self, app):
        """Webhook for unregistered channel returns 404."""
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/webhook/unknown_channel",
                json={"text": "hello"},
            )
        assert resp.status_code == 404
        assert "unknown_channel" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_registered_channel_parses_message(self, app):
        """Webhook with registered adapter parses the message."""
        registry = ChannelRegistry()
        adapter = _make_adapter("test_channel")
        registry.register(adapter)

        with patch("app.services.chat_orchestrator.ChatOrchestrator") as mock_orch:
            mock_instance = MagicMock()
            mock_instance.process = AsyncMock(return_value={
                "answer": "Response from Wiii",
                "sources": [],
                "metadata": {},
            })
            mock_orch.return_value = mock_instance

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v1/webhook/test_channel",
                    json={"content": "Hello"},
                )

        assert resp.status_code == 200
        adapter.parse_incoming.assert_called_once()
        adapter.format_outgoing.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_json_returns_400(self, app):
        """Invalid JSON body returns 400."""
        registry = ChannelRegistry()
        registry.register(_make_adapter("test"))

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/webhook/test",
                content="not json",
                headers={"Content-Type": "application/json"},
            )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_parse_error_returns_400(self, app):
        """If adapter.parse_incoming raises ValueError, return 400."""
        registry = ChannelRegistry()
        adapter = _make_adapter("test")
        adapter.parse_incoming.side_effect = ValueError("Bad format")
        registry.register(adapter)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/webhook/test",
                json={"bad": "data"},
            )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Cannot parse incoming message"

    @pytest.mark.asyncio
    async def test_orchestrator_error_returns_500(self, app):
        """If ChatOrchestrator fails, return 500."""
        registry = ChannelRegistry()
        registry.register(_make_adapter("test"))

        with patch("app.services.chat_orchestrator.ChatOrchestrator") as mock_orch:
            mock_instance = MagicMock()
            mock_instance.process = AsyncMock(side_effect=Exception("LLM down"))
            mock_orch.return_value = mock_instance

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v1/webhook/test",
                    json={"message": "test"},
                )

        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_telegram_adds_chat_id(self, app):
        """Telegram webhook response includes chat_id from metadata."""
        registry = ChannelRegistry()
        tg_msg = ChannelMessage(
            text="question",
            sender_id="42",
            channel_id="tg:42",
            channel_type="telegram",
            metadata={"telegram_chat_id": "42"},
        )
        adapter = _make_adapter("telegram", parse_result=tg_msg)
        registry.register(adapter)

        with patch("app.services.chat_orchestrator.ChatOrchestrator") as mock_orch:
            mock_instance = MagicMock()
            mock_instance.process = AsyncMock(return_value={
                "answer": "response", "sources": [], "metadata": {},
            })
            mock_orch.return_value = mock_instance

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v1/webhook/telegram",
                    json={"message": {"text": "test", "from": {"id": 42}, "chat": {"id": 42}}},
                )

        assert resp.status_code == 200
        # Verify the adapter received a response_data dict with chat_id
        call_args = adapter.format_outgoing.call_args[0][0]
        assert call_args.get("chat_id") == "42"
