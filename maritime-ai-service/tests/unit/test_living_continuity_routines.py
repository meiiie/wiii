import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.unit.living_continuity_helpers import (
    reset_runtime_metrics as reset_runtime_metrics,
)


class TestRoutineTrackerOrgScope:
    """Test org-scoped routine tracking guardrails."""

    @pytest.mark.asyncio
    async def test_routine_record_blocks_missing_org_context_before_db(
        self,
        monkeypatch,
        caplog,
    ):
        """Routine writes fail closed without org context."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.routine_tracker import RoutineTracker

        tracker = RoutineTracker()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        monkeypatch.setattr(settings, "living_agent_enable_routine_tracking", True)
        caplog.set_level(logging.WARNING)

        token = current_org_id.set(None)
        try:
            with patch("app.core.database.get_shared_session_factory") as mock_factory:
                await tracker.record_interaction(
                    "raw-routine-user",
                    "web",
                    "PRIVATE ROUTINE TOPIC",
                )
        finally:
            current_org_id.reset(token)

        mock_factory.assert_not_called()
        assert "routine_tracking_blocked_missing_org_context" in caplog.text
        assert "raw-routine-user" not in caplog.text
        assert "PRIVATE ROUTINE TOPIC" not in caplog.text

    @pytest.mark.asyncio
    async def test_inactive_user_query_filters_by_org_context(self, monkeypatch):
        """Inactive-user reads only return current-org routines."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.routine_tracker import RoutineTracker

        tracker = RoutineTracker()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = [("user-a",)]
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
                inactive = await tracker.get_inactive_users(days=2)
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert inactive == ["user-a"]
        assert "organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"

    @pytest.mark.asyncio
    async def test_routine_load_blocks_missing_org_column(self, monkeypatch, caplog):
        """Legacy local routine tables fail closed until migration 051 is applied."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.routine_tracker import RoutineTracker

        tracker = RoutineTracker()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        caplog.set_level(logging.WARNING)

        schema_result = MagicMock()
        schema_result.fetchone.return_value = None
        mock_session = MagicMock()
        mock_session.execute.return_value = schema_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
                routine = await tracker.get_routine("raw-routine-user")
        finally:
            current_org_id.reset(token)

        assert routine is None
        assert mock_session.execute.call_count == 1
        assert "routine_tracking_blocked_missing_org_column" in caplog.text
        assert "raw-routine-user" not in caplog.text

    @pytest.mark.asyncio
    async def test_routine_upsert_uses_org_conflict_key(self, monkeypatch):
        """Routine profile writes are keyed by org and user."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.models import UserRoutine
        from app.engine.living_agent.routine_tracker import RoutineTracker

        tracker = RoutineTracker()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        routine = UserRoutine(
            user_id="raw-routine-user",
            typical_active_hours=[8],
            common_topics=["PRIVATE ROUTINE TOPIC"],
            total_messages=6,
            last_seen=datetime.now(timezone.utc),
        )
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
                await tracker._save_routine(routine)
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert "organization_id" in statement
        assert "ON CONFLICT (organization_id, user_id)" in statement
        assert params["org_id"] == "org-A"
        assert params["uid"] == "raw-routine-user"

    @pytest.mark.asyncio
    async def test_routine_load_filters_by_org_context(self, monkeypatch):
        """Routine reads request exactly one org/user row."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.routine_tracker import RoutineTracker

        tracker = RoutineTracker()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        mock_result = MagicMock()
        mock_result.fetchone.return_value = (
            "raw-routine-user",
            [8],
            8,
            1.0,
            ["maritime"],
            datetime.now(timezone.utc),
            6,
            datetime.now(timezone.utc),
            "org-A",
        )
        mock_session = MagicMock()
        mock_session.execute.return_value = mock_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
                routine = await tracker.get_routine("raw-routine-user")
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert routine is not None
        assert routine.organization_id == "org-A"
        assert "organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"
