"""
Tests for Sprint 171: API Endpoints — browsing log, pending actions,
heartbeat audit.

Sprint 171: "Quyền Tự Chủ" — Safety-first autonomous capabilities.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


def _make_settings(**overrides):
    """Create a mock settings object."""
    defaults = {"enable_living_agent": True}
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


# Lazy imports → patch at SOURCE module
_SETTINGS_PATCH = "app.core.config.settings"
_DB_PATCH = "app.api.v1.living_agent_support.get_shared_session_factory"
_SCHED_PATCH = "app.engine.living_agent.heartbeat.get_heartbeat_scheduler"


class TestBrowsingLogEndpoint:
    """Tests for GET /living-agent/browsing-log."""

    @pytest.mark.asyncio
    async def test_browsing_log_returns_items(self):
        """Should return browsing log entries from DB."""
        from app.api.v1.living_agent import get_browsing_log

        now = datetime.now(timezone.utc)
        mock_rows = [
            ("id-1", "web_search", "https://example.com", "Test Title",
             "Summary text", 0.85, now),
        ]

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_session.execute.return_value = mock_result

        mock_factory = MagicMock()
        mock_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_factory.return_value.__exit__ = MagicMock(return_value=False)

        settings = _make_settings()

        with patch(_SETTINGS_PATCH, settings), \
             patch(_DB_PATCH, return_value=mock_factory):

            result = await get_browsing_log(MagicMock(), MagicMock(), days=7, limit=50)

            assert len(result) == 1
            assert result[0].title == "Test Title"
            assert result[0].relevance_score == 0.85


class TestPendingActionsEndpoint:
    """Tests for GET/POST /living-agent/pending-actions."""

    @pytest.mark.asyncio
    async def test_pending_actions_returns_items(self):
        """Should return pending actions from DB."""
        from app.api.v1.living_agent import get_pending_actions

        now = datetime.now(timezone.utc)
        mock_rows = [
            ("act-1", "browse_social", "news", 0.6, "pending", now, None, None),
        ]

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_session.execute.return_value = mock_result

        mock_factory = MagicMock()
        mock_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_factory.return_value.__exit__ = MagicMock(return_value=False)

        settings = _make_settings()

        with patch(_SETTINGS_PATCH, settings), \
             patch(_DB_PATCH, return_value=mock_factory):

            result = await get_pending_actions(
                MagicMock(), MagicMock(), status_filter="pending",
            )

            assert len(result) == 1
            assert result[0].action_type == "browse_social"
            assert result[0].status == "pending"

    @pytest.mark.asyncio
    async def test_resolve_action_approve(self):
        """Approving a pending action should execute it."""
        from app.api.v1.living_agent import resolve_pending_action, ResolveActionRequest

        mock_session = MagicMock()
        # First query: check status
        mock_status_result = MagicMock()
        mock_status_result.fetchone.return_value = ("pending",)
        mock_session.execute.return_value = mock_status_result

        mock_factory = MagicMock()
        mock_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_factory.return_value.__exit__ = MagicMock(return_value=False)

        settings = _make_settings()
        auth = MagicMock()
        auth.user_id = "admin-1"

        from app.engine.living_agent.models import HeartbeatResult
        mock_result = HeartbeatResult()

        with patch(_SETTINGS_PATCH, settings), \
             patch(_DB_PATCH, return_value=mock_factory), \
             patch(_SCHED_PATCH) as mock_sched:

            mock_sched.return_value.execute_approved_action = AsyncMock(return_value=mock_result)

            body = ResolveActionRequest(decision="approve")
            result = await resolve_pending_action(MagicMock(), auth, "act-1", body)

            assert result["status"] == "approved_and_executed"
            mock_sched.return_value.execute_approved_action.assert_called_once_with("act-1")

    @pytest.mark.asyncio
    async def test_resolve_action_reject(self):
        """Rejecting a pending action should not execute it."""
        from app.api.v1.living_agent import resolve_pending_action, ResolveActionRequest

        mock_session = MagicMock()
        mock_status_result = MagicMock()
        mock_status_result.fetchone.return_value = ("pending",)
        mock_session.execute.return_value = mock_status_result

        mock_factory = MagicMock()
        mock_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_factory.return_value.__exit__ = MagicMock(return_value=False)

        settings = _make_settings()
        auth = MagicMock()
        auth.user_id = "admin-1"

        with patch(_SETTINGS_PATCH, settings), \
             patch(_DB_PATCH, return_value=mock_factory):

            body = ResolveActionRequest(decision="reject")
            result = await resolve_pending_action(MagicMock(), auth, "act-1", body)

            assert result["status"] == "rejected"


class TestHeartbeatAuditEndpoint:
    """Tests for GET /living-agent/heartbeat/audit."""

    @pytest.mark.asyncio
    async def test_heartbeat_audit_returns_entries(self):
        """Should return audit log entries from DB."""
        from app.api.v1.living_agent import get_heartbeat_audit

        now = datetime.now(timezone.utc)
        mock_rows = [
            ("audit-1", 5, '[{"action_type": "check_goals", "target": ""}]',
             0, 150, None, now),
        ]

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_session.execute.return_value = mock_result

        mock_factory = MagicMock()
        mock_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_factory.return_value.__exit__ = MagicMock(return_value=False)

        settings = _make_settings()

        with patch(_SETTINGS_PATCH, settings), \
             patch(_DB_PATCH, return_value=mock_factory):

            result = await get_heartbeat_audit(MagicMock(), MagicMock(), limit=20)

            assert len(result) == 1
            assert result[0].cycle_number == 5
            assert result[0].duration_ms == 150
            assert len(result[0].actions_taken) == 1
            assert result[0].actions_taken[0]["action_type"] == "check_goals"
