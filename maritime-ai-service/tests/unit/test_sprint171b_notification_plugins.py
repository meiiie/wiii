"""
Tests for Sprint 171b: Notification Plugin Architecture

Verifies:
- NotificationChannelAdapter ABC contract
- ChannelConfig and NotificationResult data models
- NotificationChannelRegistry (register/get/clear/list_ids/get_all_enabled)
- init_notification_channels() with config flag combinations
- Dispatcher integration with registry
- Each adapter: config, send success, send failure
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.notifications.base import (
    ChannelConfig,
    NotificationChannelAdapter,
    NotificationResult,
)
from app.services.notifications.registry import (
    NotificationChannelRegistry,
    get_notification_channel_registry,
)


# =============================================================================
# Data Model Tests
# =============================================================================

class TestChannelConfig:
    """Tests for ChannelConfig dataclass."""

    def test_defaults(self):
        cfg = ChannelConfig(id="test", display_name="Test Channel")
        assert cfg.id == "test"
        assert cfg.display_name == "Test Channel"
        assert cfg.enabled is True
        assert cfg.requires_config is False

    def test_custom_values(self):
        cfg = ChannelConfig(id="x", display_name="X", enabled=False, requires_config=True)
        assert cfg.enabled is False
        assert cfg.requires_config is True


class TestNotificationResult:
    """Tests for NotificationResult dataclass."""

    def test_success_result(self):
        r = NotificationResult(delivered=True, channel="ws", detail="ok")
        assert r.delivered is True
        assert r.channel == "ws"
        assert r.detail == "ok"

    def test_to_dict(self):
        r = NotificationResult(delivered=False, channel="telegram", detail="err")
        d = r.to_dict()
        assert d == {"delivered": False, "channel": "telegram", "detail": "err"}

    def test_to_dict_empty_detail(self):
        r = NotificationResult(delivered=True, channel="ws")
        d = r.to_dict()
        assert d["detail"] == ""


# =============================================================================
# ABC Contract Tests
# =============================================================================

class TestNotificationChannelAdapterABC:
    """Tests that ABC enforces interface."""

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            NotificationChannelAdapter()

    def test_concrete_implementation(self):
        class DummyAdapter(NotificationChannelAdapter):
            def get_config(self):
                return ChannelConfig(id="dummy", display_name="Dummy")

            async def send(self, user_id, message, metadata=None):
                return NotificationResult(delivered=True, channel="dummy")

        a = DummyAdapter()
        assert a.get_config().id == "dummy"
        assert a.validate_config() is True

    def test_validate_config_default_true(self):
        class MinAdapter(NotificationChannelAdapter):
            def get_config(self):
                return ChannelConfig(id="min", display_name="Min")

            async def send(self, user_id, message, metadata=None):
                return NotificationResult(delivered=True, channel="min")

        assert MinAdapter().validate_config() is True


# =============================================================================
# Registry Tests
# =============================================================================

class TestNotificationChannelRegistry:
    """Tests for NotificationChannelRegistry."""

    def _make_adapter(self, channel_id, enabled=True):
        adapter = MagicMock(spec=NotificationChannelAdapter)
        adapter.get_config.return_value = ChannelConfig(
            id=channel_id, display_name=channel_id.title(), enabled=enabled
        )
        return adapter

    def test_register_and_get(self):
        reg = NotificationChannelRegistry()
        adapter = self._make_adapter("ws")
        reg.register(adapter)

        assert reg.get("ws") is adapter
        assert reg.get("missing") is None

    def test_list_ids(self):
        reg = NotificationChannelRegistry()
        reg.register(self._make_adapter("a"))
        reg.register(self._make_adapter("b"))

        ids = reg.list_ids()
        assert "a" in ids
        assert "b" in ids

    def test_clear(self):
        reg = NotificationChannelRegistry()
        reg.register(self._make_adapter("x"))
        assert len(reg) == 1

        reg.clear()
        assert len(reg) == 0
        assert reg.get("x") is None

    def test_get_all_enabled(self):
        reg = NotificationChannelRegistry()
        reg.register(self._make_adapter("on", enabled=True))
        reg.register(self._make_adapter("off", enabled=False))

        enabled = reg.get_all_enabled()
        assert len(enabled) == 1
        assert enabled[0].get_config().id == "on"

    def test_overwrite_adapter(self):
        reg = NotificationChannelRegistry()
        a1 = self._make_adapter("ws")
        a2 = self._make_adapter("ws")
        reg.register(a1)
        reg.register(a2)

        assert reg.get("ws") is a2
        assert len(reg) == 1

    def test_len(self):
        reg = NotificationChannelRegistry()
        assert len(reg) == 0
        reg.register(self._make_adapter("a"))
        reg.register(self._make_adapter("b"))
        assert len(reg) == 2


class TestRegistrySingleton:
    """Tests for get_notification_channel_registry singleton."""

    def test_singleton_returns_same_instance(self):
        import app.services.notifications.registry as mod
        old = mod._registry_instance
        mod._registry_instance = None

        try:
            r1 = get_notification_channel_registry()
            r2 = get_notification_channel_registry()
            assert r1 is r2
        finally:
            mod._registry_instance = old


# =============================================================================
# Init Function Tests
# =============================================================================

class TestInitNotificationChannels:
    """Tests for init_notification_channels()."""

    def test_all_channels_enabled(self):
        """All 3 channels registered when all flags enabled."""
        mock_settings = MagicMock()
        mock_settings.enable_websocket = True
        mock_settings.enable_telegram = True
        mock_settings.telegram_bot_token = "bot-123"
        mock_settings.living_agent_callmebot_api_key = "api-key"
        mock_settings.enable_zalo = False
        mock_settings.zalo_oa_access_token = None

        # Clear singleton state
        import app.services.notifications.registry as reg_mod
        old = reg_mod._registry_instance
        reg_mod._registry_instance = None

        try:
            with patch("app.core.config.settings", mock_settings):
                from app.services.notifications import init_notification_channels
                registry = init_notification_channels()

            ids = registry.list_ids()
            assert "websocket" in ids
            assert "telegram" in ids
            assert "messenger" in ids
            assert len(registry) == 3
        finally:
            reg_mod._registry_instance = old

    def test_no_channels_enabled(self):
        """No adapters registered when all flags disabled."""
        mock_settings = MagicMock()
        mock_settings.enable_websocket = False
        mock_settings.enable_telegram = False
        mock_settings.telegram_bot_token = None
        mock_settings.living_agent_callmebot_api_key = None
        mock_settings.enable_zalo = False
        mock_settings.zalo_oa_access_token = None

        import app.services.notifications.registry as reg_mod
        old = reg_mod._registry_instance
        reg_mod._registry_instance = None

        try:
            with patch("app.core.config.settings", mock_settings):
                from app.services.notifications import init_notification_channels
                registry = init_notification_channels()

            assert len(registry) == 0
        finally:
            reg_mod._registry_instance = old

    def test_only_websocket(self):
        """Only websocket registered when others disabled."""
        mock_settings = MagicMock()
        mock_settings.enable_websocket = True
        mock_settings.enable_telegram = False
        mock_settings.telegram_bot_token = None
        mock_settings.living_agent_callmebot_api_key = None
        mock_settings.enable_zalo = False
        mock_settings.zalo_oa_access_token = None

        import app.services.notifications.registry as reg_mod
        old = reg_mod._registry_instance
        reg_mod._registry_instance = None

        try:
            with patch("app.core.config.settings", mock_settings):
                from app.services.notifications import init_notification_channels
                registry = init_notification_channels()

            assert registry.list_ids() == ["websocket"]
        finally:
            reg_mod._registry_instance = old

    def test_telegram_needs_both_flag_and_token(self):
        """Telegram requires enable_telegram=True AND telegram_bot_token set."""
        mock_settings = MagicMock()
        mock_settings.enable_websocket = False
        mock_settings.enable_telegram = True
        mock_settings.telegram_bot_token = None  # No token
        mock_settings.living_agent_callmebot_api_key = None
        mock_settings.enable_zalo = False
        mock_settings.zalo_oa_access_token = None

        import app.services.notifications.registry as reg_mod
        old = reg_mod._registry_instance
        reg_mod._registry_instance = None

        try:
            with patch("app.core.config.settings", mock_settings):
                from app.services.notifications import init_notification_channels
                registry = init_notification_channels()

            assert "telegram" not in registry.list_ids()
        finally:
            reg_mod._registry_instance = old

    def test_messenger_needs_api_key(self):
        """Messenger requires callmebot_api_key to be set."""
        mock_settings = MagicMock()
        mock_settings.enable_websocket = False
        mock_settings.enable_telegram = False
        mock_settings.telegram_bot_token = None
        mock_settings.living_agent_callmebot_api_key = "key-123"
        mock_settings.enable_zalo = False
        mock_settings.zalo_oa_access_token = None

        import app.services.notifications.registry as reg_mod
        old = reg_mod._registry_instance
        reg_mod._registry_instance = None

        try:
            with patch("app.core.config.settings", mock_settings):
                from app.services.notifications import init_notification_channels
                registry = init_notification_channels()

            assert registry.list_ids() == ["messenger"]
        finally:
            reg_mod._registry_instance = old


# =============================================================================
# Adapter Config Tests
# =============================================================================

class TestAdapterConfigs:
    """Tests for each adapter's get_config()."""

    def test_websocket_config(self):
        from app.services.notifications.adapters.websocket import WebSocketAdapter
        cfg = WebSocketAdapter().get_config()
        assert cfg.id == "websocket"
        assert cfg.enabled is True
        assert cfg.requires_config is False

    def test_telegram_config(self):
        from app.services.notifications.adapters.telegram import TelegramAdapter
        cfg = TelegramAdapter().get_config()
        assert cfg.id == "telegram"
        assert cfg.enabled is True
        assert cfg.requires_config is True

    def test_messenger_config(self):
        from app.services.notifications.adapters.messenger import MessengerAdapter
        cfg = MessengerAdapter().get_config()
        assert cfg.id == "messenger"
        assert cfg.enabled is True
        assert cfg.requires_config is True


class TestAdapterValidateConfig:
    """Tests for validate_config() on each adapter."""

    def test_websocket_validate_always_true(self):
        from app.services.notifications.adapters.websocket import WebSocketAdapter
        assert WebSocketAdapter().validate_config() is True

    def test_telegram_validate_with_token(self):
        from app.services.notifications.adapters.telegram import TelegramAdapter
        mock_settings = MagicMock()
        mock_settings.telegram_bot_token = "bot-123"
        with patch("app.core.config.settings", mock_settings):
            assert TelegramAdapter().validate_config() is True

    def test_telegram_validate_without_token(self):
        from app.services.notifications.adapters.telegram import TelegramAdapter
        mock_settings = MagicMock()
        mock_settings.telegram_bot_token = None
        with patch("app.core.config.settings", mock_settings):
            assert TelegramAdapter().validate_config() is False

    def test_messenger_validate_with_key(self):
        from app.services.notifications.adapters.messenger import MessengerAdapter
        mock_settings = MagicMock()
        mock_settings.living_agent_callmebot_api_key = "key-123"
        with patch("app.core.config.settings", mock_settings):
            assert MessengerAdapter().validate_config() is True

    def test_messenger_validate_without_key(self):
        from app.services.notifications.adapters.messenger import MessengerAdapter
        mock_settings = MagicMock()
        mock_settings.living_agent_callmebot_api_key = None
        with patch("app.core.config.settings", mock_settings):
            assert MessengerAdapter().validate_config() is False


# =============================================================================
# Dispatcher + Registry Integration Tests
# =============================================================================

class TestDispatcherRegistryIntegration:
    """Tests for NotificationDispatcher using registry."""

    @pytest.mark.asyncio
    async def test_dispatcher_routes_to_registered_adapter(self):
        """Dispatcher delegates to the correct adapter from registry."""
        from app.services.notification_dispatcher import NotificationDispatcher

        dispatcher = NotificationDispatcher()
        registry = NotificationChannelRegistry()
        dispatcher._registry = registry

        mock_adapter = MagicMock()
        mock_adapter.get_config.return_value = ChannelConfig(id="test", display_name="Test")
        mock_adapter.send = AsyncMock(return_value=NotificationResult(
            delivered=True, channel="test", detail="sent"
        ))
        registry.register(mock_adapter)

        result = await dispatcher.notify_user("user-1", "hello", channel="test")

        assert result == {"delivered": True, "channel": "test", "detail": "sent"}
        mock_adapter.send.assert_called_once_with("user-1", "hello", None)

    @pytest.mark.asyncio
    async def test_dispatcher_passes_metadata_to_adapter(self):
        """Dispatcher forwards metadata to adapter.send()."""
        from app.services.notification_dispatcher import NotificationDispatcher

        dispatcher = NotificationDispatcher()
        registry = NotificationChannelRegistry()
        dispatcher._registry = registry

        mock_adapter = MagicMock()
        mock_adapter.get_config.return_value = ChannelConfig(id="test", display_name="Test")
        mock_adapter.send = AsyncMock(return_value=NotificationResult(
            delivered=True, channel="test"
        ))
        registry.register(mock_adapter)

        meta = {"task_id": "t1"}
        await dispatcher.notify_user("u1", "msg", channel="test", metadata=meta)

        mock_adapter.send.assert_called_once_with("u1", "msg", meta)

    @pytest.mark.asyncio
    async def test_dispatcher_unknown_channel_returns_failure(self):
        """Dispatcher returns failure dict for unregistered channel."""
        from app.services.notification_dispatcher import NotificationDispatcher

        dispatcher = NotificationDispatcher()
        registry = NotificationChannelRegistry()
        dispatcher._registry = registry

        result = await dispatcher.notify_user("u1", "msg", channel="discord")

        assert result["delivered"] is False
        assert "Unknown channel: discord" in result["detail"]

    @pytest.mark.asyncio
    async def test_dispatcher_lazy_init_registry(self):
        """Dispatcher lazy-initializes registry on first use."""
        from app.services.notification_dispatcher import NotificationDispatcher

        dispatcher = NotificationDispatcher()
        assert dispatcher._registry is None

        mock_settings = MagicMock()
        mock_settings.enable_websocket = False
        mock_settings.enable_telegram = False
        mock_settings.telegram_bot_token = None
        mock_settings.living_agent_callmebot_api_key = None

        import app.services.notifications.registry as reg_mod
        old = reg_mod._registry_instance
        reg_mod._registry_instance = None

        try:
            with patch("app.core.config.settings", mock_settings):
                result = await dispatcher.notify_user("u1", "msg", channel="ws")

            # Registry should now be initialized (even though channel not found)
            assert dispatcher._registry is not None
        finally:
            reg_mod._registry_instance = old

    @pytest.mark.asyncio
    async def test_notify_task_result_backward_compat(self):
        """notify_task_result still returns dict (backward compat)."""
        from app.services.notification_dispatcher import NotificationDispatcher

        dispatcher = NotificationDispatcher()
        registry = NotificationChannelRegistry()
        dispatcher._registry = registry

        mock_adapter = MagicMock()
        mock_adapter.get_config.return_value = ChannelConfig(id="websocket", display_name="WS")
        mock_adapter.send = AsyncMock(return_value=NotificationResult(
            delivered=True, channel="websocket", detail="ok"
        ))
        registry.register(mock_adapter)

        task = {"id": "t1", "user_id": "u1", "description": "Test", "channel": "websocket"}
        result_data = {"mode": "notification", "response": "Done"}

        result = await dispatcher.notify_task_result(task, result_data)

        assert isinstance(result, dict)
        assert result["delivered"] is True
