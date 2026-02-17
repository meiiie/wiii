"""
Tests for Sprint 47: EventCallbackService coverage.

Tests LMS event webhook service including:
- EventCallbackService init
- _get_client (lazy HTTP client)
- send_event (success, failure, no URL, timeout, circuit breaker)
- Convenience methods (emit_knowledge_gap, emit_goal_evolution, emit_module_completed, emit_stuck_detected)
- close
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx


# ============================================================================
# EventCallbackService init
# ============================================================================


class TestEventCallbackServiceInit:
    """Test EventCallbackService initialization."""

    def test_init(self):
        with patch("app.services.event_callback_service.settings") as mock_settings:
            mock_settings.lms_callback_url = "https://lms.example.com/webhook"
            mock_settings.lms_callback_secret = "secret123"
            from app.services.event_callback_service import EventCallbackService
            svc = EventCallbackService()
            assert svc.callback_url == "https://lms.example.com/webhook"
            assert svc.callback_secret == "secret123"
            assert svc._client is None

    def test_init_no_url(self):
        with patch("app.services.event_callback_service.settings") as mock_settings:
            mock_settings.lms_callback_url = None
            mock_settings.lms_callback_secret = None
            from app.services.event_callback_service import EventCallbackService
            svc = EventCallbackService()
            assert svc.callback_url is None


# ============================================================================
# _get_client
# ============================================================================


class TestGetClient:
    """Test lazy HTTP client initialization."""

    @pytest.mark.asyncio
    async def test_creates_client(self):
        with patch("app.services.event_callback_service.settings") as mock_settings:
            mock_settings.lms_callback_url = "https://example.com"
            mock_settings.lms_callback_secret = None
            from app.services.event_callback_service import EventCallbackService
            svc = EventCallbackService()
            client = await svc._get_client()
            assert client is not None
            await client.aclose()

    @pytest.mark.asyncio
    async def test_reuses_client(self):
        with patch("app.services.event_callback_service.settings") as mock_settings:
            mock_settings.lms_callback_url = "https://example.com"
            mock_settings.lms_callback_secret = None
            from app.services.event_callback_service import EventCallbackService
            svc = EventCallbackService()
            client1 = await svc._get_client()
            client2 = await svc._get_client()
            assert client1 is client2
            await client1.aclose()


# ============================================================================
# send_event
# ============================================================================


class TestSendEvent:
    """Test send_event."""

    def _make_event(self):
        from app.models.schemas import AIEvent, AIEventData, AIEventType
        return AIEvent(
            user_id="user1",
            event_type=AIEventType.KNOWLEDGE_GAP_DETECTED,
            data=AIEventData(topic="Rule 15", confidence=0.8)
        )

    @pytest.mark.asyncio
    async def test_no_url_returns_false(self):
        with patch("app.services.event_callback_service.settings") as mock_settings:
            mock_settings.lms_callback_url = None
            mock_settings.lms_callback_secret = None
            from app.services.event_callback_service import EventCallbackService
            svc = EventCallbackService()
            result = await svc.send_event(self._make_event())
            assert result is False

    @pytest.mark.asyncio
    async def test_success(self):
        with patch("app.services.event_callback_service.settings") as mock_settings:
            mock_settings.lms_callback_url = "https://example.com/webhook"
            mock_settings.lms_callback_secret = "secret"
            from app.services.event_callback_service import EventCallbackService
            svc = EventCallbackService()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.is_closed = False
            svc._client = mock_client

            with patch("app.services.event_callback_service._cb", None):
                result = await svc.send_event(self._make_event())
                assert result is True
                mock_client.post.assert_called_once()
                # Verify secret header
                call_kwargs = mock_client.post.call_args
                assert call_kwargs.kwargs["headers"]["X-Callback-Secret"] == "secret"

    @pytest.mark.asyncio
    async def test_failure_status(self):
        with patch("app.services.event_callback_service.settings") as mock_settings:
            mock_settings.lms_callback_url = "https://example.com/webhook"
            mock_settings.lms_callback_secret = None
            from app.services.event_callback_service import EventCallbackService
            svc = EventCallbackService()

            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.is_closed = False
            svc._client = mock_client

            with patch("app.services.event_callback_service._cb", None):
                result = await svc.send_event(self._make_event())
                assert result is False

    @pytest.mark.asyncio
    async def test_timeout(self):
        with patch("app.services.event_callback_service.settings") as mock_settings:
            mock_settings.lms_callback_url = "https://example.com/webhook"
            mock_settings.lms_callback_secret = None
            from app.services.event_callback_service import EventCallbackService
            svc = EventCallbackService()

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_client.is_closed = False
            svc._client = mock_client

            with patch("app.services.event_callback_service._cb", None):
                result = await svc.send_event(self._make_event())
                assert result is False

    @pytest.mark.asyncio
    async def test_general_error(self):
        with patch("app.services.event_callback_service.settings") as mock_settings:
            mock_settings.lms_callback_url = "https://example.com/webhook"
            mock_settings.lms_callback_secret = None
            from app.services.event_callback_service import EventCallbackService
            svc = EventCallbackService()

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("Network error"))
            mock_client.is_closed = False
            svc._client = mock_client

            with patch("app.services.event_callback_service._cb", None):
                result = await svc.send_event(self._make_event())
                assert result is False

    @pytest.mark.asyncio
    async def test_circuit_breaker_open(self):
        with patch("app.services.event_callback_service.settings") as mock_settings:
            mock_settings.lms_callback_url = "https://example.com/webhook"
            mock_settings.lms_callback_secret = None
            from app.services.event_callback_service import EventCallbackService
            svc = EventCallbackService()

            mock_cb = MagicMock()
            mock_cb.is_available.return_value = False
            mock_cb.retry_after = 60.0

            with patch("app.services.event_callback_service._cb", mock_cb):
                result = await svc.send_event(self._make_event())
                assert result is False


# ============================================================================
# close
# ============================================================================


class TestClose:
    """Test close."""

    @pytest.mark.asyncio
    async def test_close_client(self):
        with patch("app.services.event_callback_service.settings") as mock_settings:
            mock_settings.lms_callback_url = "https://example.com"
            mock_settings.lms_callback_secret = None
            from app.services.event_callback_service import EventCallbackService
            svc = EventCallbackService()
            mock_client = AsyncMock()
            mock_client.is_closed = False
            svc._client = mock_client
            await svc.close()
            mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_no_client(self):
        with patch("app.services.event_callback_service.settings") as mock_settings:
            mock_settings.lms_callback_url = "https://example.com"
            mock_settings.lms_callback_secret = None
            from app.services.event_callback_service import EventCallbackService
            svc = EventCallbackService()
            await svc.close()  # Should not raise


# ============================================================================
# Convenience methods
# ============================================================================


class TestConvenienceMethods:
    """Test emit_* convenience methods."""

    def _make_svc(self):
        with patch("app.services.event_callback_service.settings") as mock_settings:
            mock_settings.lms_callback_url = "https://example.com"
            mock_settings.lms_callback_secret = None
            from app.services.event_callback_service import EventCallbackService
            svc = EventCallbackService()
            svc.send_event_background = MagicMock()
            return svc

    @pytest.mark.asyncio
    async def test_emit_knowledge_gap(self):
        svc = self._make_svc()
        await svc.emit_knowledge_gap("user1", "Rule 15", 0.8)
        svc.send_event_background.assert_called_once()
        event = svc.send_event_background.call_args[0][0]
        assert event.user_id == "user1"
        assert event.data.topic == "Rule 15"

    @pytest.mark.asyncio
    async def test_emit_goal_evolution(self):
        svc = self._make_svc()
        await svc.emit_goal_evolution("user1", "old goal", "new goal")
        svc.send_event_background.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_module_completed(self):
        svc = self._make_svc()
        await svc.emit_module_completed("user1", "module1", 0.9)
        svc.send_event_background.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_stuck_detected(self):
        svc = self._make_svc()
        await svc.emit_stuck_detected("user1", "Rule 15", 3)
        svc.send_event_background.assert_called_once()
