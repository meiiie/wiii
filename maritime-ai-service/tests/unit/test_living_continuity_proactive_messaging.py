import json
import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.unit.living_continuity_helpers import (
    _counter_value,
    _histogram_values,
    reset_runtime_metrics as reset_runtime_metrics,
)


class TestProactiveMessengerOrgScope:
    """Test org-scoped proactive messaging guardrails."""

    @pytest.mark.asyncio
    async def test_proactive_send_blocks_missing_org_context_before_delivery(
        self,
        monkeypatch,
        caplog,
    ):
        """Autonomous proactive sends fail closed before delivery without org."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.proactive_messenger import ProactiveMessenger

        messenger = ProactiveMessenger()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        caplog.set_level(logging.WARNING)

        token = current_org_id.set(None)
        try:
            with patch.object(messenger, "_deliver", new_callable=AsyncMock) as mock_deliver, \
                 patch("app.core.database.get_shared_session_factory") as mock_factory:
                sent = await messenger.send(
                    "raw-proactive-user",
                    "messenger",
                    "PRIVATE PROACTIVE BODY",
                    trigger="briefing",
                )
        finally:
            current_org_id.reset(token)

        assert sent is False
        mock_deliver.assert_not_called()
        mock_factory.assert_not_called()
        assert "proactive_message_blocked_missing_org_context" in caplog.text
        assert "raw-proactive-user" not in caplog.text
        assert "PRIVATE PROACTIVE BODY" not in caplog.text
        assert _counter_value(
            "runtime.living_agent.proactive.sends",
            {"status": "blocked_missing_org_context"},
        ) == 1

    @pytest.mark.asyncio
    async def test_proactive_opt_out_filters_by_org_context(self, monkeypatch):
        """Opt-out writes are keyed by current org and user."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.proactive_messenger import ProactiveMessenger

        messenger = ProactiveMessenger()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
                await messenger.opt_out("raw-proactive-user")
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert "organization_id" in statement
        assert "ON CONFLICT (organization_id, user_id)" in statement
        assert params["org_id"] == "org-A"
        assert params["uid"] == "raw-proactive-user"

    @pytest.mark.asyncio
    async def test_proactive_can_send_reads_opt_out_by_org_context(self, monkeypatch):
        """Opt-out reads use request org before allowing autonomous send."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.proactive_messenger import ProactiveMessenger

        messenger = ProactiveMessenger()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        monkeypatch.setattr(settings, "living_agent_enable_proactive_messaging", True)
        monkeypatch.setattr(settings, "living_agent_proactive_quiet_start", 23)
        monkeypatch.setattr(settings, "living_agent_proactive_quiet_end", 5)
        monkeypatch.setattr(settings, "living_agent_max_proactive_per_day", 3)

        mock_result = MagicMock()
        mock_result.fetchone.return_value = (False,)
        mock_session = MagicMock()
        mock_session.execute.return_value = mock_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)
        fixed_time = datetime(2026, 2, 26, 3, 0, 0, tzinfo=timezone.utc)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory), \
                 patch("app.engine.living_agent.proactive_messenger.datetime") as mock_dt:
                mock_dt.now.return_value = fixed_time
                mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
                allowed = await messenger.can_send("raw-proactive-user")
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert allowed is True
        assert "organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"
        assert _counter_value(
            "runtime.living_agent.proactive.can_send",
            {"status": "allowed", "reason": "allowed"},
        ) == 1

    @pytest.mark.asyncio
    async def test_proactive_save_message_includes_org_context(self, monkeypatch):
        """Proactive message log rows include current org scope."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.models import ProactiveMessage
        from app.engine.living_agent.proactive_messenger import ProactiveMessenger

        messenger = ProactiveMessenger()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        message = ProactiveMessage(
            user_id="raw-proactive-user",
            channel="messenger",
            content="PRIVATE PROACTIVE BODY",
            trigger="briefing",
        )

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
                await messenger._save_message(message)
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert "organization_id" in statement
        assert params["org_id"] == "org-A"
        assert params["uid"] == "raw-proactive-user"
        assert params["content"] == "PRIVATE PROACTIVE BODY"

    @pytest.mark.asyncio
    async def test_proactive_send_records_delivered_metric(self, monkeypatch):
        """Delivered proactive sends are visible without user/content labels."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.proactive_messenger import ProactiveMessenger

        messenger = ProactiveMessenger()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        token = current_org_id.set("org-A")
        try:
            with patch.object(messenger, "can_send", new_callable=AsyncMock, return_value=True), \
                 patch.object(messenger, "_deliver", new_callable=AsyncMock, return_value=True), \
                 patch.object(messenger, "_save_message", new_callable=AsyncMock):
                sent = await messenger.send(
                    "raw-proactive-user",
                    "messenger",
                    "PRIVATE PROACTIVE BODY",
                    trigger="briefing",
                )
        finally:
            current_org_id.reset(token)

        assert sent is True
        assert _counter_value(
            "runtime.living_agent.proactive.sends",
            {"status": "delivered"},
        ) == 1
        assert _histogram_values(
            "runtime.living_agent.proactive.send_duration_ms",
            {"status": "delivered"},
        )

    @pytest.mark.asyncio
    async def test_proactive_send_records_delivery_failed_metric(self, monkeypatch):
        """Delivery failures are distinct from guardrail blocks."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.proactive_messenger import ProactiveMessenger

        messenger = ProactiveMessenger()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        token = current_org_id.set("org-A")
        try:
            with patch.object(messenger, "can_send", new_callable=AsyncMock, return_value=True), \
                 patch.object(messenger, "_deliver", new_callable=AsyncMock, return_value=False), \
                 patch.object(messenger, "_save_message", new_callable=AsyncMock) as mock_save:
                sent = await messenger.send(
                    "raw-proactive-user",
                    "messenger",
                    "PRIVATE PROACTIVE BODY",
                    trigger="briefing",
                )
        finally:
            current_org_id.reset(token)

        assert sent is False
        mock_save.assert_not_called()
        assert _counter_value(
            "runtime.living_agent.proactive.sends",
            {"status": "delivery_failed"},
        ) == 1

    @pytest.mark.asyncio
    async def test_proactive_websocket_delivery_uses_org_scoped_connection_manager(
        self,
        monkeypatch,
    ):
        """A proactive WebSocket send reaches only sessions in the current org."""
        from app.api.v1.websocket import ConnectionManager
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.proactive_messenger import ProactiveMessenger
        from app.services.notification_dispatcher import NotificationDispatcher
        from app.services.notifications.adapters.websocket import WebSocketAdapter
        from app.services.notifications.registry import NotificationChannelRegistry

        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        monkeypatch.setattr(settings, "living_agent_enable_proactive_messaging", True)
        monkeypatch.setattr(settings, "living_agent_proactive_quiet_start", 0)
        monkeypatch.setattr(settings, "living_agent_proactive_quiet_end", 0)
        monkeypatch.setattr(settings, "living_agent_max_proactive_per_day", 3)

        registry = NotificationChannelRegistry()
        registry.register(WebSocketAdapter())
        dispatcher = NotificationDispatcher()
        dispatcher._registry = registry
        manager = ConnectionManager()
        org_socket = AsyncMock()
        other_org_socket = AsyncMock()
        await manager.connect(org_socket, "proactive-org-session")
        await manager.connect(other_org_socket, "proactive-other-org-session")
        manager.register_user("proactive-org-session", "proactive-user", "org-proactive")
        manager.register_user(
            "proactive-other-org-session",
            "proactive-user",
            "org-other",
        )

        messenger = ProactiveMessenger()
        token = current_org_id.set("org-proactive")
        try:
            with patch.object(
                messenger,
                "_is_opted_out",
                new_callable=AsyncMock,
                return_value=False,
            ), patch.object(
                messenger,
                "_save_message",
                new_callable=AsyncMock,
            ) as mock_save, patch(
                "app.services.notification_dispatcher.get_notification_dispatcher",
                return_value=dispatcher,
            ), patch("app.api.v1.websocket.manager", manager):
                sent = await messenger.send(
                    "proactive-user",
                    "websocket",
                    "Review COLREG Rule 13 soon",
                    trigger="inactive_reengage",
                )
        finally:
            current_org_id.reset(token)

        assert sent is True
        org_socket.send_text.assert_awaited_once()
        sent_payload = json.loads(org_socket.send_text.await_args.args[0])
        assert sent_payload["type"] == "proactive_message"
        assert sent_payload["content"] == "Review COLREG Rule 13 soon"
        assert sent_payload["trigger"] == "inactive_reengage"
        other_org_socket.send_text.assert_not_awaited()
        saved_message = mock_save.await_args.args[0]
        assert saved_message.user_id == "proactive-user"
        assert saved_message.channel == "websocket"
        assert saved_message.organization_id == "org-proactive"
        assert messenger._daily_counts["org-proactive:proactive-user"] == 1
        assert _counter_value(
            "runtime.living_agent.proactive.can_send",
            {"status": "allowed", "reason": "allowed"},
        ) == 1
        assert _counter_value(
            "runtime.living_agent.proactive.sends",
            {"status": "delivered"},
        ) == 1
