import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.unit.living_continuity_helpers import (
    reset_runtime_metrics as reset_runtime_metrics,
)


class TestBriefingComposerOrgScope:
    """Test org-scoped autonomous briefing guardrails."""

    @pytest.mark.asyncio
    async def test_briefing_compose_blocks_missing_org_context_before_llm_or_db(
        self,
        monkeypatch,
        caplog,
    ):
        """Briefing composition fails closed without org context."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.briefing_composer import BriefingComposer

        composer = BriefingComposer()
        monkeypatch.setattr(settings, "living_agent_enable_briefing", True)
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        caplog.set_level(logging.WARNING)

        token = current_org_id.set(None)
        try:
            with patch("app.engine.living_agent.weather_service.get_weather_service") as mock_weather, \
                 patch("app.engine.living_agent.local_llm.get_local_llm") as mock_llm, \
                 patch("app.core.database.get_shared_session_factory") as mock_factory:
                briefing = await composer.compose_for_time()
        finally:
            current_org_id.reset(token)

        assert briefing is None
        mock_weather.assert_not_called()
        mock_llm.assert_not_called()
        mock_factory.assert_not_called()
        assert "briefing_composer_blocked_missing_org_context" in caplog.text

    @pytest.mark.asyncio
    async def test_briefing_highlights_filter_by_org_context(self, monkeypatch):
        """Briefing highlights only read current-org browsing rows."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.briefing_composer import BriefingComposer

        composer = BriefingComposer()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = [("Org A headline",)]
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
                highlights = await composer._get_recent_highlights(2)
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert highlights == ["Org A headline"]
        assert "AND organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"
        assert params["count"] == 2

    def test_briefing_save_includes_org_context(self, monkeypatch):
        """Briefing audit rows include resolved org scope."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.briefing_composer import BriefingComposer
        from app.engine.living_agent.models import Briefing, BriefingType

        composer = BriefingComposer()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        briefing = Briefing(briefing_type=BriefingType.MORNING, content="Org scoped")

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
                composer._save_briefing(briefing)
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert "organization_id" in statement
        assert params["org_id"] == "org-A"
        assert briefing.organization_id == "org-A"

    @pytest.mark.asyncio
    async def test_briefing_deliver_blocks_missing_org_context_before_send_or_db(
        self,
        monkeypatch,
        caplog,
    ):
        """Briefing delivery fails closed before outbound channel sends."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.briefing_composer import BriefingComposer
        from app.engine.living_agent.models import Briefing, BriefingType

        composer = BriefingComposer()
        briefing = Briefing(briefing_type=BriefingType.MORNING, content="PRIVATE BRIEFING")
        monkeypatch.setattr(settings, "living_agent_briefing_channels", '["messenger"]')
        monkeypatch.setattr(settings, "living_agent_briefing_users", '["raw-user"]')
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        caplog.set_level(logging.WARNING)

        token = current_org_id.set(None)
        try:
            with patch.object(composer, "_send_to_channel", new_callable=AsyncMock) as mock_send, \
                 patch("app.core.database.get_shared_session_factory") as mock_factory:
                delivered = await composer.deliver(briefing)
        finally:
            current_org_id.reset(token)

        assert delivered == []
        mock_send.assert_not_called()
        mock_factory.assert_not_called()
        assert "briefing_composer_blocked_missing_org_context" in caplog.text
        assert "PRIVATE BRIEFING" not in caplog.text
        assert "raw-user" not in caplog.text

    @pytest.mark.asyncio
    async def test_briefing_delivery_window_is_scoped_per_org(self, monkeypatch):
        """One org's daily briefing marker does not suppress another org."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.briefing_composer import BriefingComposer
        from app.engine.living_agent.models import Briefing, BriefingType

        composer = BriefingComposer()
        monkeypatch.setattr(settings, "living_agent_enable_briefing", True)
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        today = "2026-01-02"
        composer._delivered_today[("org-B", BriefingType.MORNING)] = today

        token = current_org_id.set("org-A")
        try:
            with patch("app.engine.living_agent.briefing_composer.datetime") as mock_datetime, \
                 patch.object(
                     composer,
                     "_compose_morning",
                     new_callable=AsyncMock,
                     return_value=Briefing(briefing_type=BriefingType.MORNING, content="Org A"),
                 ) as mock_compose:
                mock_datetime.now.return_value = datetime(2026, 1, 1, 23, 0, tzinfo=timezone.utc)
                briefing = await composer.compose_for_time()
        finally:
            current_org_id.reset(token)

        assert briefing is not None
        assert briefing.organization_id == "org-A"
        mock_compose.assert_awaited_once()
        assert composer._delivered_today[("org-A", BriefingType.MORNING)] == today
