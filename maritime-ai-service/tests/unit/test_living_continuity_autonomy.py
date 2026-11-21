import json
import logging
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from tests.unit.living_continuity_helpers import (
    reset_runtime_metrics as reset_runtime_metrics,
)


class TestAutonomyManagerOrgScope:
    """Test org-scoped autonomy graduation guardrails."""

    @pytest.mark.asyncio
    async def test_autonomy_graduation_blocks_missing_org_context_before_db(
        self,
        monkeypatch,
        caplog,
    ):
        """Graduation checks fail closed without org context."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.autonomy_manager import AutonomyManager

        manager = AutonomyManager()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        monkeypatch.setattr(settings, "living_agent_enable_autonomy_graduation", True)
        monkeypatch.setattr(settings, "living_agent_autonomy_level", 0)
        caplog.set_level(logging.WARNING)

        token = current_org_id.set(None)
        try:
            with patch("app.core.database.get_shared_session_factory") as mock_factory:
                upgraded = await manager.check_graduation()
        finally:
            current_org_id.reset(token)

        assert upgraded is False
        mock_factory.assert_not_called()
        assert "autonomy_manager_blocked_missing_org_context" in caplog.text

    @pytest.mark.asyncio
    async def test_autonomy_load_stats_filters_by_org_context(self, monkeypatch):
        """Autonomy stats only aggregate current-org heartbeat audit rows."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.autonomy_manager import AutonomyManager

        manager = AutonomyManager()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        mock_session = MagicMock()
        mock_session.execute.return_value.fetchone.return_value = (
            10,
            datetime.now(timezone.utc) - timedelta(days=20),
            1,
        )
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
                stats = await manager._load_stats()
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert stats["successful_actions"] == 9
        assert "WHERE organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"

    @pytest.mark.asyncio
    async def test_autonomy_approve_graduation_upserts_by_org_key(self, monkeypatch):
        """Approved autonomy levels are keyed by org and state key."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.autonomy_manager import AutonomyManager

        manager = AutonomyManager()
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
                approved = await manager.approve_graduation(1)
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert approved is True
        assert "organization_id" in statement
        assert "ON CONFLICT (organization_id, key)" in statement
        assert params["org_id"] == "org-A"

    @pytest.mark.asyncio
    async def test_autonomy_pending_graduation_upserts_by_org_key(self, monkeypatch):
        """Pending graduation proposals are isolated by org."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.autonomy_manager import AutonomyManager

        manager = AutonomyManager()
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
                await manager._propose_graduation(
                    0,
                    1,
                    {"successful_actions": 50},
                )
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert "organization_id" in statement
        assert "ON CONFLICT (organization_id, key)" in statement
        assert params["org_id"] == "org-A"
        payload = json.loads(params["data"])
        assert payload["to_level"] == 1
